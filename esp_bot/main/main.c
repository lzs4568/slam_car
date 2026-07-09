#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"

// 真实传感器驱动
#include "driver/i2c.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"

// I2S 驱动（IDF v6.0.1 新 channel API，DMA 直达 PSRAM）
#include "driver/i2s_std.h"
#include "driver/i2s_common.h"

// LEDC PWM (GP2Y1010AU 脉冲驱动)
#include "driver/ledc.h"
#include "esp_rom_sys.h"

// ESP-IDF v6.0.1 USB（espressif/esp_tinyusb v2.x）
#include "tinyusb.h"
#include "tinyusb_default_config.h"
#include "tinyusb_cdc_acm.h"

// esp-sr 语音唤醒（关键头文件）
#include "esp_wn_iface.h"
#include "esp_wn_models.h"
#include "esp_mn_iface.h"
#include "esp_mn_models.h"
#include "esp_vad.h"
#include "model_path.h"

static const char *TAG = "MAIN_APP";

// ===================================================================
// 引脚定义（避开 PSRAM 26-35、USB 19-20、UART0 43-44）
// ===================================================================
// INMP441 I2S 数字麦克风
#define I2S_BCLK_IO         GPIO_NUM_6
#define I2S_WS_IO           GPIO_NUM_7
#define I2S_DIN_IO          GPIO_NUM_15

// AHT25 温湿度传感器 (I2C_NUM_0)
#define AHT25_I2C_SDA_IO    GPIO_NUM_4
#define AHT25_I2C_SCL_IO    GPIO_NUM_5
#define AHT25_I2C_ADDR      0x38
#define AHT25_I2C_PORT      I2C_NUM_0

// SGP30 CO₂/VOC 传感器 (I2C_NUM_1)
#define SGP30_I2C_SDA_IO    GPIO_NUM_11
#define SGP30_I2C_SCL_IO    GPIO_NUM_12
#define SGP30_I2C_ADDR      0x58
#define SGP30_I2C_PORT      I2C_NUM_1

// PM2.5 GP2Y1010AU 脉冲驱动 (LEDC + ADC)
#define PM25_LED_IO         GPIO_NUM_18     // LED 驱动脉冲 (10ms周期, 0.32ms脉宽)
#define PM25_ADC_CH         ADC_CHANNEL_7   // GPIO8 → ADC1_CH7 (Vo 模拟输出)

// 电池电压 + MQ2 (ADC1)
#define BATTERY_ADC_CH      ADC_CHANNEL_0   // GPIO1  → ADC1_CH0
#define MQ2_ADC_CH          ADC_CHANNEL_1   // GPIO2  → ADC1_CH1

// MQ135 空气质量 (ADC2, 因 GPIO14 属 ADC2)
#define MQ135_ADC_CH        ADC_CHANNEL_3   // GPIO14 → ADC2_CH3

// ===================================================================
// 音频参数
// ===================================================================
#define SAMPLE_RATE         16000
#define BITS_PER_SAMPLE     16
#define FRAME_MS            30
#define SAMPLES_PER_FRAME   (SAMPLE_RATE * FRAME_MS / 1000)  // 480
#define BYTES_PER_FRAME     (SAMPLES_PER_FRAME * (BITS_PER_SAMPLE / 8))  // 960

#define DMA_DESC_NUM        8
#define DMA_FRAME_NUM       SAMPLES_PER_FRAME
#define RING_BUFFER_SIZE    (64 * 1024)

static RingbufHandle_t audio_ring_buf = NULL;
static volatile bool is_streaming = false;
static i2s_chan_handle_t i2s_rx_chan = NULL;

// ========== USB 设备描述符 ==========
static const tusb_desc_device_t desc_device = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0200,
    .bDeviceClass       = TUSB_CLASS_MISC,
    .bDeviceSubClass    = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol    = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor           = 0x303A,
    .idProduct          = 0x4001,
    .bcdDevice          = 0x0100,
    .iManufacturer      = 0x01,
    .iProduct           = 0x02,
    .iSerialNumber      = 0x03,
    .bNumConfigurations = 0x01
};

