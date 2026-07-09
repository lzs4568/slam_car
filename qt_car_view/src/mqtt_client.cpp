#include "mqtt_client.h"
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDateTime>
#include <QCryptographicHash>
#include <QMessageAuthenticationCode>
#include <QRandomGenerator>
#include <QSet>
#include <QDebug>

#include <mqtt/async_client.h>

// ---- Utility functions ----

QString huaweiAppUsername(const QString &accessKey,
                          const QString &instanceId, qint64 tsMs)
{
    if (tsMs == 0)
        tsMs = QDateTime::currentMSecsSinceEpoch();
    QString username = QString("accessKey=%1|timestamp=%2").arg(accessKey).arg(tsMs);
    if (!instanceId.isEmpty())
        username += QString("|instanceId=%1").arg(instanceId);
    return username;
}

QString huaweiDevicePassword(const QString &deviceSecret, QString &timestampOut)
{
    QDateTime beijing = QDateTime::currentDateTimeUtc().addSecs(8 * 3600);
    timestampOut = beijing.toString("yyyyMMddHH");

    QMessageAuthenticationCode mac(QCryptographicHash::Sha256);
    mac.setKey(deviceSecret.toUtf8());
    mac.addData(timestampOut.toUtf8());
    return mac.result().toHex();
}

// IAM AK/SK HMAC 签名密码（应用侧 MQTT 接入）
QString huaweiIamPassword(const QString &secretKey, const QString &timestampMs)
{
    QMessageAuthenticationCode mac(QCryptographicHash::Sha256);
    mac.setKey(secretKey.toUtf8());
    mac.addData(timestampMs.toUtf8());
    return mac.result().toHex();
}

QVariantMap parseSensorMessage(const QString &payload)
{
    QJsonParseError err;
    QJsonDocument doc = QJsonDocument::fromJson(payload.toUtf8(), &err);
    if (err.error != QJsonParseError::NoError)
        return {};

    QJsonObject root = doc.object();
    QJsonArray services = root["services"].toArray();
    if (services.isEmpty())
        return {};

    static const QSet<QString> EXPECTED = {
        "temp", "hum", "mq2_gas_value", "mq135_gas_value", "pm2_5", "battery", "volt",
        "eco2", "tvoc"
    };

    for (const auto &svc : services) {
        QJsonObject svcObj = svc.toObject();
        if (svcObj["service_id"].toString() == "car_sensor") {
            QJsonObject props = svcObj["properties"].toObject();
            QVariantMap result;
            for (auto it = props.begin(); it != props.end(); ++it) {
                if (EXPECTED.contains(it.key()))
                    result[it.key()] = it.value().toVariant();
            }
            return result;
        }
    }
    return {};
}

// ---- MqttClient ----

MqttClient::MqttClient(const QVariantMap &config, QObject *parent)
    : QObject(parent), m_config(config)
{
    m_reconnectTimer.setSingleShot(true);
    QObject::connect(&m_reconnectTimer, &QTimer::timeout, this, &MqttClient::doConnect);
}

MqttClient::~MqttClient()
{
    disconnect();
}

void MqttClient::buildAuth()
{
    QString accessKey = m_config.value("mqtt_access_key").toString();
    QString accessCode = m_config.value("mqtt_access_code").toString();
    QString instanceId = m_config.value("mqtt_instance_id").toString();
    QString username = m_config.value("mqtt_username").toString();
    QString password = m_config.value("mqtt_password").toString();

    // 应用侧接入
    if (!accessKey.isEmpty() && !accessCode.isEmpty()) {
        qint64 tsMs = QDateTime::currentMSecsSinceEpoch();
        m_username = huaweiAppUsername(accessKey, instanceId, tsMs);
        m_password = accessCode;
        return;
    }
    // 自定义用户名密码
    m_username = username;
    m_password = password;
}

void MqttClient::connect()
{
    m_disconnecting = false;
    m_reconnectAttempt = 0;
    doConnect();
}

void MqttClient::doConnect()
{
    try {
        buildAuth();

        QString host = m_config.value("mqtt_host").toString();
        int port = m_config.value("mqtt_port", 8883).toInt();
        QString brokerUri = QString("ssl://%1:%2").arg(host).arg(port);

        QString suffix;
        for (int i = 0; i < 8; ++i)
            suffix.append(QChar('a' + QRandomGenerator::global()->bounded(26)));
        QString clientId = QString("car_view_%1").arg(suffix);

        m_client = std::make_shared<mqtt::async_client>(brokerUri.toStdString(),
                                                         clientId.toStdString());

        // Only use set_message_callback (don't set set_callback)
        m_client->set_message_callback([this](mqtt::const_message_ptr msg) {
            QString topic = QString::fromStdString(msg->get_topic());
            QString qPayload = QString::fromStdString(msg->get_payload_str());

            qDebug() << "MQTT rx topic:" << topic;
            qDebug() << "MQTT rx payload:" << qPayload.left(200);

            // 设备上下线检测
            if (topic.contains("/status/up") || topic.contains("/events/up")) {
                emit deviceOnline(true);
                qDebug() << "MQTT device ONLINE";
            } else if (topic.contains("/status/down") || topic.contains("/events/down")) {
                emit deviceOnline(false);
                qDebug() << "MQTT device OFFLINE";
            }

            QVariantMap data = parseSensorMessage(qPayload);
            if (!data.isEmpty()) {
                qDebug() << "MQTT parsed sensor data:" << data;
                emit sensorDataReady(data);
            }
        });

        mqtt::connect_options opts;
        opts.set_user_name(m_username.toStdString());
        opts.set_password(m_password.toStdString());
        opts.set_keep_alive_interval(60);
        opts.set_clean_session(true);

        mqtt::ssl_options sslOpts;
        sslOpts.set_verify(false);
        opts.set_ssl(sslOpts);

        qDebug() << "MQTT connecting to" << host << ":" << port
                 << "user=" << m_username.left(60);

        auto token = m_client->connect(opts);
        bool ok = token->wait_for(std::chrono::seconds(10));

        if (ok) {
            m_connected = true;
            m_reconnectAttempt = 0;
            qDebug() << "MQTT connected";
            emit connectionStatus(true);

            // 应用侧 MQTT 不支持订阅设备 topic，仅用 HTTPS 拉数据
        } else {
            qWarning() << "MQTT connect timeout after 10s";
            emit connectionStatus(false);
            emit errorMessage("MQTT连接超时");
            scheduleReconnect();
        }
    } catch (const mqtt::exception &e) {
        m_connected = false;
        qWarning() << "MQTT connect failed:" << e.what();
        emit connectionStatus(false);
        emit errorMessage(QString("MQTT: %1").arg(e.what()));
        scheduleReconnect();
    }
}

void MqttClient::scheduleReconnect()
{
    if (m_disconnecting) return;
    int idx = std::min(m_reconnectAttempt, (int)RECONNECT_DELAYS.size() - 1);
    int delay = RECONNECT_DELAYS[idx] * 1000;
    m_reconnectAttempt++;
    qDebug() << "MQTT retry in" << delay / 1000 << "s (attempt" << m_reconnectAttempt << ")";
    m_reconnectTimer.start(delay);
}

void MqttClient::disconnect()
{
    m_disconnecting = true;
    m_reconnectTimer.stop();
    if (m_client) {
        try {
            m_client->disconnect()->wait_for(3000);
        } catch (...) {}
        m_client.reset();
    }
    m_connected = false;
    emit connectionStatus(false);
    qDebug() << "MQTT disconnected";
}
