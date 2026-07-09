cmake_minimum_required(VERSION 3.8)
project(slam_car_rtsp)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

# GStreamer
find_package(PkgConfig REQUIRED)
pkg_check_modules(GSTREAMER REQUIRED
  gstreamer-1.0
  gstreamer-app-1.0
)

include_directories(include ${GSTREAMER_INCLUDE_DIRS})

add_executable(rtsp_node src/rtsp_node.cpp)

ament_target_dependencies(rtsp_node rclcpp sensor_msgs)

target_link_libraries(rtsp_node ${GSTREAMER_LIBRARIES})

target_compile_options(rtsp_node PRIVATE -Wall -O2)

install(TARGETS rtsp_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME})

ament_package()