static const char* string_desc[] = {
    (const char[]) { 0x09, 0x04 },
    "Espressif",
    "ESP32-S3 Dual USB Audio",
    "S3-N8R8-001",
    "Audio Streaming",
};

// ========== esp-sr 全局句柄 ==========
static const esp_wn_iface_t *wakenet = NULL;
static model_iface_data_t *model_data = NULL;
static srmodel_list_t *models = NULL;
static vad_handle_t vad_handle = NULL;

// ========== I2S 初始化（标准模式，INMP441）==========
static void init_i2s_microphone(void)
{
    ESP_LOGI(TAG, "初始化 I2S INMP441 麦克风");

    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = DMA_DESC_NUM;
    chan_cfg.dma_frame_num = DMA_FRAME_NUM;

    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, NULL, &i2s_rx_chan));

    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = I2S_BCLK_IO,
            .ws   = I2S_WS_IO,
            .dout = I2S_GPIO_UNUSED,
            .din  = I2S_DIN_IO,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    std_cfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(i2s_rx_chan, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_enable(i2s_rx_chan));

    ESP_LOGI(TAG, "I2S 就绪: %dHz, GPIO BCLK=%d WS=%d DIN=%d",
             SAMPLE_RATE, I2S_BCLK_IO, I2S_WS_IO, I2S_DIN_IO);
}

// ========== AHT25 I2C 温湿度传感器驱动 ==========
static bool aht25_init(void)
{
    uint8_t cmd[] = {0xBE, 0x08, 0x00};
    esp_err_t ret = i2c_master_write_to_device(AHT25_I2C_PORT, AHT25_I2C_ADDR,
                                                cmd, sizeof(cmd), pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "AHT25 初始化失败: %s", esp_err_to_name(ret));
        return false;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
    return true;
}

static bool aht25_read(float *temp_out, float *humi_out)
{
    uint8_t trig[] = {0xAC, 0x33, 0x00};
    esp_err_t ret = i2c_master_write_to_device(AHT25_I2C_PORT, AHT25_I2C_ADDR,
                                                trig, sizeof(trig), pdMS_TO_TICKS(100));
    if (ret != ESP_OK) return false;
    vTaskDelay(pdMS_TO_TICKS(80));

    uint8_t data[7] = {0};
    ret = i2c_master_read_from_device(AHT25_I2C_PORT, AHT25_I2C_ADDR,
                                       data, 7, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) return false;
    if (data[0] & 0x80) return false;

    uint32_t humi_raw = ((uint32_t)data[1] << 12) | ((uint32_t)data[2] << 4) | (data[3] >> 4);
    *humi_out = (float)humi_raw * 100.0f / 1048576.0f;

    uint32_t temp_raw = ((uint32_t)(data[3] & 0x0F) << 16) | ((uint32_t)data[4] << 8) | data[5];
    *temp_out = (float)temp_raw * 200.0f / 1048576.0f - 50.0f;

    return true;
}

// ========== SGP30 CO₂/VOC 传感器驱动 ==========
static bool sgp30_is_init = false;

static bool sgp30_init(void)
{
    // SGP30 初始化命令: 0x20 0x03 (Init_air_quality)
    uint8_t init_cmd[] = {0x20, 0x03};
    esp_err_t ret = i2c_master_write_to_device(SGP30_I2C_PORT, SGP30_I2C_ADDR,
                                                init_cmd, sizeof(init_cmd), pdMS_TO_TICKS(100));
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SGP30 初始化失败: %s", esp_err_to_name(ret));
        return false;
    }
    // 等待传感器就绪（最长 15 秒，但 2 秒通常足够首次初始化）
    vTaskDelay(pdMS_TO_TICKS(2000));
    sgp30_is_init = true;
    ESP_LOGI(TAG, "✅ SGP30 初始化完成 (I2C%d addr=0x%02X)", SGP30_I2C_PORT, SGP30_I2C_ADDR);
    return true;
}

