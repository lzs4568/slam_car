#include "iotda_api.h"
#include <QNetworkRequest>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QSet>
#include <QDateTime>
#include <QDebug>

IotdaApi::IotdaApi(const QString &iamUser, const QString &iamPass,
                   const QString &domain, const QString &project,
                   const QString &host, const QString &projectId,
                   const QString &deviceId, QObject *parent)
    : QObject(parent), m_iamUser(iamUser), m_iamPass(iamPass),
      m_domain(domain), m_project(project),
      m_host(host), m_projectId(projectId), m_deviceId(deviceId)
{
    m_nam = new QNetworkAccessManager(this);
    connect(&m_timer, &QTimer::timeout, this, &IotdaApi::doFetch);
}

void IotdaApi::start(int intervalMs)
{
    doFetch();
    m_timer.start(intervalMs);
}

void IotdaApi::stop()
{
    m_timer.stop();
}

// ---- IAM Token 获取（缓存 23h）----
void IotdaApi::fetchToken(std::function<void(const QString&)> onSuccess)
{
    if (m_fetchingToken) return;

    // 缓存命中
    if (!m_token.isEmpty() && QDateTime::currentMSecsSinceEpoch() < m_tokenExpire) {
        onSuccess(m_token);
        return;
    }

    m_fetchingToken = true;

    QJsonObject body;
    QJsonObject identity;
    identity["methods"] = QJsonArray{"password"};
    QJsonObject user;
    user["name"] = m_iamUser;
    user["password"] = m_iamPass;
    QJsonObject dom;
    dom["name"] = m_domain;
    user["domain"] = dom;
    QJsonObject password;
    password["user"] = user;
    identity["password"] = password;
    QJsonObject auth;
    auth["identity"] = identity;
    QJsonObject scope;
    QJsonObject projectObj;
    projectObj["name"] = m_project;
    scope["project"] = projectObj;
    auth["scope"] = scope;
    body["auth"] = auth;

    QNetworkRequest req{QUrl("https://iam.myhuaweicloud.com/v3/auth/tokens")};
    req.setRawHeader("Content-Type", "application/json");

    QNetworkReply *reply = m_nam->post(req, QJsonDocument(body).toJson());
    connect(reply, &QNetworkReply::finished, this, [this, reply, onSuccess]() {
        reply->deleteLater();
        m_fetchingToken = false;

        if (reply->error() != QNetworkReply::NoError || reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() != 201) {
            qWarning() << "IAM auth failed:" << reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
            return;
        }

        // Token 在响应头 X-Subject-Token 中
        for (const auto &h : reply->rawHeaderPairs()) {
            if (h.first.toLower() == "x-subject-token") {
                m_token = h.second;
                m_tokenExpire = QDateTime::currentMSecsSinceEpoch() + 23 * 3600 * 1000;
                qDebug() << "IAM token obtained, expires in 23h";
                onSuccess(m_token);
                return;
            }
        }
        qWarning() << "IAM: X-Subject-Token not found in response headers";
    });
}

// ---- 拉取设备影子 + 在线状态 ----
void IotdaApi::doFetch()
{
    fetchToken([this](const QString &token) {
        // --- 1. 设备影子（传感器数据）---
        QString shadowPath = QString("/v5/iot/%1/devices/%2/shadow").arg(m_projectId, m_deviceId);
        QNetworkRequest shadowReq{QUrl(QString("https://%1%2").arg(m_host, shadowPath))};
        shadowReq.setRawHeader("Content-Type", "application/json");
        shadowReq.setRawHeader("X-Auth-Token", token.toUtf8());

        QNetworkReply *shadowReply = m_nam->get(shadowReq);
        connect(shadowReply, &QNetworkReply::finished, this, [this, shadowReply]() {
            shadowReply->deleteLater();
            if (shadowReply->error() != QNetworkReply::NoError) {
                qWarning() << "IoTDA shadow error:" << shadowReply->errorString();
                return;
            }

            QByteArray body = shadowReply->readAll();
            QJsonDocument doc = QJsonDocument::fromJson(body);
            QJsonObject root = doc.object();
            QJsonArray shadowArr = root["shadow"].toArray();

            static const QSet<QString> EXPECTED = {
                "temp", "hum", "mq2_gas_value", "mq135_gas_value", "pm2_5", "battery", "volt",
                "eco2", "tvoc"
            };

            for (const auto &sv : shadowArr) {
                QJsonObject svObj = sv.toObject();
                if (svObj["service_id"].toString() == "car_sensor") {
                    QJsonObject reported = svObj["reported"].toObject();
                    QJsonObject props = reported["properties"].toObject();
                    QVariantMap result;
                    for (auto it = props.begin(); it != props.end(); ++it) {
                        if (EXPECTED.contains(it.key()))
                            result[it.key()] = it.value().toVariant();
                    }
                    if (!result.isEmpty()) {
                        qDebug() << "IoTDA shadow data:" << result;
                        emit sensorDataReady(result);
                    }
                    break;
                }
            }
        });

        // --- 2. 设备在线状态 ---
        QString statusPath = QString("/v5/iot/%1/devices/%2").arg(m_projectId, m_deviceId);
        QNetworkRequest statusReq{QUrl(QString("https://%1%2").arg(m_host, statusPath))};
        statusReq.setRawHeader("Content-Type", "application/json");
        statusReq.setRawHeader("X-Auth-Token", token.toUtf8());

        QNetworkReply *statusReply = m_nam->get(statusReq);
        connect(statusReply, &QNetworkReply::finished, this, [this, statusReply]() {
            statusReply->deleteLater();
            if (statusReply->error() != QNetworkReply::NoError) {
                qWarning() << "IoTDA status error:" << statusReply->errorString();
                return;
            }
            QJsonDocument doc = QJsonDocument::fromJson(statusReply->readAll());
            QString status = doc.object()["status"].toString();
            bool online = (status == "ONLINE");
            qDebug() << "IoTDA device status:" << status;
            emit deviceStatus(online);
        });
    });
}
