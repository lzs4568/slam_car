#include "ros2_bridge.h"
#include <QDebug>
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>

// ---- Ros2Bridge (public API) ----

Ros2Bridge::Ros2Bridge(const QString &gpsTopic, const QString &waypointTopic,
                       QObject *parent)
    : QObject(parent)
{
#ifdef HAS_ROS2
    m_thread = new QThread(this);

    m_worker = new Ros2Worker(gpsTopic, waypointTopic, nullptr);
    m_worker->moveToThread(m_thread);

    connect(m_thread, &QThread::started, m_worker, &Ros2Worker::run);
    connect(m_thread, &QThread::finished, m_worker, &QObject::deleteLater);

    connect(m_worker, &Ros2Worker::gpsPosition, this, &Ros2Bridge::gpsPosition);
    connect(m_worker, &Ros2Worker::yoloFrame, this, &Ros2Bridge::yoloFrame);
    connect(m_worker, &Ros2Worker::placesList, this, &Ros2Bridge::placesList);
    connect(m_worker, &Ros2Worker::chatMessage, this, &Ros2Bridge::chatMessage);
    connect(m_worker, &Ros2Worker::rosStatus, this, [this](bool ready) {
        m_ready = ready;
        emit rosStatus(ready);
    });
    connect(m_worker, &Ros2Worker::errorOccurred, this, &Ros2Bridge::errorOccurred);
#else
    Q_UNUSED(gpsTopic)
    Q_UNUSED(waypointTopic)
    qWarning() << "ROS2 not available - bridge disabled";
#endif
}

Ros2Bridge::~Ros2Bridge()
{
    stop();
}

void Ros2Bridge::start()
{
#ifdef HAS_ROS2
    m_thread->start();
#endif
}

void Ros2Bridge::stop()
{
#ifdef HAS_ROS2
    if (m_worker) {
        QMetaObject::invokeMethod(m_worker, "stop", Qt::QueuedConnection);
    }
    if (m_thread) {
        m_thread->quit();
        m_thread->wait(5000);
    }
#endif
}

void Ros2Bridge::publishWaypoint(double lat, double lng, double alt)
{
#ifdef HAS_ROS2
    if (m_worker && m_ready) {
        QMetaObject::invokeMethod(m_worker, "doPublishWaypoint",
                                  Qt::QueuedConnection,
                                  Q_ARG(double, lat),
                                  Q_ARG(double, lng),
                                  Q_ARG(double, alt));
    } else {
        emit errorOccurred("ROS2 未连接，无法发布目标点");
    }
#else
    Q_UNUSED(lat) Q_UNUSED(lng) Q_UNUSED(alt)
    emit errorOccurred("ROS2 不可用");
#endif
}

QImage Ros2Bridge::getYoloFrame() const
{
#ifdef HAS_ROS2
    if (m_worker) return m_worker->getYoloFrame();
#endif
    return QImage();
}

QImage Ros2Worker::getYoloFrame() const
{
    QMutexLocker lock(&m_frameMutex);
    if (m_yoloFrame.isNull()) return QImage();
    return m_yoloFrame.copy();  // 深拷贝 — 避免 QImage 隐式共享竞态段错误
}

void Ros2Bridge::publishAnnotation(const QString &name, double lat, double lng)
{
#ifdef HAS_ROS2
    if (m_worker && m_ready) {
        QMetaObject::invokeMethod(m_worker, "doPublishAnnotation",
                                  Qt::QueuedConnection,
                                  Q_ARG(QString, name),
                                  Q_ARG(double, lat),
                                  Q_ARG(double, lng));
    } else {
        emit errorOccurred("ROS2 未连接，无法发布标注");
    }
#else
    Q_UNUSED(name) Q_UNUSED(lat) Q_UNUSED(lng)
    emit errorOccurred("ROS2 不可用");
#endif
}