static bool sgp30_read(uint16_t *eco2_out, uint16_t *tvoc_out)
{
    if (!sgp30_is_init) return false;

    // 测量命令: 0x20 0x08 (Measure_air_quality)
    uint8_t measure_cmd[] = {0x20, 0x08};
    esp_err_t ret = i2c_master_write_to_device(SGP30_I2C_PORT, SGP30_I2C_ADDR,
                                                measure_cmd, sizeof(measure_cmd), pdMS_TO_TICKS(100));
    if (ret != ESP_OK) return false;

    vTaskDelay(pdMS_TO_TICKS(15));  // 等待测量完成 (typ 12ms)

    uint8_t data[6] = {0};
    ret = i2c_master_read_from_device(SGP30_I2C_PORT, SGP30_I2C_ADDR,
                                       data, 6, pdMS_TO_TICKS(100));
    if (ret != ESP_OK) return false;

    // CRC 校验 (SGP30 每 2 字节跟 1 字节 CRC8)
    *eco2_out = ((uint16_t)data[0] << 8) | data[1];
    *tvoc_out = ((uint16_t)data[3] << 8) | data[4];
    return true;
}

// ========== GP2Y1010AU PM2.5 粉尘传感器 (脉冲驱动) ==========
// 规格: LED脉冲周期 10ms, 脉宽 0.32ms, 采样点 0.28ms
// 检出感度 K = 0.5V/(0.1mg/m³), 无尘输出电压 Voc ≈ 0.9V
// 方法: LEDC 100Hz PWM驱动LED, 软件多次采样取MAX捕获脉冲峰值
// (ADC/校准句柄需前向声明, pm25_read 引用)
static adc_oneshot_unit_handle_t adc1_handle = NULL;
static adc_cali_handle_t adc_cali_handle = NULL;
static adc_oneshot_unit_handle_t adc2_handle = NULL;  // MQ135 (GPIO14 / ADC2)

static float pm25_voc = 0.9f;  // 无尘基准电压 (动态更新)

static void pm25_init(void)
{
    // LEDC PWM: 100Hz (10ms), 3.2% duty → 0.32ms 脉宽
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_LOW_SPEED_MODE,
        .duty_resolution  = LEDC_TIMER_10_BIT,  // 0-1023
        .timer_num        = LEDC_TIMER_0,
        .freq_hz          = 100,                 // 10ms 周期
        .clk_cfg          = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&ledc_timer));

    ledc_channel_config_t ledc_ch = {
        .gpio_num       = PM25_LED_IO,
        .speed_mode     = LEDC_LOW_SPEED_MODE,
        .channel        = LEDC_CHANNEL_0,
        .timer_sel      = LEDC_TIMER_0,
        .duty           = 33,   // 33/1024 ≈ 3.2% → 0.32ms @ 100Hz
        .hpoint         = 0,
    };
    ESP_ERROR_CHECK(ledc_channel_config(&ledc_ch));
    ESP_LOGI(TAG, "✅ GP2Y1010AU LED PWM 就绪 (GPIO%d, 100Hz/3.2%%)", PM25_LED_IO);
}

