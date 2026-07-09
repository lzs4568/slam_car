#include <QtTest>
#include <QSignalSpy>
#include <QVariantMap>
#include "../src/data_manager.h"
#include "../src/mqtt_client.h"

class TestSignalChain : public QObject
{
    Q_OBJECT

private slots:
    void testMqttParseToDataManager()
    {
        DataManager dm({{"temp_high", 60.0}, {"temp_low", 0.0}});

        QSignalSpy spyDisplay(&dm, &DataManager::sensorDisplay);

        QString payload = R"({
            "services": [{
                "service_id": "car_sensor",
                "properties": {
                    "temp": 26.5, "hum": 58.2, "mq2_gas_value": 320,
                    "mq135_gas_value": 185, "pm2_5": 15, "battery": 12.4
                }
            }]
        })";

        QVariantMap data = parseSensorMessage(payload);
        QVERIFY(!data.isEmpty());

        dm.onSensorData(data);

        QCOMPARE(spyDisplay.count(), 1);
        QVariantMap emitted = spyDisplay[0][0].toMap();
        QCOMPARE(emitted["temp"].toDouble(), 26.5);
        QCOMPARE(emitted["battery"].toDouble(), 12.4);
    }

    void testThresholdAlarmChain()
    {
        DataManager dm({{"temp_high", 60.0}, {"battery_low", 10.5}});

        QSignalSpy spyAlarm(&dm, &DataManager::alarmTriggered);

        QString payload = R"({
            "services": [{
                "service_id": "car_sensor",
                "properties": {"temp": 99.0, "battery": 8.0}
            }]
        })";

        QVariantMap data = parseSensorMessage(payload);
        dm.onSensorData(data);

        QCOMPARE(spyAlarm.count(), 2);

        QStringList triggeredSensors;
        for (int i = 0; i < spyAlarm.count(); ++i)
            triggeredSensors << spyAlarm[i][0].toString();

        QVERIFY(triggeredSensors.contains("temp"));
        QVERIFY(triggeredSensors.contains("battery"));
    }

    void testGpsToTrajectory()
    {
        DataManager dm({});

        QSignalSpy spyGps(&dm, &DataManager::gpsDisplay);

        dm.onGpsPosition(31.2, 121.4, 10.0);
        dm.onGpsPosition(31.3, 121.5, 10.0);

        QCOMPARE(spyGps.count(), 2);
        QCOMPARE(spyGps[1][0].toDouble(), 31.3);
        QCOMPARE(spyGps[1][1].toDouble(), 121.5);

        QVariantList traj = dm.getTrajectory();
        QCOMPARE(traj.size(), 2);
    }

    void testGpsOriginFiltered()
    {
        DataManager dm({});

        QSignalSpy spyGps(&dm, &DataManager::gpsDisplay);
        dm.onGpsPosition(0.0, 0.0, 0.0);

        QCOMPARE(spyGps.count(), 0);
    }

    void testClearTrajectory()
    {
        DataManager dm({});

        dm.onGpsPosition(31.2, 121.4, 10.0);
        dm.clearTrajectory();

        QCOMPARE(dm.getTrajectory().size(), 0);
    }
};

QTEST_MAIN(TestSignalChain)
#include "test_integration.moc"
