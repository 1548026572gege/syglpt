const { request, badgeClass } = require("../../utils/api");
Page({
  data: { list: [], showForm: false, labs: ["生物实验室A", "生物实验室B", "生物准备室"],
          form: { experiment_name: "", lab_index: 0, class_name: "", student_count: "", group_count: "",
                  start_time: "", end_time: "", remark: "" } },
  onShow() { this.load(); },
  async load() {
    try {
      const list = await request("/api/reservations");
      this.setData({ list: list.map(r => ({ ...r, badge: badgeClass(r.status) })) });
    } catch (e) {}
  },
  toggleForm() { this.setData({ showForm: !this.data.showForm }); },
  onInput(e) { this.setData({ ["form." + e.currentTarget.dataset.k]: e.detail.value }); },
  onLabChange(e) { this.setData({ "form.lab_index": Number(e.detail.value) }); },
  async onSubmit() {
    const f = this.data.form;
    if (!f.experiment_name || !f.start_time || !f.end_time) {
      wx.showToast({ title: "请填写实验名称与起止时间", icon: "none" }); return;
    }
    try {
      await request("/api/reservations", "POST", {
        experiment_name: f.experiment_name, lab_name: this.data.labs[f.lab_index],
        class_name: f.class_name, student_count: Number(f.student_count) || null,
        group_count: Number(f.group_count) || null,
        start_time: f.start_time, end_time: f.end_time, remark: f.remark
      });
      wx.showToast({ title: "预约已提交" });
      this.setData({ showForm: false, form: { experiment_name: "", lab_index: 0, class_name: "", student_count: "", group_count: "", start_time: "", end_time: "", remark: "" } });
      this.load();
    } catch (e) {}
  },
  onCancel(e) {
    wx.showModal({ title: "取消预约", content: "确定取消该预约吗？", success: async (res) => {
      if (!res.confirm) return;
      try { await request(`/api/reservations/${e.currentTarget.dataset.id}/cancel`, "PUT"); this.load(); } catch (err) {}
    }});
  }
});
