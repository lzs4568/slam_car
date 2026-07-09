Component({
  properties: {
    name:    { type: String,  value: '' },
    value:   { type: null,    value: null },
    unit:    { type: String,  value: '' },
    alarm:   { type: Boolean, value: false },
    decimal: { type: Number,  value: 1 },
  },

  methods: {
    onCardTap() {
      this.triggerEvent('cardtap');
    },
    onSettingTap() {
      this.triggerEvent('settingtap');
    },
  },
});
