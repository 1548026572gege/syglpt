const { request, badgeClass } = require("../../utils/api");
Page({
  data: { kw: "", list: [] },
  onShow() { this.load(); },
  onSearch(e) { this.setData({ kw: e.detail.value }); this.load(); },
  async load() {
    try {
      const data = await request("/api/instruments?kw=" + encodeURIComponent(this.data.kw));
      this.setData({ list: data.list.map(i => ({ ...i, badge: badgeClass(i.status) })) });
    } catch (e) {}
  }
});
