#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <mutex>
#include <thread>
#include <string>

static std::atomic<bool> g_running{true};

#include "slam_car_yolo/yolo_engine.hpp"

using namespace std::chrono_literals;

class YoloNode : public rclcpp::Node {
public:
    YoloNode() : Node("yolo_node"), running_(false) {
        // ---- 声明参数 ----
        this->declare_parameter("model_path",
            "/data/yolov8/car.rknn");
        this->declare_parameter("labels_path",
            "/data/yolov8/labels_list.txt");
        this->declare_parameter("camera_topic", "/camera/color/image_raw");
        this->declare_parameter("conf_threshold", 0.25);
        this->declare_parameter("nms_threshold", 0.45);
        this->declare_parameter("core_mask", 1);

        // ---- 获取参数 ----
        std::string model_path  = this->get_parameter("model_path").as_string();
        std::string labels_path  = this->get_parameter("labels_path").as_string();
        std::string camera_topic = this->get_parameter("camera_topic").as_string();
        float conf_threshold     = this->get_parameter("conf_threshold").as_double();
        float nms_threshold      = this->get_parameter("nms_threshold").as_double();
        int core_mask            = this->get_parameter("core_mask").as_int();

        RCLCPP_INFO(this->get_logger(),
                    "YOLO Node starting...");
        RCLCPP_INFO(this->get_logger(),
                    "  model:  %s", model_path.c_str());
        RCLCPP_INFO(this->get_logger(),
                    "  labels: %s", labels_path.c_str());
        RCLCPP_INFO(this->get_logger(),
                    "  camera: %s", camera_topic.c_str());
        RCLCPP_INFO(this->get_logger(),
                    "  conf=%.2f  nms=%.2f  core_mask=%d",
                    conf_threshold, nms_threshold, core_mask);

        // ---- 初始化 YOLO 引擎 ----
        engine_ = std::make_unique<slam_car_yolo::YoloEngine>();
        if (!engine_->init(model_path, labels_path, core_mask)) {
            RCLCPP_FATAL(this->get_logger(), "YOLO engine init FAILED");
            engine_failed_ = true;
            return;
        }
        engine_->setConfThreshold(conf_threshold);
        engine_->setNmsThreshold(nms_threshold);

        // ---- 订阅相机 ----
        auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).best_effort();
        sub_ = this->create_subscription<sensor_msgs::msg::Image>(
            camera_topic, qos,
            std::bind(&YoloNode::imageCallback, this, std::placeholders::_1));

        // ---- 发布标注图像 ----
        annotated_pub_ = this->create_publisher<sensor_msgs::msg::Image>(
            "/yolo/annotated", 10);

        // ---- 发布 JPEG (QT前端) ----
        jpeg_pub_ = this->create_publisher<sensor_msgs::msg::Image>(
            "/yolo/jpeg", 10);

        // ---- 启动推理线程 ----
        if (!engine_failed_) {
            running_ = true;
            inference_thread_ = std::thread(&YoloNode::inferenceLoop, this);
        }

        RCLCPP_INFO(this->get_logger(),
                    engine_failed_ ? "YOLO Node started (NO ENGINE - node will idle)"
                                   : "YOLO Node READY");
    }

    ~YoloNode() override {
        running_ = false;
        cv_.notify_all();
        if (inference_thread_.joinable()) {
            inference_thread_.join();
        }
        RCLCPP_INFO(this->get_logger(), "YOLO Node shutdown");
    }

