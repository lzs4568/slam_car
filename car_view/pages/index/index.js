const api = require('../../utils/api.js');
const {
  SENSOR_DEFS,
  SERVICE_ID,
  DEFAULT_THRESHOLDS,
  POLL_INTERVAL,
} = require('../../utils/constants.js');

Page({
  data: {
    deviceOnline: false,
    batteryVoltage: '--',
    lastUpdate: '',
    sensors: SENSOR_DEFS.map(s => ({
      ...s,
      value: null,
      alarm: false,
    })),
    popupVisible: false,
    editingSensor: null,
  },

  _timer: null,
  _firstLoad: true,

  onShow() {
    this.fetchAll();
    this._timer = setInterval(() => this.fetchAll(), POLL_INTERVAL);
  },

  onHide() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  },

  onPullDownRefresh() {
    this.fetchAll().then(() => wx.stopPullDownRefresh());
  },

  // ==========================================
  // 数据获取
  // ==========================================
  fetchAll() {
    return Promise.all([
      api.getShadow().catch(err => {
        console.error('getShadow error:', err);
        return null;
      }),
      api.getDeviceStatus().catch(err => {
        console.error('getDeviceStatus error:', err);
        return null;
      }),
    ]).then(([shadow, status]) => {
      this.processShadow(shadow);
      this.processStatus(status);
      this.setData({
        lastUpdate: this._formatTime(new Date()),
      });
    });
  },

  processShadow(shadow) {
    if (!shadow || !shadow.shadow) return;

    const shadowList = shadow.shadow || [];
    const carService = shadowList.find(s => s.service_id === SERVICE_ID);
    if (!carService) return;

    const props = (carService.reported && carService.reported.properties) || {};
    const thresholds = wx.getStorageSync('thresholds') || {};

    const now = Date.now();
    const history = wx.getStorageSync('sensor_history') || {};
    const sensors = this.data.sensors.map(s => {
      const raw = props[s.key];
      let value = null;
      if (raw !== undefined && raw !== null) {
        value = Number(raw);
      }
      if (isNaN(value)) value = null;

      // 存入本地历史
      if (value != null) {
        if (!history[s.key]) history[s.key] = [];
        history[s.key].push([now, value]);
      }

      const alarm = this._checkAlarm(s.key, value, thresholds);
      return { ...s, value, alarm };
    });

    // 清理 24 小时前的旧数据
    const cutoff = now - 24 * 3600 * 1000;
    Object.keys(history).forEach(key => {
      history[key] = history[key].filter(([ts]) => ts > cutoff);
    });
    wx.setStorageSync('sensor_history', history);

    // 提取电池电压
    const batterySensor = sensors.find(s => s.key === 'volt');
    const batteryVoltage = batterySensor && batterySensor.value != null
      ? batterySensor.value.toFixed(2)
      : '--';

    this.setData({ sensors, batteryVoltage });
  },

  processStatus(status) {
    if (!status) return;
    const online = status.status === 'ONLINE';
    this.setData({ deviceOnline: online });

    if (!online && !this._firstLoad) {
      // 离线时传感器值归 false/0 视觉效果，但不覆盖存储
    }
    this._firstLoad = false;
  },

  // ==========================================
  // 告警判断
  // ==========================================
  _checkAlarm(key, value, thresholds) {
    if (value == null) return false;
    const t = thresholds[key] || DEFAULT_THRESHOLDS[key] || {};
    if (t.min !== undefined && value < t.min) return true;
    if (t.max !== undefined && value > t.max) return true;
    return false;
  },

  // ==========================================
  // 事件处理
  // ==========================================
  onCardTap(e) {
    const idx = e.currentTarget.dataset.index;
    const sensor = this.data.sensors[idx];
    wx.navigateTo({
      url: `/pages/history/history?sensor_key=${sensor.key}&sensor_name=${sensor.name}&unit=${sensor.unit}`,
    });
  },

  onSettingTap(e) {
    const idx = e.currentTarget.dataset.index;
    const sensor = this.data.sensors[idx];
    const thresholds = wx.getStorageSync('thresholds') || {};
    const t = thresholds[sensor.key] || DEFAULT_THRESHOLDS[sensor.key] || {};

    this.setData({
      popupVisible: true,
      editingSensor: {
        key: sensor.key,
        name: sensor.name,
        unit: sensor.unit,
        min: t.min !== undefined ? t.min : 0,
        max: t.max !== undefined ? t.max : 100,
      },
    });
  },

  onThresholdSave(e) {
    const { min, max } = e.detail;
    const { key } = this.data.editingSensor;
    const thresholds = wx.getStorageSync('thresholds') || {};
    thresholds[key] = { min, max };
    wx.setStorageSync('thresholds', thresholds);

    // 重新做告警判断
    const sensors = this.data.sensors.map(s => {
      if (s.key === key) {
        return { ...s, alarm: this._checkAlarm(key, s.value, thresholds) };
      }
      return s;
    });
    this.setData({ sensors, popupVisible: false, editingSensor: null });
  },

  onPopupClose() {
    this.setData({ popupVisible: false, editingSensor: null });
  },

  onRefresh() {
    this.fetchAll();
  },

  // ==========================================
  // 工具函数
  // ==========================================
  _formatTime(date) {
    const h = date.getHours().toString().padStart(2, '0');
    const m = date.getMinutes().toString().padStart(2, '0');
    const s = date.getSeconds().toString().padStart(2, '0');
    return `${h}:${m}:${s}`;
  },
});
