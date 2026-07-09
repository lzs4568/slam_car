import * as echarts from '../../components/ec-canvas/echarts';

let chartInstance = null;

function initChart(canvas, width, height, dpr) {
  chartInstance = echarts.init(canvas, null, {
    width: width,
    height: height,
    devicePixelRatio: dpr,
  });
  canvas.setChart(chartInstance);
  return chartInstance;
}

Page({
  data: {
    sensor_key: '',
    sensor_name: '',
    unit: '',
    range: 6,
    ranges: [
      { label: '1小时', value: 1 },
      { label: '6小时', value: 6 },
      { label: '24小时', value: 24 },
    ],
    empty: false,
    ec: { onInit: initChart },
  },

  onLoad(options) {
    const { sensor_key, sensor_name, unit } = options;
    this.setData({ sensor_key, sensor_name, unit });
    wx.setNavigationBarTitle({ title: sensor_name + '历史' });
  },

  onReady() {
    this.loadHistory();
  },

  switchRange(e) {
    const range = Number(e.currentTarget.dataset.range);
    this.setData({ range }, () => this.loadHistory());
  },

  loadHistory() {
    const { sensor_key, range } = this.data;
    const now = Date.now();
    const startTs = now - range * 3600 * 1000;

    const history = wx.getStorageSync('sensor_history') || {};
    const entries = history[sensor_key] || [];
    const filtered = entries
      .filter(([ts]) => ts >= startTs)
      .sort((a, b) => a[0] - b[0]);

    if (filtered.length === 0) {
      this.setData({ empty: true });
      return;
    }

    this.setData({ empty: false });
    this.setChartData(filtered);
  },

  setChartData(dataPoints) {
    const { unit } = this.data;
    const option = {
      grid: { top: 20, bottom: 30, left: 50, right: 20 },
      xAxis: {
        type: 'time',
        axisLabel: {
          fontSize: 10,
          formatter: (value) => {
            const d = new Date(value);
            return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
          },
        },
      },
      yAxis: {
        type: 'value',
        name: unit,
        nameTextStyle: { fontSize: 10 },
        axisLabel: { fontSize: 10 },
      },
      series: [{
        type: 'line',
        data: dataPoints,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 2 },
      }],
    };

    if (chartInstance) {
      chartInstance.setOption(option);
    }
  },
});
