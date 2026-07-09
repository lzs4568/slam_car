#include "settings_manager.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>

SettingsManager::SettingsManager(QObject *parent)
    : QObject(parent)
{
    // Default thresholds (matching config/thresholds_default.json)
    m_defaultThresholds = {
        {"temp_high", 60.0},       {"temp_low", 0.0},
        {"hum_high", 95.0},        {"hum_low", 0.0},
        {"mq2_gas_value_high", 500},
        {"mq135_gas_value_high", 500},
        {"pm2_5_high", 75},
        {"battery_high", 13.0},    {"battery_low", 10.5},
    };

    // Default connection — 上位机 app-side access.
    // 敏感字段留空占位,运行时从 config/connection.json 读取(见 connection.example.json)
    m_defaultConnection = {
        {"mqtt_access_key", ""},        // 华为云 IoTDA app 接入 access key
        {"mqtt_access_code", ""},
        {"mqtt_instance_id", ""},
        {"mqtt_host", ""},              // xxxx.st1.iotda-app.cn-east-3.myhuaweicloud.com
        {"mqtt_port", 8883},
        {"amap_api_key", ""},           // 高德开放平台申请
        {"ros2_gps_topic", "/gps/fix"},
        {"ros2_waypoint_topic", "/gps_waypoint"},
        {"stream_url", "http://192.168.5.10:8082"},
        {"elf_host", "192.168.5.10"},
    };
}

QString SettingsManager::configDir() const
{
    return QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) + "/car_view";
}

QVariantMap SettingsManager::readJson(const QString &filename) const
{
    QFile file(filename);
    if (!file.open(QIODevice::ReadOnly))
        return {};
    QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    return doc.object().toVariantMap();
}

void SettingsManager::writeJson(const QString &filename, const QVariantMap &data) const
{
    QDir().mkpath(QFileInfo(filename).path());
    QFile file(filename);
    file.open(QIODevice::WriteOnly);
    file.write(QJsonDocument(QJsonObject::fromVariantMap(data)).toJson());
}

QVariantMap SettingsManager::loadThresholds() const
{
    QString path = configDir() + "/thresholds.json";
    if (QFile::exists(path))
        return readJson(path);
    return m_defaultThresholds;
}

void SettingsManager::saveThresholds(const QVariantMap &data)
{
    writeJson(configDir() + "/thresholds.json", data);
}

QVariantMap SettingsManager::loadConnectionConfig() const
{
    QString path = configDir() + "/config.json";
    if (QFile::exists(path))
        return readJson(path);
    return m_defaultConnection;
}

void SettingsManager::saveConnectionConfig(const QVariantMap &config)
{
    writeJson(configDir() + "/config.json", config);
    emit configChanged();
}

bool SettingsManager::hasConnectionConfig() const
{
    return QFile::exists(configDir() + "/config.json");
}

QString SettingsManager::amapApiKey() const
{
    QVariantMap cfg = loadConnectionConfig();
    return cfg.value("amap_api_key").toString();
}

QString SettingsManager::ros2GpsTopic() const
{
    QVariantMap cfg = loadConnectionConfig();
    return cfg.value("ros2_gps_topic", "/gps/fix").toString();
}

QString SettingsManager::ros2WaypointTopic() const
{
    QVariantMap cfg = loadConnectionConfig();
    return cfg.value("ros2_waypoint_topic", "/gps_waypoint").toString();
}

QString SettingsManager::streamUrl() const
{
    QVariantMap cfg = loadConnectionConfig();
    return cfg.value("stream_url", "http://192.168.5.10:8082").toString();
}

QString SettingsManager::elfHost() const
{
    QVariantMap cfg = loadConnectionConfig();
    return cfg.value("elf_host", "elf2-desktop.local").toString();
}