void Ros2Bridge::publishCmdVel(double linearX, double angularZ)
{
    qDebug() << "[ROS2] publishCmdVel called: lx=" << linearX << "az=" << angularZ
             << "ready=" << m_ready;
#ifdef HAS_ROS2
    if (m_worker && m_ready) {
        QMetaObject::invokeMethod(m_worker, "doPublishCmdVel",
                                  Qt::QueuedConnection,
                                  Q_ARG(double, linearX),
                                  Q_ARG(double, angularZ));
    } else if (m_worker && !m_ready) {
        qWarning() << "[ROS2] publishCmdVel SKIPPED - ROS not ready yet";
    } else if (!m_worker) {
        qWarning() << "[ROS2] publishCmdVel SKIPPED - no worker";
    }
#else
    Q_UNUSED(linearX) Q_UNUSED(angularZ)
    qWarning() << "[ROS2] publishCmdVel SKIPPED - HAS_ROS2 not defined (stub build)";
#endif
}

void Ros2Bridge::sendChatInput(const QString &text)
{
#ifdef HAS_ROS2
    if (m_worker && m_ready) {
        QMetaObject::invokeMethod(m_worker, "doPublishChatInput",
                                  Qt::QueuedConnection,
                                  Q_ARG(QString, text));
    } else {
        emit errorOccurred("ROS2 未连接，无法发送消息");
    }
#else
    Q_UNUSED(text)
    emit errorOccurred("ROS2 不可用");
#endif
}

// ---- Ros2Node ----

#ifdef HAS_ROS2
Ros2Node::Ros2Node(const std::string &gpsTopic, const std::string &waypointTopic,
                   std::function<void(double,double,double)> gpsCallback)
    : Node("car_view_ros2_bridge"),
      m_gpsCallback(std::move(gpsCallback))
{
    m_sub = this->create_subscription<sensor_msgs::msg::NavSatFix>(
        gpsTopic, 10,
        [this](std::shared_ptr<const sensor_msgs::msg::NavSatFix> msg) {
            if (m_gpsCallback)
                m_gpsCallback(msg->latitude, msg->longitude, msg->altitude);
        });

    m_pub = this->create_publisher<sensor_msgs::msg::NavSatFix>(waypointTopic, 10);

    m_cmdVelPub = this->create_publisher<geometry_msgs::msg::Twist>("/cmd_vel", 10);

    m_annotatePub = this->create_publisher<std_msgs::msg::String>("/annotation/remote", 10);

    m_chatInputPub = this->create_publisher<std_msgs::msg::String>("/voice/chat_input", 10);

    qDebug() << "ROS2 node ready: sub=" << gpsTopic.c_str()
             << "pub=" << waypointTopic.c_str()
             << "cmd_vel=/cmd_vel";
}

void Ros2Node::subscribeYolo(std::function<void(const QImage&)> cb)
{
    m_yoloSub = this->create_subscription<sensor_msgs::msg::Image>(
        "/yolo/jpeg", rclcpp::SensorDataQoS(),
        [cb](std::shared_ptr<const sensor_msgs::msg::Image> msg) {
            if (msg->encoding != "jpeg" || msg->data.empty())
                return;
            QImage img;
            if (img.loadFromData(msg->data.data(), msg->data.size(), "JPEG"))
                cb(img);
        });
}

void Ros2Node::subscribePlaces(std::function<void(const QString&)> cb)
{
    m_placesSub = this->create_subscription<std_msgs::msg::String>(
        "/places/list", 10,
        [cb](std::shared_ptr<const std_msgs::msg::String> msg) {
            cb(QString::fromStdString(msg->data));
        });
}

void Ros2Node::subscribeChat(std::function<void(const QString&, const QString&)> cb)
{
    m_chatSub = this->create_subscription<std_msgs::msg::String>(
        "/voice/chat", 10,
        [cb](std::shared_ptr<const std_msgs::msg::String> msg) {
            QJsonParseError err;
            QJsonDocument doc = QJsonDocument::fromJson(
                QByteArray::fromStdString(msg->data), &err);
            if (err.error != QJsonParseError::NoError || !doc.isObject())
                return;
            QJsonObject obj = doc.object();
            cb(obj.value("role").toString(), obj.value("text").toString());
        });
}

void Ros2Node::publishChatInput(const QString &text)
{
    auto msg = std_msgs::msg::String();
    msg.data = text.toStdString();
    m_chatInputPub->publish(msg);
}

