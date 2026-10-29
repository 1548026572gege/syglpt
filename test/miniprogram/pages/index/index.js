Page({
  data: { user: {}, overview: {} },
  onShow() {
    const app = getApp();
    if (!app.globalData.token) { wx.reLaunch({ url: "/pages/login/login" }); return; }
    this.setData({ user: app.globalData.user || {} });
    this.loadOverview();
  },
  async loadOverview() {
    const { request } = require("../../utils/api");
    try { this.setData({ overview: await request("/api/stats/overview") }); } catch (e) {}
  },
  go(e) { wx.navigateTo({ url: "/pages/" + e.currentTarget.dataset.page + "/" + e.currentTarget.dataset.page }); },
  onLogout() {
    getApp().globalData.token = "";
    wx.removeStorageSync("token"); wx.removeStorageSync("user");
    wx.reLaunch({ url: "/pages/login/login" });
  }
});
