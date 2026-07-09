#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H

#include <QObject>
#include <QVariantMap>
#include <memory>
#include <vector>
#include <QTimer>

namespace mqtt {
class async_client;
class callback;
}

class MqttClient : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool connected READ isConnected NOTIFY connectionStatus)

public:
    explicit MqttClient(const QVariantMap &config, QObject *parent = nullptr);
    ~MqttClient() override;

    Q_INVOKABLE void connect();
    Q_INVOKABLE void disconnect();
    bool isConnected() const { return m_connected; }

signals:
    void sensorDataReady(const QVariantMap &data);
    void connectionStatus(bool connected);
    void deviceOnline(bool online);
    void errorMessage(const QString &msg);

private:
    void doConnect();
    void buildAuth();
    void scheduleReconnect();

    QVariantMap m_config;
    std::shared_ptr<mqtt::async_client> m_client;
    QString m_username;
    QString m_password;
    bool m_connected = false;
    bool m_disconnecting = false;
    int m_reconnectAttempt = 0;
    QTimer m_reconnectTimer;
    static const inline std::vector<int> RECONNECT_DELAYS = {1, 2, 4, 8, 16, 30};
};

// Utility functions (pure, no Qt dependency for testing)
QString huaweiAppUsername(const QString &accessKey,
                          const QString &instanceId = "",
                          qint64 tsMs = 0);
QString huaweiDevicePassword(const QString &deviceSecret, QString &timestampOut);
QVariantMap parseSensorMessage(const QString &payload);

#endif // MQTT_CLIENT_H