void Ros2Node::publishWaypoint(double lat, double lng, double alt)
{
    auto msg = sensor_msgs::msg::NavSatFix();
    msg.latitude = lat;
    msg.longitude = lng;
    msg.altitude = alt;
    msg.header.stamp = this->get_clock()->now();
    msg.header.frame_id = "map";
    m_pub->publish(msg);
}

void Ros2Node::publishCmdVel(double linearX, double angularZ)
{
    auto msg = geometry_msgs::msg::Twist();
    msg.linear.x = linearX;
    msg.angular.z = angularZ;
    m_cmdVelPub->publish(msg);
    qDebug() << "[ROS2] cmd_vel PUBLISHED: lx=" << linearX << "az=" << angularZ;
}

void Ros2Node::publishAnnotation(const QString &name, double lat, double lng)
{
    auto msg = std_msgs::msg::String();
    QJsonObject obj;
    obj["name"] = name;
    obj["lat"] = lat;
    obj["lng"] = lng;
    msg.data = QJsonDocument(obj).toJson(QJsonDocument::Compact).toStdString();
    m_annotatePub->publish(msg);
    qDebug() << "[ROS2] annotation PUBLISHED:" << name << lat << lng;
}

void Ros2Worker::doPublishAnnotation(const QString &name, double lat, double lng)
{
    if (m_node)
        m_node->publishAnnotation(name, lat, lng);
}

// ---- Ros2Worker ----

Ros2Worker::Ros2Worker(const QString &gpsTopic, const QString &waypointTopic,
                       QObject *parent)
    : QObject(parent),
      m_gpsTopic(gpsTopic),
      m_waypointTopic(waypointTopic)
{
}

Ros2Worker::~Ros2Worker()
{
    stop();
}

void Ros2Worker::run()
{
    try {
        if (!rclcpp::ok())
            rclcpp::init(0, nullptr);

        m_node = std::make_unique<Ros2Node>(
            m_gpsTopic.toStdString(),
            m_waypointTopic.toStdString(),
            [this](double lat, double lng, double alt) {
                emit gpsPosition(lat, lng, alt);
            });

        m_node->subscribeYolo([this](const QImage &img) {
            QMutexLocker lock(&m_frameMutex);
            m_yoloFrame = img;
            emit yoloFrame();
        });

        m_node->subscribePlaces([this](const QString &json) {
            emit placesList(json);
        });

        m_node->subscribeChat([this](const QString &role, const QString &text) {
            emit chatMessage(role, text);
        });

        m_executor = std::make_shared<rclcpp::executors::SingleThreadedExecutor>();
        m_executor->add_node(m_node->get_node_base_interface());
        m_running = true;
        emit rosStatus(true);

        while (m_running && rclcpp::ok()) {
            m_executor->spin_once(std::chrono::milliseconds(10));
            QCoreApplication::processEvents(QEventLoop::AllEvents, 10);
        }
    } catch (const std::exception &e) {
        emit errorOccurred(QString("ROS2 error: %1").arg(e.what()));
    }

    if (m_executor)
        m_executor->cancel();
    if (m_node)
        m_node.reset();
}

void Ros2Worker::stop()
{
    m_running = false;
}

void Ros2Worker::doPublishWaypoint(double lat, double lng, double alt)
{
    if (m_node)
        m_node->publishWaypoint(lat, lng, alt);
}

void Ros2Worker::doPublishCmdVel(double linearX, double angularZ)
{
    if (m_node)
        m_node->publishCmdVel(linearX, angularZ);
}

void Ros2Worker::doPublishChatInput(const QString &text)
{
    if (m_node)
        m_node->publishChatInput(text);
}
// ── YoloImageProvider ──
QImage YoloImageProvider::requestImage(const QString &id, QSize *size, const QSize &requestedSize)
{
    Q_UNUSED(id)
    QImage img = m_bridge->getYoloFrame();
    if (size) *size = img.size();
    if (requestedSize.isValid() && !img.isNull())
        img = img.scaled(requestedSize, Qt::KeepAspectRatio, Qt::FastTransformation);
    return img;
}
#endif // HAS_ROS2