private:
    // ============================================================
    // 拉模式：回调只存最新帧，推理线程取走
    // ============================================================

    void imageCallback(const sensor_msgs::msg::Image::SharedPtr msg) {
        try {
            auto cv_ptr = cv_bridge::toCvCopy(msg, "bgr8");
            {
                std::lock_guard<std::mutex> lock(mutex_);
                latest_frame_ = cv_ptr->image;
                latest_header_ = msg->header;
                has_frame_ = true;
            }
            cv_.notify_one();
        } catch (const cv_bridge::Exception &e) {
            RCLCPP_ERROR(this->get_logger(), "cv_bridge: %s", e.what());
        }
    }

    void inferenceLoop() {
        double fps_ema = 0.0;

        while (rclcpp::ok() && running_) {
            cv::Mat frame;
            std_msgs::msg::Header header;

            // ---- 等待新帧（100ms 超时）----
            {
                std::unique_lock<std::mutex> lock(mutex_);
                cv_.wait_for(lock, 100ms, [this] { return has_frame_; });
                if (!has_frame_) continue;
                frame = latest_frame_.clone();
                header = latest_header_;
            }

            // ---- 推理 ----
            auto t0 = std::chrono::steady_clock::now();
            std::vector<slam_car_yolo::Detection> detections;
            engine_->infer(frame, detections, /*draw=*/true);

            // ---- FPS 统计 (EMA) ----
            auto t1 = std::chrono::steady_clock::now();
            double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
            double inst_fps = ms > 0.0 ? 1000.0 / ms : 0.0;
            if (fps_ema <= 0.0) fps_ema = inst_fps;
            else                fps_ema = fps_ema * 0.9 + inst_fps * 0.1;

            // ---- 叠加 HUD ----
            char hud[64];
            snprintf(hud, sizeof(hud), "YOLO  NPU FPS: %.1f  Det: %zu",
                     fps_ema, detections.size());
            // 黑色描边
            cv::putText(frame, hud, cv::Point(12, 34),
                        cv::FONT_HERSHEY_SIMPLEX, 0.8,
                        cv::Scalar(0, 0, 0), 4);
            // 绿色文字
            cv::putText(frame, hud, cv::Point(12, 34),
                        cv::FONT_HERSHEY_SIMPLEX, 0.8,
                        cv::Scalar(0, 255, 0), 2);

            // ---- 发布 bgr8 ----
            auto msg = cv_bridge::CvImage(header, "bgr8", frame).toImageMsg();
            annotated_pub_->publish(*msg);

            // ---- 发布 jpeg (QT DDS) ----
            std::vector<uchar> jpg;
            cv::imencode(".jpg", frame, jpg, {cv::IMWRITE_JPEG_QUALITY, 85});
            auto jpeg_msg = std::make_unique<sensor_msgs::msg::Image>();
            jpeg_msg->header = header;
            jpeg_msg->height = frame.rows;
            jpeg_msg->width = frame.cols;
            jpeg_msg->encoding = "jpeg";
            jpeg_msg->step = jpg.size();
            jpeg_msg->data = std::move(jpg);
            jpeg_pub_->publish(std::move(jpeg_msg));

            // 每 120 帧打印一次
            static int frame_cnt = 0;
            frame_cnt++;
            if (frame_cnt % 120 == 0) {
                RCLCPP_INFO(this->get_logger(),
                            "Frame %d  FPS: %.1f  Detections: %zu",
                            frame_cnt, fps_ema, detections.size());
            }
        }
    }

    // ============================================================
    // 成员
    // ============================================================

    std::unique_ptr<slam_car_yolo::YoloEngine> engine_;
    bool engine_failed_{false};

    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr annotated_pub_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr jpeg_pub_;

    std::atomic<bool> running_;
    std::thread inference_thread_;

    std::mutex mutex_;
    std::condition_variable cv_;
    cv::Mat latest_frame_;
    std_msgs::msg::Header latest_header_;
    bool has_frame_{false};
};

int main(int argc, char *argv[]) {
    signal(SIGINT, [](int) { g_running = false; });
    signal(SIGTERM, [](int) { g_running = false; });

    rclcpp::init(argc, argv);
    auto node = std::make_shared<YoloNode>();
    rclcpp::executors::SingleThreadedExecutor exec;
    exec.add_node(node);

    while (g_running && rclcpp::ok()) {
        exec.spin_once(100ms);
    }

    exec.remove_node(node);
    node.reset();
    rclcpp::shutdown();
    return 0;
}