static float pm25_read(void)
{
    // 快速采样 20 次取最大值 (捕获 LED 脉冲同步的峰值)
    int max_raw = 0;
    for (int i = 0; i < 20; i++) {
        int v = 0;
        if (adc_oneshot_read(adc1_handle, PM25_ADC_CH, &v) == ESP_OK) {
            if (v > max_raw) max_raw = v;
        }
        esp_rom_delay_us(50);  // 50μs 间隔 → 覆盖 ~1ms 窗口
    }

    if (max_raw == 0) return -1.0f;

    // ADC raw → 电压
    float vo = (float)max_raw * 2.6f / 4095.0f;
    if (adc_cali_handle != NULL) {
        int mv = 0;
        if (adc_cali_raw_to_voltage(adc_cali_handle, max_raw, &mv) == ESP_OK) {
            vo = (float)mv / 1000.0f;
        }
    }

    // 动态更新无尘基准: 当前读数低于基准 → 缓慢衰减基准
    if (vo < pm25_voc) {
        pm25_voc = pm25_voc * 0.999f + vo * 0.001f;  // EMA 衰减
    }

    // 粉尘浓度 (mg/m³) = (Vo - Voc) / K
    // K = 0.5V / (0.1 mg/m³) = 5.0V / (mg/m³)
    float delta = vo - pm25_voc;
    if (delta < 0) delta = 0;
    float mgm3 = delta / 5.0f;

    return mgm3;
}

// ========== ADC 电池 + MQ2 驱动 ==========

static void init_adc(void)
{
    adc_oneshot_unit_init_cfg_t unit_cfg = {
        .unit_id = ADC_UNIT_1,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_cfg, &adc1_handle));

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, BATTERY_ADC_CH, &chan_cfg));
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, MQ2_ADC_CH, &chan_cfg));
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc1_handle, PM25_ADC_CH, &chan_cfg));

    adc_cali_curve_fitting_config_t cali_cfg = {
        .unit_id = ADC_UNIT_1,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    esp_err_t cali_ret = adc_cali_create_scheme_curve_fitting(&cali_cfg, &adc_cali_handle);
    if (cali_ret == ESP_OK) {
        ESP_LOGI(TAG, "✅ ADC 校准已启用（eFuse 曲线拟合）");
    } else if (cali_ret == ESP_ERR_NOT_SUPPORTED) {
        ESP_LOGW(TAG, "⚠️ eFuse 无校准数据，使用默认参考电压");
    } else {
        ESP_LOGE(TAG, "❌ ADC 校准失败");
    }

    // ADC2: MQ135 (GPIO14). 本固件不使用 WiFi, ADC2 oneshot 可用
    adc_oneshot_unit_init_cfg_t adc2_unit_cfg = {
        .unit_id = ADC_UNIT_2,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&adc2_unit_cfg, &adc2_handle));
    adc_oneshot_chan_cfg_t mq135_chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc2_handle, MQ135_ADC_CH, &mq135_chan_cfg));
    ESP_LOGI(TAG, "✅ ADC2 就绪 (MQ135=GPIO14)");
}

static float adc_read_voltage(adc_channel_t ch)
{
    int raw = 0;
    esp_err_t ret = adc_oneshot_read(adc1_handle, ch, &raw);
    if (ret != ESP_OK) return -1.0f;

    if (adc_cali_handle != NULL) {
        int voltage_mv = 0;
        ret = adc_cali_raw_to_voltage(adc_cali_handle, raw, &voltage_mv);
        if (ret == ESP_OK) {
            return (float)voltage_mv / 1000.0f;
        }
    }
    return (float)raw * 2.6f / 4095.0f;
}

