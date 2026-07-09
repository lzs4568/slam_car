#ifndef IOTDA_API_H
#define IOTDA_API_H

#include <QObject>
#include <QNetworkAccessManager>
#include <QTimer>

class IotdaApi : public QObject
{
    Q_OBJECT

public:
    IotdaApi(const QString &iamUser, const QString &iamPass,
             const QString &domain, const QString &project,
             const QString &host, const QString &projectId,
             const QString &deviceId,
             QObject *parent = nullptr);

    void start(int intervalMs = 5000);
    void stop();

signals:
    void sensorDataReady(const QVariantMap &data);
    void deviceStatus(bool online);
    void httpError(const QString &msg);

private:
    void doFetch();
    void fetchToken(std::function<void(const QString&)> onSuccess);

    QNetworkAccessManager *m_nam;
    QString m_iamUser, m_iamPass, m_domain, m_project;
    QString m_host, m_projectId, m_deviceId;
    QString m_token;
    qint64 m_tokenExpire = 0;
    QTimer m_timer;
    bool m_fetchingToken = false;
};

#endif
