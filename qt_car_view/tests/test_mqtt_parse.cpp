#include <gtest/gtest.h>
#include <QVariantMap>
#include "../src/mqtt_client.h"

TEST(MqttParse, ValidHuaweiMessage)
{
    QString payload = R"({
        "services": [{
            "service_id": "car_sensor",
            "properties": {
                "temp": 26.5, "hum": 58.2, "mq2_gas_value": 320,
                "mq135_gas_value": 185, "pm2_5": 15, "battery": 12.4
            }
        }]
    })";
    auto result = parseSensorMessage(payload);
    EXPECT_FALSE(result.isEmpty());
    EXPECT_DOUBLE_EQ(result["temp"].toDouble(), 26.5);
    EXPECT_DOUBLE_EQ(result["battery"].toDouble(), 12.4);
}

TEST(MqttParse, WrongServiceIdIgnored)
{
    QString payload = R"({"services":[{"service_id":"other","properties":{"temp":99}}]})";
    auto result = parseSensorMessage(payload);
    EXPECT_TRUE(result.isEmpty());
}

TEST(MqttParse, InvalidJsonReturnsEmpty)
{
    auto result = parseSensorMessage("not json{{{");
    EXPECT_TRUE(result.isEmpty());
}

TEST(MqttParse, PartialProperties)
{
    QString payload = R"({"services":[{"service_id":"car_sensor","properties":{"temp":30,"battery":11.5}}]})";
    auto result = parseSensorMessage(payload);
    EXPECT_EQ(result.size(), 2);
    EXPECT_TRUE(result.contains("temp"));
    EXPECT_FALSE(result.contains("hum"));
}

TEST(HuaweiAuth, AppUsernameFormat)
{
    QString u = huaweiAppUsername("key123", "", 1700000000000LL);
    EXPECT_TRUE(u.contains("accessKey=key123"));
    EXPECT_TRUE(u.contains("timestamp=1700000000000"));
}

TEST(HuaweiAuth, AppUsernameWithInstanceId)
{
    QString u = huaweiAppUsername("key", "inst456", 1700000000000LL);
    EXPECT_TRUE(u.contains("instanceId=inst456"));
}

TEST(HuaweiAuth, DevicePasswordIs64CharHex)
{
    QString ts;
    QString pwd = huaweiDevicePassword("secret123", ts);
    EXPECT_EQ(pwd.size(), 64);
    EXPECT_EQ(ts.size(), 10); // YYYYMMDDHH
}

TEST(MqttParse, IncludesEco2AndTvoc)
{
    QString payload = R"({"services":[{"service_id":"car_sensor","properties":{"eco2":412,"tvoc":58,"temp":25}}]})";
    auto result = parseSensorMessage(payload);
    EXPECT_TRUE(result.contains("eco2"));
    EXPECT_TRUE(result.contains("tvoc"));
    EXPECT_EQ(result["eco2"].toInt(), 412);
    EXPECT_EQ(result["tvoc"].toInt(), 58);
}
