// ============================================================
// 复制为 constants.js 并填入你的华为云真实值
// 华为云 IAM 认证配置
// ============================================================
const IAM_USERNAME = 'YOUR_IAM_USERNAME';
const IAM_PASSWORD = 'YOUR_IAM_PASSWORD';
const IAM_DOMAIN   = 'YOUR_IAM_DOMAIN';
const IAM_PROJECT  = 'cn-east-3';

// ============================================================
// 华为云 IoTDA 配置
// ============================================================
const IOTDA_HOST  = 'xxxx.st1.iotda-app.cn-east-3.myhuaweicloud.com';
const DEVICE_ID   = 'YOUR_DEVICE_ID';
const PROJECT_ID  = 'YOUR_PROJECT_ID';

// ============================================================
// 传感器定义
// ============================================================
const SENSOR_DEFS = [
  { key: 'temp',           name: '温度',   unit: '°C',     decimal: 1 },
  { key: 'hum',            name: '湿度',   unit: '%',      decimal: 1 },
  { key: 'mq2_gas_value',  name: 'MQ2',    unit: '',       decimal: 0 },
  { key: 'mq135_gas_value',name: 'MQ135',  unit: '',       decimal: 0 },
  { key: 'pm2_5',          name: 'PM2.5',  unit: 'µg/m³',  decimal: 0 },
  { key: 'eco2',           name: 'CO₂当量', unit: 'ppm',   decimal: 0 },
  { key: 'tvoc',           name: 'TVOC',   unit: 'ppb',    decimal: 0 },
  { key: 'volt',           name: '电池',   unit: 'V',      decimal: 2 },
];

// ============================================================
// Service ID — 与华为云 IoTDA 产品中定义的 service_id 一致
// ============================================================
const SERVICE_ID = 'car_sensor';

// ============================================================
// 默认告警阈值
// ============================================================
const DEFAULT_THRESHOLDS = {
  temp:           { min: -20, max: 60 },
  hum:            { min: 0,   max: 100 },
  mq2_gas_value:  { min: 0,   max: 500 },
  mq135_gas_value:{ min: 0,   max: 500 },
  pm2_5:          { min: 0,   max: 75 },
  eco2:           { min: 0,   max: 1000 },
  tvoc:           { min: 0,   max: 500 },
  volt:           { min: 10.5,max: 13.5 },
};

// ============================================================
// 轮询间隔（毫秒）
// ============================================================
const POLL_INTERVAL = 5000;

module.exports = {
  IAM_USERNAME,
  IAM_PASSWORD,
  IAM_DOMAIN,
  IAM_PROJECT,
  IOTDA_HOST,
  DEVICE_ID,
  PROJECT_ID,
  SENSOR_DEFS,
  SERVICE_ID,
  DEFAULT_THRESHOLDS,
  POLL_INTERVAL,
};
