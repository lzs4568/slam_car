#ifndef SETTINGS_MANAGER_H
#define SETTINGS_MANAGER_H

#include <QObject>
#include <QString>
#include <QVariantMap>

class SettingsManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString amapApiKey READ amapApiKey NOTIFY configChanged)
    Q_PROPERTY(QString ros2GpsTopic READ ros2GpsTopic NOTIFY configChanged)
    Q_PROPERTY(QString ros2WaypointTopic READ ros2WaypointTopic NOTIFY configChanged)
    Q_PROPERTY(QString streamUrl READ streamUrl NOTIFY configChanged)
    Q_PROPERTY(QString elfHost READ elfHost NOTIFY configChanged)

public:
    explicit SettingsManager(QObject *parent = nullptr);

    // Thresholds
    QVariantMap loadThresholds() const;
    void saveThresholds(const QVariantMap &data);

    // Connection config
    Q_INVOKABLE QVariantMap loadConnectionConfig() const;
    Q_INVOKABLE void saveConnectionConfig(const QVariantMap &config);
    Q_INVOKABLE bool hasConnectionConfig() const;

    // Single-field accessors for QML binding
    QString amapApiKey() const;
    QString ros2GpsTopic() const;
    QString ros2WaypointTopic() const;
    QString streamUrl() const;
    QString elfHost() const;

signals:
    void configChanged();

private:
    QString configDir() const;
    QVariantMap readJson(const QString &filename) const;
    void writeJson(const QString &filename, const QVariantMap &data) const;

    QVariantMap m_defaultThresholds;
    QVariantMap m_defaultConnection;
};

#endif // SETTINGS_MANAGER_H