// ========== 传感器初始化总入口 ==========
static void init_sensors(void)
{
    // ── I2C_NUM_0: AHT25 (GPIO4/5) ──
    i2c_config_t i2c0_conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = AHT25_I2C_SDA_IO,
        .scl_io_num = AHT25_I2C_SCL_IO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master = { .clk_speed = 100000 },
    };
    ESP_ERROR_CHECK(i2c_param_config(AHT25_I2C_PORT, &i2c0_conf));
    ESP_ERROR_CHECK(i2c_driver_install(AHT25_I2C_PORT, I2C_MODE_MASTER, 0, 0, 0));

    if (aht25_init()) {
        ESP_LOGI(TAG, "✅ AHT25 就绪 (I2C%d GPIO%d/GPIO%d)",
                 AHT25_I2C_PORT, AHT25_I2C_SDA_IO, AHT25_I2C_SCL_IO);
    } else {
        ESP_LOGW(TAG, "⚠️ AHT25 未检测到");
    }

    // ── I2C_NUM_1: SGP30 (GPIO11/12) ──
    i2c_config_t i2c1_conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = SGP30_I2C_SDA_IO,
        .scl_io_num = SGP30_I2C_SCL_IO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master = { .clk_speed = 100000 },
    };
    ESP_ERROR_CHECK(i2c_param_config(SGP30_I2C_PORT, &i2c1_conf));
    ESP_ERROR_CHECK(i2c_driver_install(SGP30_I2C_PORT, I2C_MODE_MASTER, 0, 0, 0));

    if (sgp30_init()) {
        ESP_LOGI(TAG, "✅ SGP30 CO₂/VOC 就绪 (I2C%d GPIO%d/GPIO%d)",
                 SGP30_I2C_PORT, SGP30_I2C_SDA_IO, SGP30_I2C_SCL_IO);
    } else {
        ESP_LOGW(TAG, "⚠️ SGP30 未检测到");
    }

    // ── ADC1: 电池 + MQ2 ──
    init_adc();

    // ── PM2.5: GP2Y1010AU 脉冲驱动 ──
    pm25_init();

    ESP_LOGI(TAG, "✅ ADC1 就绪 (BAT=GPIO1, MQ2=GPIO2, PM25=GPIO8/LED=GPIO9)");
}

