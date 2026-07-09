#include <QApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QPalette>
#include <QDebug>
#include <QtWebEngine>

#include "data_manager.h"
#include "mqtt_client.h"
#include "settings_manager.h"
#include "js_bridge.h"
#include "iotda_api.h"
#ifdef HAS_ROS2
#include "ros2_bridge.h"
#endif

int main(int argc, char *argv[])
{
    QCoreApplication::setAttribute(Qt::AA_ShareOpenGLContexts);
    QtWebEngine::initialize();

    QApplication app(argc, argv);
    app.setApplicationName("car_view");
    app.setOrganizationName("car_view");

    // Dark palette
    QPalette p;
    p.setColor(QPalette::Window, QColor(0x1E, 0x1E, 0x1E));
    p.setColor(QPalette::WindowText, QColor(0xCC, 0xCC, 0xCC));
    p.setColor(QPalette::Base, QColor(0x25, 0x25, 0x25));
    p.setColor(QPalette::Text, QColor(0xDD, 0xDD, 0xDD));
    p.setColor(QPalette::Button, QColor(0x33, 0x33, 0x33));
    p.setColor(QPalette::ButtonText, QColor(0xDD, 0xDD, 0xDD));
    p.setColor(QPalette::Highlight, QColor(0x2E, 0x59, 0x84));
    p.setColor(QPalette::HighlightedText, QColor(0xFF, 0xFF, 0xFF));
    app.setPalette(p);

    qDebug() << "Starting car_view...";

    QQmlApplicationEngine engine;

    SettingsManager settings;
    QVariantMap thresholds = settings.loadThresholds();
    DataManager dataMgr(thresholds);
    QVariantMap connCfg = settings.loadConnectionConfig();
    MqttClient mqtt(connCfg);

    QString iamUser = connCfg.value("iam_user", "").toString();
    QString iamPass = connCfg.value("iam_pass", "").toString();
    QString iamDomain = connCfg.value("iam_domain", "").toString();
    QString iamProject = connCfg.value("iam_project", "cn-east-3").toString();
    QString iotdaHost = connCfg.value("iotda_api_host", "").toString();
    QString iotdaProjectId = connCfg.value("iotda_project_id", "").toString();
    QString iotdaDeviceId = connCfg.value("iotda_device_id", "").toString();
    IotdaApi iotda(iamUser, iamPass, iamDomain, iamProject, iotdaHost, iotdaProjectId, iotdaDeviceId);

#ifdef HAS_ROS2
    QString gpsTopic = connCfg.value("ros2_gps_topic", "/gps/fix").toString();
    QString waypointTopic = connCfg.value("ros2_waypoint_topic", "/gps_waypoint").toString();
    Ros2Bridge ros2(gpsTopic, waypointTopic);
#endif

    JsBridge jsBridge(connCfg.value("amap_api_key").toString());

    QObject::connect(&mqtt, &MqttClient::sensorDataReady, &dataMgr, &DataManager::onSensorData);
    QObject::connect(&iotda, &IotdaApi::sensorDataReady, &dataMgr, &DataManager::onSensorData);

#ifdef HAS_ROS2
    QObject::connect(&ros2, &Ros2Bridge::gpsPosition, &dataMgr, &DataManager::onGpsPosition);
    QObject::connect(&ros2, &Ros2Bridge::placesList, &dataMgr, &DataManager::onPlacesList);
    QObject::connect(&dataMgr, &DataManager::waypointPublish, &ros2, &Ros2Bridge::publishWaypoint);
#endif

    QObject::connect(&jsBridge, &JsBridge::waypointClicked, &dataMgr, &DataManager::onWaypointSelected);

    QQmlContext *ctx = engine.rootContext();
    ctx->setContextProperty("dataManager", &dataMgr);
    ctx->setContextProperty("mqttClient", &mqtt);
    ctx->setContextProperty("settingsManager", &settings);
    ctx->setContextProperty("jsBridge", &jsBridge);
#ifdef HAS_ROS2
    ctx->setContextProperty("ros2Bridge", &ros2);
    engine.addImageProvider("yolo", new YoloImageProvider(&ros2));
#endif
    ctx->setContextProperty("iotdaApi", &iotda);

    engine.load(QUrl(QStringLiteral("qrc:/qml/MainWindow.qml")));
    if (engine.rootObjects().isEmpty()) {
        qCritical() << "Failed to load QML";
        return -1;
    }

#ifdef HAS_ROS2
    ros2.start();
#endif
    mqtt.connect();
    iotda.start(5000);

    int ret = app.exec();

    mqtt.disconnect();
#ifdef HAS_ROS2
    ros2.stop();
#endif
    return ret;
}
