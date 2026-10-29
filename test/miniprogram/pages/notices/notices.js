const { request } = require("../../utils/api");
Page({
  data: { list: [] },
  onShow() { this.load(); },
  async load() {
    try { this.setData({ list: await request("/api/notices") }); } catch (e) {}
  }
});
