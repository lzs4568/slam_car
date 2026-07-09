#ifndef JS_BRIDGE_H
#define JS_BRIDGE_H

#include <QObject>
#include <QString>
#include <QVariantList>

class JsBridge : public QObject
{
    Q_OBJECT

public:
    explicit JsBridge(const QString &apiKey, QObject *parent = nullptr);

    Q_INVOKABLE QString getApiKey() const;
    Q_INVOKABLE void onMapClick(double lat, double lng);
    Q_INVOKABLE void onMapReady();

    void setApiKey(const QString &key);

signals:
    void waypointClicked(double lat, double lng);
    void mapReady();

private:
    QString m_apiKey;
};

#endif // JS_BRIDGE_H
