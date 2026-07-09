#ifndef DATA_MANAGER_H
#define DATA_MANAGER_H

#include <QObject>
#include <QVariantMap>
#include <QVariantList>
#include <QHash>
#include <QSet>
#include <deque>
#include <utility>

// ---- Pure data structures ----

struct TrajectoryCache {
    std::deque<std::pair<double,double>> points;
    size_t maxlen = 2000;

    void add(double lat, double lng);
    QVariantList toVariantList() const;
    void clear();
    size_t size() const;
};

QHash<QString, QString> checkThresholds(const QVariantMap &data,
                                         const QVariantMap &thresholds);

// ---- Qt signal hub ----

class DataManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVariantMap sensorData READ sensorData NOTIFY sensorDisplay)
    Q_PROPERTY(double latitude READ latitude NOTIFY gpsDisplay)
    Q_PROPERTY(double longitude READ longitude NOTIFY gpsDisplay)

public:
    explicit DataManager(const QVariantMap &thresholds, QObject *parent = nullptr);

    QVariantMap sensorData() const { return m_sensorData; }
    double latitude() const { return m_latitude; }
    double longitude() const { return m_longitude; }

public slots:
    void onSensorData(const QVariantMap &data);
    void onGpsPosition(double lat, double lng, double alt);
    void onWaypointSelected(double lat, double lng);
    void onPlacesList(const QString &json);
    void clearTrajectory();

signals:
    void sensorDisplay(const QVariantMap &data);
    void gpsDisplay(double lat, double lng);
    void trajectoryPoint(double lat, double lng);
    void trajectoryClear();
    void alarmTriggered(const QString &sensor, const QString &direction);
    void alarmCleared(const QString &sensor);
    void waypointPublish(double lat, double lng, double alt);
    void waypointMarker(double lat, double lng);
    void placesUpdated(const QString &json);
    void statusMessage(const QString &msg);

    // QML helper signals for trajectory replay
    void trajectoryChanged();

public:
    Q_INVOKABLE QVariantList getTrajectory() const;
    Q_INVOKABLE QVariantMap getThresholds() const;
    Q_INVOKABLE void setThresholds(const QVariantMap &data);

private:
    QVariantMap m_thresholds;
    TrajectoryCache m_trajectory;
    QSet<QString> m_activeAlarms;
    QVariantMap m_sensorData;
    double m_latitude = 0.0;
    double m_longitude = 0.0;
};

#endif // DATA_MANAGER_H
