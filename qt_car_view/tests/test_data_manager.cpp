#include <gtest/gtest.h>
#include <QVariantMap>
#include "../src/data_manager.h"

TEST(ThresholdCheck, NormalWithinRange)
{
    QVariantMap thresholds = {{"temp_high", 60.0}, {"temp_low", 0.0}};
    QVariantMap data = {{"temp", 26.5}};
    auto alarms = checkThresholds(data, thresholds);
    EXPECT_FALSE(alarms.contains("temp"));
}

TEST(ThresholdCheck, HighAlarm)
{
    QVariantMap thresholds = {{"temp_high", 60.0}};
    QVariantMap data = {{"temp", 75.0}};
    auto alarms = checkThresholds(data, thresholds);
    EXPECT_TRUE(alarms.contains("temp"));
    EXPECT_EQ(alarms["temp"].toStdString(), "high");
}

TEST(ThresholdCheck, LowAlarm)
{
    QVariantMap thresholds = {{"battery_low", 10.5}};
    QVariantMap data = {{"battery", 9.0}};
    auto alarms = checkThresholds(data, thresholds);
    EXPECT_TRUE(alarms.contains("battery"));
    EXPECT_EQ(alarms["battery"].toStdString(), "low");
}

TEST(ThresholdCheck, BoundaryValueNoAlarm)
{
    QVariantMap thresholds = {{"temp_high", 60.0}};
    QVariantMap data = {{"temp", 60.0}};
    auto alarms = checkThresholds(data, thresholds);
    EXPECT_FALSE(alarms.contains("temp"));
}

TEST(ThresholdCheck, PartialDataChecksPresent)
{
    QVariantMap thresholds = {
        {"temp_high", 60.0}, {"temp_low", 0.0},
        {"hum_high", 95.0}
    };
    QVariantMap data = {{"temp", 99.0}};
    auto alarms = checkThresholds(data, thresholds);
    EXPECT_TRUE(alarms.contains("temp"));
    EXPECT_FALSE(alarms.contains("hum"));
}

TEST(TrajectoryCache, AddAndGet)
{
    TrajectoryCache cache;
    cache.add(31.2, 121.4);
    cache.add(31.3, 121.5);
    EXPECT_EQ(cache.size(), 2);
    auto list = cache.toVariantList();
    EXPECT_EQ(list.size(), 2);
    EXPECT_EQ(list[1].toMap()["lat"].toDouble(), 31.3);
}

TEST(TrajectoryCache, FifoEviction)
{
    TrajectoryCache cache;
    cache.maxlen = 3;
    cache.add(1, 1);
    cache.add(2, 2);
    cache.add(3, 3);
    cache.add(4, 4);
    EXPECT_EQ(cache.size(), 3);
    auto list = cache.toVariantList();
    EXPECT_EQ(list[0].toMap()["lat"].toDouble(), 2);
    EXPECT_EQ(list[2].toMap()["lat"].toDouble(), 4);
}

TEST(TrajectoryCache, Clear)
{
    TrajectoryCache cache;
    cache.add(1, 1);
    cache.clear();
    EXPECT_EQ(cache.size(), 0);
}
