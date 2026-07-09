const {
  IAM_USERNAME,
  IAM_PASSWORD,
  IAM_DOMAIN,
  IAM_PROJECT,
  IOTDA_HOST,
  DEVICE_ID,
  PROJECT_ID,
  SERVICE_ID,
} = require('./constants.js');

// ============================================================
// Token 缓存
// ============================================================
let cachedToken = null;
let tokenExpire = 0;          // 毫秒时间戳
const TOKEN_TTL = 23 * 3600 * 1000; // 23 小时

// ============================================================
// 获取 IAM Token（自动缓存）
// ============================================================
function getToken() {
  if (cachedToken && Date.now() < tokenExpire) {
    return Promise.resolve(cachedToken);
  }
  return new Promise((resolve, reject) => {
    wx.request({
      url: 'https://iam.myhuaweicloud.com/v3/auth/tokens',
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        auth: {
          identity: {
            methods: ['password'],
            password: {
              user: {
                name: IAM_USERNAME,
                password: IAM_PASSWORD,
                domain: { name: IAM_DOMAIN },
              },
            },
          },
          scope: {
            project: { name: IAM_PROJECT },
          },
        },
      },
      success(res) {
        if (res.statusCode === 201) {
          cachedToken = res.header['X-Subject-Token'] || res.header['x-subject-token'];
          tokenExpire = Date.now() + TOKEN_TTL;
          resolve(cachedToken);
        } else {
          reject(new Error('IAM auth failed: ' + res.statusCode));
        }
      },
      fail(err) {
        reject(err);
      },
    });
  });
}

// ============================================================
// 获取设备影子（当前传感器值）
// ============================================================
function getShadow() {
  return getToken().then(token => {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `https://${IOTDA_HOST}/v5/iot/${PROJECT_ID}/devices/${DEVICE_ID}/shadow`,
        method: 'GET',
        header: { 'X-Auth-Token': token },
        success(res) {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error('getShadow failed: ' + res.statusCode));
          }
        },
        fail(err) {
          reject(err);
        },
      });
    });
  });
}

// ============================================================
// 获取设备在线状态
// ============================================================
function getDeviceStatus() {
  return getToken().then(token => {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `https://${IOTDA_HOST}/v5/iot/${PROJECT_ID}/devices/${DEVICE_ID}`,
        method: 'GET',
        header: { 'X-Auth-Token': token },
        success(res) {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error('getDeviceStatus failed: ' + res.statusCode));
          }
        },
        fail(err) {
          reject(err);
        },
      });
    });
  });
}

// ============================================================
// 获取设备属性历史（单传感器，指定时间范围）
// ============================================================
function getProperties(serviceId, startTime, endTime) {
  return getToken().then(token => {
    const startTs = new Date(startTime).getTime();
    const endTs   = new Date(endTime).getTime();
    return new Promise((resolve, reject) => {
      wx.request({
        url: `https://${IOTDA_HOST}/v5/iot/${PROJECT_ID}/devices/${DEVICE_ID}/properties`,
        method: 'POST',
        header: {
          'X-Auth-Token': token,
          'Content-Type': 'application/json',
        },
        data: {
          service_id: serviceId,
          start_time: startTs,
          end_time: endTs,
        },
        success(res) {
          if (res.statusCode === 200) {
            resolve(res.data);
          } else {
            reject(new Error('getProperties failed: ' + res.statusCode));
          }
        },
        fail(err) {
          reject(err);
        },
      });
    });
  });
}

module.exports = {
  getToken,
  getShadow,
  getDeviceStatus,
  getProperties,
};
