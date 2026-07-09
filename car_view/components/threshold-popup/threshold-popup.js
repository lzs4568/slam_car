Component({
  properties: {
    visible:     { type: Boolean, value: false },
    sensor_key:  { type: String,  value: '' },
    sensor_name: { type: String,  value: '' },
    current_min: { type: Number,  value: 0 },
    current_max: { type: Number,  value: 100 },
    unit:        { type: String,  value: '' },
  },

  observers: {
    'visible, current_min, current_max'(visible, min, max) {
      if (visible) {
        this.setData({ minValue: min, maxValue: max });
      }
    },
  },

  data: {
    minValue: 0,
    maxValue: 100,
  },

  methods: {
    onClose() {
      this.triggerEvent('close');
    },

    onMinInput(e) {
      this.setData({ minValue: Number(e.detail.value) });
    },

    onMaxInput(e) {
      this.setData({ maxValue: Number(e.detail.value) });
    },

    onSave() {
      const { minValue, maxValue } = this.data;
      if (minValue >= maxValue) {
        wx.showToast({ title: '最小值必须小于最大值', icon: 'none' });
        return;
      }
      this.triggerEvent('save', { min: minValue, max: maxValue });
    },
  },
});
