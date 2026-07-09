#include "js_bridge.h"
#include <QDebug>

JsBridge::JsBridge(const QString &apiKey, QObject *parent)
    : QObject(parent), m_apiKey(apiKey)
{
}

QString JsBridge::getApiKey() const
{
    return m_apiKey;
}

void JsBridge::onMapClick(double lat, double lng)
{
    qDebug() << "Map clicked:" << lat << lng;
    emit waypointClicked(lat, lng);
}

void JsBridge::onMapReady()
{
    emit mapReady();
}

void JsBridge::setApiKey(const QString &key)
{
    m_apiKey = key;
}
