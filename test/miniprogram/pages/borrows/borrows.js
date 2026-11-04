const { request, badgeClass, formatDateTime } = require("../../utils/api");
Page({
  data: { list: [], instruments: [], insIndex: 0, showForm: false,
          form: { quantity: "1", expect_return_time: "", purpose: "" } },
  onShow() { this.load(); },
  async load() {
    try {
      const [list, insData] = await Promise.all([
        request("/api/borrows"), request("/api/instruments")
      ]);
      this.setData({
        list: list.map(b => ({
          ...b, badge: badgeClass(b.status),
          borrow_text: formatDateTime(b.borrow_time) || "-",
          return_text: b.return_time ? formatDateTime(b.return_time)
            : (b.expect_return_time ? "预计 " + formatDateTime(b.expect_return_time) : "-")
        })),
        instruments: insData.list.filter(i => i.status === "正常" && i.quantity > 0)
      });
    } catch (e) {}
  },
  toggleForm() { this.setData({ showForm: !this.data.showForm }); },
  onInput(e) { this.setData({ ["form." + e.currentTarget.dataset.k]: e.detail.value }); },
  onInsChange(e) { this.setData({ insIndex: Number(e.detail.value) }); },
  async onSubmit() {
    const ins = this.data.instruments[this.data.insIndex];
    if (!ins) { wx.showToast({ title: "请选择仪器", icon: "none" }); return; }
    try {
      await request("/api/borrows", "POST", {
        instrument_id: ins.id, quantity: Number(this.data.form.quantity) || 1,
        expect_return_time: this.data.form.expect_return_time, purpose: this.data.form.purpose
      });
      wx.showToast({ title: "申请已提交" });
      this.setData({ showForm: false, form: { quantity: "1", expect_return_time: "", purpose: "" } });
      this.load();
    } catch (e) {}
  }
});