// ========== 任务 A：传感器打印（Core 0）==========
void task_sensors_print(void *pvParameters) {
    ESP_LOGI(TAG, "传感器任务 @ Core %d", xPortGetCoreID());

    // SGP30 读失败时回退到上一次有效值(初值为室内正常值)
    static uint16_t last_eco2 = 400;
    static uint16_t last_tvoc = 0;

    while (1) {
        float temp = -99.0f, humi = -1.0f;
        int mq2_raw = 0;
        float bat_v = -1.0f, pm25_ugm3 = -1.0f;
        uint16_t eco2 = 0, tvoc = 0;

        // 读取 AHT25 温湿度
        aht25_read(&temp, &humi);

        // 读取 MQ2 (ADC raw)
        adc_oneshot_read(adc1_handle, MQ2_ADC_CH, &mq2_raw);

        // MQ135 真实读取 (ADC2 原始值, 与 MQ2 一致不做校准)
        int mq135_raw = 0;
        adc_oneshot_read(adc2_handle, MQ135_ADC_CH, &mq135_raw);

        // 读取 PM2.5 (GP2Y1010AU: 脉冲驱动, Max采样, Voc 动态基准)
        pm25_ugm3 = pm25_read();

        // 读取 SGP30 CO₂(eCO2 ppm) + TVOC (ppb),失败则回退上一次有效值
        if (sgp30_read(&eco2, &tvoc)) {
            last_eco2 = eco2;
            last_tvoc = tvoc;
        } else {
            eco2 = last_eco2;
            tvoc = last_tvoc;
        }

        // 读取电池电压
        float bat_pin_v = adc_read_voltage(BATTERY_ADC_CH);
        if (bat_pin_v > 0) {
            float raw_v = bat_pin_v * (10.462f * (24.64f / 23.80f));
            bat_v = 1.3855f * raw_v - 9.57f;
            if (bat_v < 0) bat_v = 0;
        }

        printf("{\"temp\":%.2f,\"humi\":%.2f,\"mq2\":%d,"
               "\"mq135\":%d,"
               "\"pm25\":%.3f,\"pm25_voc\":%.3f,"
               "\"eco2\":%d,\"tvoc\":%d,\"volt\":%.2f,\"stream\":%s}\n",
               temp, humi, mq2_raw, mq135_raw,
               pm25_ugm3, pm25_voc,
               eco2, tvoc, bat_v, is_streaming ? "true" : "false");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

// ========== 任务 B：USB 音频推流（Core 0）==========
void task_audio_push(void *pvParameters) {
    ESP_LOGI(TAG, "USB推流任务 @ Core %d", xPortGetCoreID());
    size_t item_size;
    uint32_t total_bytes = 0;

    while (1) {
        if (!is_streaming) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        uint8_t *data = xRingbufferReceive(audio_ring_buf, &item_size, pdMS_TO_TICKS(10));
        if (data == NULL) continue;

        if (tud_mounted()) {
            esp_err_t ret = tinyusb_cdcacm_write_queue(TINYUSB_CDC_ACM_0, data, item_size);
            if (ret == ESP_OK) {
                tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, 0);
                total_bytes += item_size;
            }
        }
        vRingbufferReturnItem(audio_ring_buf, (void *)data);
    }
}

// ========== 任务 C：语音唤醒 + I2S 音频采集（Core 1）==========
void task_speech_wake(void *pvParameters) {
    ESP_LOGI(TAG, "语音唤醒任务 @ Core %d", xPortGetCoreID());

    int16_t *audio_buffer = heap_caps_malloc(
        SAMPLES_PER_FRAME * sizeof(int16_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_DMA
    );
    if (audio_buffer == NULL) {
        ESP_LOGE(TAG, "PSRAM DMA 音频缓冲区分配失败");
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(TAG, "音频缓冲: %d samples, PSRAM DMA 零拷贝", SAMPLES_PER_FRAME);

    size_t bytes_read = 0;
    int64_t stream_start = 0;
    int silence_frames = 0;
    const int MAX_STREAM_SEC = 60;
    const int SILENCE_THRESHOLD = 300;

    while (1) {
        esp_err_t i2s_ret = i2s_channel_read(
            i2s_rx_chan,
            audio_buffer,
            SAMPLES_PER_FRAME * sizeof(int16_t),
            &bytes_read,
            pdMS_TO_TICKS(50)
        );

        if (i2s_ret != ESP_OK) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        if (wakenet != NULL && model_data != NULL) {
            int r = wakenet->detect(model_data, audio_buffer);

            if (r == WAKENET_DETECTED) {
                ESP_LOGW(TAG, "🎤 检测到唤醒词！");
                is_streaming = true;
                stream_start = esp_timer_get_time();
                silence_frames = 0;
            }
        }

        if (is_streaming) {
            if (vad_handle != NULL) {
                vad_state_t v = vad_process(vad_handle, audio_buffer, SAMPLE_RATE, FRAME_MS);
                if (v == VAD_SPEECH) {
                    silence_frames = 0;
                } else {
                    silence_frames++;
                }
            }

            if (silence_frames >= SILENCE_THRESHOLD) {
                is_streaming = false;
                ESP_LOGW(TAG, "⏹️ 静音 %.1fs，停止推流", silence_frames * FRAME_MS / 1000.0f);
            }

            int64_t elapsed_s = (esp_timer_get_time() - stream_start) / 1000000;
            if (elapsed_s > MAX_STREAM_SEC) {
                is_streaming = false;
                ESP_LOGW(TAG, "⏹️ 推流超时（%ds）", MAX_STREAM_SEC);
            }

            if (is_streaming) {
                BaseType_t res = xRingbufferSend(
                    audio_ring_buf,
                    audio_buffer,
                    SAMPLES_PER_FRAME * sizeof(int16_t),
                    pdMS_TO_TICKS(5)
                );
                if (res != pdTRUE) {
                    static uint32_t drops = 0;
                    if (++drops % 50 == 0) {
                        ESP_LOGW(TAG, "RingBuf 满，丢帧: %lu", drops);
                    }
                }
            }
        }
    }
}

// ========== 初始化 esp-sr ==========
void init_esp_sr(void) {
    ESP_LOGI(TAG, "初始化 esp-sr（零拷贝 PSRAM）...");

    models = esp_srmodel_init("model");
    if (models == NULL) {
        ESP_LOGE(TAG, "模型分区未找到！使用模拟模式");
        return;
    }

    ESP_LOGI(TAG, "可用模型:");
    for (int i = 0; i < models->num; i++) {
        ESP_LOGI(TAG, "  [%d] %s", i, models->model_name[i]);
    }

    const char *model_name = models->model_name[0];
    ESP_LOGI(TAG, "选择唤醒词模型: %s", model_name);

    wakenet = esp_wn_handle_from_name(model_name);
    if (wakenet == NULL) {
        ESP_LOGE(TAG, "唤醒词模型加载失败");
        return;
    }

    model_data = wakenet->create(model_name, DET_MODE_90);
    if (model_data == NULL) {
        ESP_LOGE(TAG, "模型实例创建失败");
        return;
    }

    int rate = wakenet->get_samp_rate(model_data);
    int chunks = wakenet->get_samp_chunksize(model_data);
    ESP_LOGI(TAG, "唤醒模型就绪: %dHz, 帧大小: %d samples", rate, chunks);

    vad_handle = vad_create(VAD_MODE_0);
    if (vad_handle != NULL) {
        ESP_LOGI(TAG, "✅ VAD 就绪 (静音 3.0s → 自动停止推流)");
    } else {
        ESP_LOGW(TAG, "⚠️ VAD 初始化失败，使用 5s 固定超时回退");
    }
}

// ========== 主入口 ==========
void app_main(void) {
    ESP_LOGI(TAG, "=================================");
    ESP_LOGI(TAG, " ESP32-S3 双USB系统 (IDF v6.0.1) ");
    ESP_LOGI(TAG, " N8R8 PSRAM 零拷贝架构          ");
    ESP_LOGI(TAG, "=================================");

    // 1. 初始化 USB CDC
    tinyusb_config_t tusb_cfg = TINYUSB_DEFAULT_CONFIG();
    tusb_cfg.descriptor.device = &desc_device;
    tusb_cfg.descriptor.string = string_desc;
    tusb_cfg.descriptor.string_count = sizeof(string_desc) / sizeof(string_desc[0]);
    ESP_ERROR_CHECK(tinyusb_driver_install(&tusb_cfg));

    tinyusb_config_cdcacm_t acm_cfg = {
        .cdc_port = TINYUSB_CDC_ACM_0,
        .callback_rx = NULL,
        .callback_rx_wanted_char = NULL,
        .callback_line_state_changed = NULL,
        .callback_line_coding_changed = NULL
    };
    ESP_ERROR_CHECK(tinyusb_cdcacm_init(&acm_cfg));
    ESP_LOGI(TAG, "✅ USB CDC 就绪（原生 USB → 音频推流）");

    // 2. 初始化 I2S INMP441
    init_i2s_microphone();

    // 3. 创建 RingBuffer
    audio_ring_buf = xRingbufferCreate(RING_BUFFER_SIZE, RINGBUF_TYPE_BYTEBUF);
    if (audio_ring_buf == NULL) {
        ESP_LOGE(TAG, "RingBuffer 创建失败");
        return;
    }
    ESP_LOGI(TAG, "✅ 64KB RingBuffer 就绪（PSRAM）");

    // 4. 初始化所有传感器 (AHT25 + SGP30 + ADC 电池/MQ2/PM2.5)
    init_sensors();

    // 5. 初始化 esp-sr
    init_esp_sr();

    // 6. 任务绑定
    xTaskCreatePinnedToCore(task_sensors_print, "sensors", 4096, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(task_audio_push,    "usb_push", 8192, NULL, 6, NULL, 0);
    xTaskCreatePinnedToCore(task_speech_wake,   "speech",   16384, NULL, 10, NULL, 1);

    ESP_LOGI(TAG, "=================================");
    ESP_LOGI(TAG, " 🚀 系统启动完成");
    ESP_LOGI(TAG, "   传感器: AHT25 + SGP30 + MQ2 + PM2.5 + BAT");
    ESP_LOGI(TAG, "   [Core 0] 传感器 + USB 推流");
    ESP_LOGI(TAG, "   [Core 1] I2S 采集 + 唤醒检测");
    ESP_LOGI(TAG, "=================================");
}
