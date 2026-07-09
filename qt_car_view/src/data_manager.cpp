#include "data_manager.h"

// --- TrajectoryCache ---

void TrajectoryCache::add(double lat, double lng)
{
    points.push_back({lat, lng});
    if (points.size() > maxlen)
        points.pop_front();
}

QVariantList TrajectoryCache::toVariantList() const
{
    QVariantList list;
    for (const auto &p : points) {
        QVariantMap pt;
        pt["lat"] = p.first;
        pt["lng"] = p.second;
        list.append(pt);
    }
    return list;
}

void TrajectoryCache::clear() { points.clear(); }
size_t TrajectoryCache::size() const { return points.size(); }

// --- checkThresholds (pure function) ---

QHash<QString, QString> checkThresholds(const QVariantMap &data,
                                         const QVariantMap &thresholds)
{
    QHash<QString, QString> alarms;

    for (auto it = data.begin(); it != data.end(); ++it) {
        const QString &key = it.key();
        double value = it.value().toDouble();

        QString highKey = key + "_high";
        QString lowKey = key + "_low";

        if (thresholds.contains(highKey) && value > thresholds[highKey].toDouble())
            alarms[key] = "high";
        else if (thresholds.contains(lowKey) && value < thresholds[lowKey].toDouble())
            alarms[key] = "low";
    }
    return alarms;
}

// --- DataManager ---

DataManager::DataManager(const QVariantMap &thresholds, QObject *parent)
    : QObject(parent), m_thresholds(thresholds)
{
}

void DataManager::onSensorData(const QVariantMap &data)
{
    m_sensorData = data;

    QHash<QString, QString> alarms = checkThresholds(data, m_thresholds);
    QSet<QString> newAlarms;
    for (auto it = alarms.begin(); it != alarms.end(); ++it)
        newAlarms.insert(it.key());

    // New alarms
    for (const auto &sensor : newAlarms) {
        if (!m_activeAlarms.contains(sensor))
            emit alarmTriggered(sensor, alarms[sensor]);
    }

    // Cleared alarms
    for (const auto &sensor : m_activeAlarms) {
        if (!newAlarms.contains(sensor))
            emit alarmCleared(sensor);
    }

    m_activeAlarms = newAlarms;
    emit sensorDisplay(data);
}

void DataManager::onGpsPosition(double lat, double lng, double alt)
{
    Q_UNUSED(alt)
    if (lat == 0.0 && lng == 0.0)
        return;

    m_latitude = lat;
    m_longitude = lng;
    m_trajectory.add(lat, lng);

    emit gpsDisplay(lat, lng);
    emit trajectoryPoint(lat, lng);
    emit trajectoryChanged();
}

void DataManager::onWaypointSelected(double lat, double lng)
{
    emit waypointMarker(lat, lng);
    emit waypointPublish(lat, lng, 0.0);
    emit statusMessage(QString("目标点已设置: %1, %2")
                       .arg(lat, 0, 'f', 6).arg(lng, 0, 'f', 6));
}

void DataManager::onPlacesList(const QString &json)
{
    emit placesUpdated(json);
}

void DataManager::clearTrajectory()
{
    m_trajectory.clear();
    emit trajectoryClear();
    emit trajectoryChanged();
    emit statusMessage("轨迹已清空");
}

QVariantList DataManager::getTrajectory() const
{
    return m_trajectory.toVariantList();
}

QVariantMap DataManager::getThresholds() const
{
    return m_thresholds;
}

void DataManager::setThresholds(const QVariantMap &data)
{
    for (auto it = data.begin(); it != data.end(); ++it)
        m_thresholds[it.key()] = it.value();
}
