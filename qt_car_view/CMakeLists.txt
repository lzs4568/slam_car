cmake_minimum_required(VERSION 3.16)
project(car_view VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

# Qt5 (WebEngine requires QApplication, provided by Widgets)
find_package(Qt5 REQUIRED COMPONENTS Qml Quick WebEngine WebChannel Core Widgets Network Multimedia MultimediaWidgets)

# paho-mqtt (either system or FetchContent)
find_package(paho-mqtt-cpp QUIET)
if(NOT paho-mqtt-cpp_FOUND)
  include(FetchContent)
  set(PAHO_WITH_SSL TRUE CACHE BOOL "Enable SSL support" FORCE)
  find_package(OpenSSL REQUIRED)
  FetchContent_Declare(
    paho-mqtt-c
    URL https://github.com/eclipse/paho.mqtt.c/archive/refs/tags/v1.3.13.tar.gz
  )
  FetchContent_MakeAvailable(paho-mqtt-c)

  FetchContent_Declare(
    paho-mqtt-cpp
    URL https://github.com/eclipse/paho.mqtt.cpp/archive/refs/tags/v1.4.0.tar.gz
  )
  FetchContent_MakeAvailable(paho-mqtt-cpp)
endif()

# rclcpp (optional, find if ROS2 sourced)
find_package(rclcpp QUIET)
find_package(sensor_msgs QUIET)
find_package(geometry_msgs QUIET)
if(rclcpp_FOUND AND sensor_msgs_FOUND AND geometry_msgs_FOUND)
  set(HAS_ROS2 TRUE)
  add_compile_definitions(HAS_ROS2)
endif()

# Source files
set(SOURCES
  src/main.cpp
  src/data_manager.cpp
  src/mqtt_client.cpp
  src/settings_manager.cpp
  src/js_bridge.cpp
  src/iotda_api.cpp
)

if(HAS_ROS2)
  list(APPEND SOURCES src/ros2_bridge.cpp)
endif()

# Qt resource file (qml + web + config)
set(RESOURCE_FILE resources.qrc)

# Main executable
add_executable(car_view ${SOURCES} ${RESOURCE_FILE})

target_link_libraries(car_view PRIVATE
  Qt5::Qml Qt5::Quick Qt5::WebEngine Qt5::WebChannel Qt5::Core Qt5::Widgets Qt5::Network Qt5::Multimedia Qt5::MultimediaWidgets
  paho-mqttpp3
)
if(HAS_ROS2)
  target_link_libraries(car_view PRIVATE ${rclcpp_LIBRARIES} ${sensor_msgs_LIBRARIES} ${geometry_msgs_LIBRARIES})
  target_include_directories(car_view PRIVATE ${rclcpp_INCLUDE_DIRS} ${sensor_msgs_INCLUDE_DIRS} ${geometry_msgs_INCLUDE_DIRS})
endif()

# Tests (GoogleTest fetched optionally)
option(BUILD_TESTS "Build tests" ON)
if(BUILD_TESTS)
  find_package(GTest QUIET)
  if(NOT GTest_FOUND)
    include(FetchContent)
    FetchContent_Declare(googletest
      URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
    )
    FetchContent_MakeAvailable(googletest)
  endif()

  enable_testing()
  add_executable(test_data_manager tests/test_data_manager.cpp src/data_manager.cpp)
  target_link_libraries(test_data_manager PRIVATE Qt5::Core GTest::gtest_main)
  add_test(NAME test_data_manager COMMAND test_data_manager)

  add_executable(test_mqtt_parse tests/test_mqtt_parse.cpp src/mqtt_client.cpp)
  target_link_libraries(test_mqtt_parse PRIVATE Qt5::Core GTest::gtest_main paho-mqttpp3)
  add_test(NAME test_mqtt_parse COMMAND test_mqtt_parse)

  find_package(Qt5 REQUIRED COMPONENTS Test)
  add_executable(test_integration tests/test_integration.cpp src/data_manager.cpp src/mqtt_client.cpp)
  target_link_libraries(test_integration PRIVATE Qt5::Core Qt5::Test paho-mqttpp3)
  add_test(NAME test_integration COMMAND test_integration)
endif()
