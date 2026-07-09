idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    # 依赖的组件（显式声明）
    REQUIRES
        freertos
        esp_common
        esp_hw_support
        esp_ringbuf             # freertos/ringbuf.h
        esp_timer               # esp_timer.h
        esp_partition           # 模型分区读取
        esp_system
        esp-sr                  # esp-sr 语音识别
        esp_driver_i2s          # I2S 驱动（IDF v6.0.1 channel API）
        esp_driver_ledc         # LEDC PWM 驱动（GP2Y1010AU 脉冲）
        esp_adc                 # ADC oneshot（电池 + MQ2）
        driver
)