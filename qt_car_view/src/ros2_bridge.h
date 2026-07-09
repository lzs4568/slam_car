#ifndef ROS2_BRIDGE_H
#define ROS2_BRIDGE_H

#include <QObject>
#include <QThread>
#include <QQuickImageProvider>

#ifdef HAS_ROS2
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/nav_sat_fix.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <std_msgs/msg/string.hpp>
#include <QImage>
#include <QMutex>

class Ros2Node : public rclcpp::Node
{
public:
    Ros2Node(const std::string &gpsTopic, const std::string &waypointTopic,
             std::function<void(double,double,double)> gpsCallback);

    void publishWaypoint(double lat, double lng, double alt);
    void publishCmdVel(double linearX, double angularZ);
    void publishAnnotation(const QString &name, double lat, double lng);
    void subscribeYolo(std::function<void(const QImage&)> cb);
    void subscribePlaces(std::function<void(const QString&)> cb);
    void subscribeChat(std::function<void(const QString&, const QString&)> cb);
    void publishChatInput(const QString &text);

private:
    rclcpp::Subscription<sensor_msgs::msg::NavSatFix>::SharedPtr m_sub;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr m_yoloSub;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr m_placesSub;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr m_chatSub;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr m_chatInputPub;
    rclcpp::Publisher<sensor_msgs::msg::NavSatFix>::SharedPtr m_pub;
    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr m_cmdVelPub;
    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr m_annotatePub;
    std::function<void(double,double,double)> m_gpsCallback;
};

class Ros2Worker : public QObject
{
    Q_OBJECT
public:
    Ros2Worker(const QString &gpsTopic, const QString &waypointTopic,
               QObject *parent = nullptr);
    ~Ros2Worker() override;

public slots:
    void run();
    void stop();
    void doPublishWaypoint(double lat, double lng, double alt);
    void doPublishCmdVel(double linearX, double angularZ);
    void doPublishAnnotation(const QString &name, double lat, double lng);
    void doPublishChatInput(const QString &text);

    // YOLO 帧访问 (线程安全)
    QImage getYoloFrame() const;

signals:
    void gpsPosition(double lat, double lng, double alt);
    void yoloFrame();
    void placesList(const QString &json);
    void chatMessage(const QString &role, const QString &text);
    void rosStatus(bool ready);
    void errorOccurred(const QString &msg);

private:
    QString m_gpsTopic;
    QString m_waypointTopic;
    mutable QMutex m_frameMutex;
    QImage m_yoloFrame;
    std::unique_ptr<Ros2Node> m_node;
    rclcpp::executors::SingleThreadedExecutor::SharedPtr m_executor;
    std::atomic<bool> m_running{false};
};
#endif // HAS_ROS2

class Ros2Bridge : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool ready READ isReady NOTIFY rosStatus)

public:
    Ros2Bridge(const QString &gpsTopic, const QString &waypointTopic,
               QObject *parent = nullptr);
    ~Ros2Bridge() override;

    bool isReady() const { return m_ready; }

    Q_INVOKABLE void publishWaypoint(double lat, double lng, double alt);
    Q_INVOKABLE void publishCmdVel(double linearX, double angularZ);
    Q_INVOKABLE void publishAnnotation(const QString &name, double lat, double lng);
    Q_INVOKABLE void sendChatInput(const QString &text);
    Q_INVOKABLE QImage getYoloFrame() const;
    void start();
    void stop();

signals:
    void gpsPosition(double lat, double lng, double alt);
    void yoloFrame();
    void placesList(const QString &json);
    void chatMessage(const QString &role, const QString &text);
    void rosStatus(bool ready);
    void errorOccurred(const QString &msg);

private:
#ifdef HAS_ROS2
    Ros2Worker *m_worker;
    QThread *m_thread;
#endif
    bool m_ready = false;
};

// ── QQuickImageProvider: image://yolo/ → Ros2Bridge::getYoloFrame() ──
class YoloImageProvider : public QQuickImageProvider
{
public:
    explicit YoloImageProvider(Ros2Bridge *bridge)
        : QQuickImageProvider(QQuickImageProvider::Image), m_bridge(bridge) {}

    QImage requestImage(const QString &id, QSize *size, const QSize &requestedSize) override;

private:
    Ros2Bridge *m_bridge;
};

#endif // ROS2_BRIDGE_H
