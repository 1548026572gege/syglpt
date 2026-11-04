const { request, formatDateTime } = require("../../utils/api");
Page({
  data: { list: [] },
  onShow() { this.load(); },
  async load() {
    try {
      const list = await request("/api/notices");
      this.setData({ list: list.map(n => ({
        ...n, time_text: formatDateTime(n.experiment_time), created_text: formatDateTime(n.created_at)
      })) });
    } catch (e) {}
  }
});
