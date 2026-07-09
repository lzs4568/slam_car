/**
 * RK3588 mpph264enc → raw TCP 推流节点
 *
 * 管道: appsrc(BGR) → videoconvert → NV12 → mpph264enc → h264parse → appsink
 * appsink 回调拿 h264 byte-stream → TCP 广播给所有客户端
 *
 * 客户端拉流:
 *   gst-launch-1.0 tcpclientsrc host=192.168.5.10 port=8554 ! h264parse ! avdec_h264 ! autovideosink
 *   ffplay tcp://192.168.5.10:8554
 */
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>

#include <gst/gst.h>
#include <gst/app/gstappsrc.h>
#include <gst/app/gstappsink.h>

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#include <cstring>
#include <vector>
#include <mutex>
#include <thread>
#include <atomic>

// ═══════════════════════════════════════
// TCP 广播
// ═══════════════════════════════════════
class TcpBroadcaster {
    int                    fd_  = -1;
    std::atomic<bool>      run_{true};
    std::thread            thr_;
    std::mutex             mtx_;
    std::vector<int>       clients_;

public:
    TcpBroadcaster(int port) {
        fd_ = socket(AF_INET, SOCK_STREAM, 0);
        int one = 1;
        setsockopt(fd_, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

        sockaddr_in a{};
        a.sin_family = AF_INET;
        a.sin_addr.s_addr = INADDR_ANY;
        a.sin_port = htons(port);
        if (bind(fd_, (sockaddr*)&a, sizeof(a)) < 0) { perror("bind"); return; }
        listen(fd_, 5);
        fcntl(fd_, F_SETFL, O_NONBLOCK);

        thr_ = std::thread([this] {
            while (run_) {
                int c = accept(fd_, nullptr, nullptr);
                if (c >= 0) {
                    fcntl(c, F_SETFL, O_NONBLOCK);
                    std::lock_guard lk(mtx_);
                    clients_.push_back(c);
                    fprintf(stderr, "[TCP] +client (%zu)\n", clients_.size());
                }
                usleep(100000);
            }
        });
        fprintf(stderr, "[TCP] :%d ready\n", port);
    }

    ~TcpBroadcaster() {
        run_ = false;
        if (thr_.joinable()) thr_.join();
        if (fd_ >= 0) close(fd_);
        for (int c : clients_) close(c);
    }

    void broadcast(const void *p, size_t n) {
        std::lock_guard lk(mtx_);
        for (auto it = clients_.begin(); it != clients_.end(); ) {
            if (::send(*it, p, n, MSG_NOSIGNAL) < 0 && (errno == EPIPE || errno == ECONNRESET)) {
                close(*it); it = clients_.erase(it);
            } else { ++it; }
        }
    }
};

// ═══════════════════════════════════════
// ROS2 节点
// ═══════════════════════════════════════
class StreamNode : public rclcpp::Node {
    GstElement           *pipeline_ = nullptr;
    GstElement           *appsrc_   = nullptr;
    GstElement           *appsink_  = nullptr;
    guint64               pts_      = 0;
    int64_t               n_        = 0;
    rclcpp::Time          t_{0, 0, RCL_ROS_TIME};
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
    std::unique_ptr<TcpBroadcaster> tcp_;

    static GstFlowReturn on_h264(GstElement *, gpointer self_ptr) {
        auto *s = static_cast<StreamNode*>(self_ptr);
        GstSample *sample = gst_app_sink_pull_sample(GST_APP_SINK(s->appsink_));
        if (!sample) return GST_FLOW_OK;

        GstBuffer *buf = gst_sample_get_buffer(sample);
        GstMapInfo map;
        if (buf && gst_buffer_map(buf, &map, GST_MAP_READ)) {
            s->tcp_->broadcast(map.data, map.size);
            gst_buffer_unmap(buf, &map);
        }
        gst_sample_unref(sample);
        return GST_FLOW_OK;
    }

    void frame_cb(const sensor_msgs::msg::Image::SharedPtr msg) {
        n_++;
        if (n_ % 4 != 0) return;
        auto now = this->now();
        if ((now - t_).seconds() < 0.060) return;
        t_ = now;

        auto *holder = new std::shared_ptr<sensor_msgs::msg::Image>(msg);
        GstBuffer *b = gst_buffer_new_wrapped_full(
            GST_MEMORY_FLAG_NO_SHARE,
            (gpointer)msg->data.data(), msg->data.size(),
            0, msg->data.size(), holder,
            [](gpointer p) { delete static_cast<std::shared_ptr<sensor_msgs::msg::Image>*>(p); });
        if (!b) return;

        pts_++;
        GST_BUFFER_PTS(b)      = pts_ * (GST_SECOND / 15);
        GST_BUFFER_DURATION(b) = GST_SECOND / 15;
        GstFlowReturn r;
        g_signal_emit_by_name(appsrc_, "push-buffer", b, &r);
        gst_buffer_unref(b);
        if (r != GST_FLOW_OK && r != GST_FLOW_CUSTOM_SUCCESS && (n_ % 120 == 0)) {
            RCLCPP_WARN(get_logger(), "push-buffer: %s", gst_flow_get_name(r));
        }
    }

public:
    StreamNode() : Node("stream_node"), tcp_(std::make_unique<TcpBroadcaster>(8554))
    {
        pipeline_ = gst_parse_launch(
            "appsrc name=src is-live=true block=false format=GST_FORMAT_TIME "
            " max-bytes=2000000 "
            " caps=video/x-raw,format=BGR,width=424,height=240,framerate=15/1 "
            "! videoconvert ! video/x-raw,format=NV12 "
            "! mpph264enc ! h264parse "
            "! appsink name=sink emit-signals=true max-buffers=1 drop=true", nullptr);
        if (!pipeline_) { RCLCPP_FATAL(get_logger(), "parse failed"); return; }

        appsrc_  = gst_bin_get_by_name(GST_BIN(pipeline_), "src");
        appsink_ = gst_bin_get_by_name(GST_BIN(pipeline_), "sink");
        g_signal_connect(appsink_, "new-sample", G_CALLBACK(&StreamNode::on_h264), this);

        gst_element_set_state(pipeline_, GST_STATE_PLAYING);

        auto q = rclcpp::QoS(rclcpp::SensorDataQoS());
        sub_ = this->create_subscription<sensor_msgs::msg::Image>(
            "/yolo/annotated", q, std::bind(&StreamNode::frame_cb, this, std::placeholders::_1));

        RCLCPP_INFO(get_logger(), "mpph264enc→TCP :8554 ready");
    }

    ~StreamNode() override {
        if (pipeline_) { gst_element_set_state(pipeline_, GST_STATE_NULL); gst_object_unref(pipeline_); }
        if (appsrc_)  gst_object_unref(appsrc_);
        if (appsink_) gst_object_unref(appsink_);
    }
};

int main(int argc, char *argv[]) {
    gst_init(&argc, &argv);
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<StreamNode>());
    rclcpp::shutdown();
    return 0;
}
