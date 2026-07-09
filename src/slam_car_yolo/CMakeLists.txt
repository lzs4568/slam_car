cmake_minimum_required(VERSION 3.8)
project(slam_car_yolo)

# ---- C++17 ----
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- ROS2 依赖 ----
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

# ---- RKNN 运行时（板端 ELF2 上的路径）----
set(RKNN_RT_LIB
    /data/yolov8/yolo_test/rknn-cpp-Multithreading-main/include/librknnrt.so)

# ---- 编译选项 ----
add_compile_options(-Wall -pthread -Wno-sign-compare)

# ---- 可执行文件 ----
add_executable(yolo_node
    src/yolo_node.cpp
    src/yolo_engine.cpp
    src/postprocess.cpp
)

# ament 包依赖（rclcpp / sensor_msgs / cv_bridge）的 include + link
ament_target_dependencies(yolo_node
    rclcpp
    sensor_msgs
    cv_bridge
)

# 额外 include 目录（RKNN API、OpenCV）
target_include_directories(yolo_node PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OpenCV_INCLUDE_DIRS}
    /usr/include/opencv4
)

# 额外 link 库
target_link_libraries(yolo_node
    ${RKNN_RT_LIB}
    ${OpenCV_LIBS}
)

# ---- 安装 ----
install(TARGETS yolo_node
    DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY model launch config
    DESTINATION share/${PROJECT_NAME})

ament_package()
