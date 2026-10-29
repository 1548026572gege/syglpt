Page({
  data: { username: "", password: "", loading: false },
  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  async onLogin() {
    const { username, password } = this.data;
    if (!username || !password) {
      wx.showToast({ title: "请输入账号和密码", icon: "none" });
      return;
    }
    this.setData({ loading: true });
    try {
      const { request } = require("../../utils/api");
      const data = await request("/api/login", "POST", { username, password });
      getApp().globalData.token = data.token;
      getApp().globalData.user = data.user;
      wx.setStorageSync("token", data.token);
      wx.setStorageSync("user", data.user);
      wx.reLaunch({ url: "/pages/index/index" });
    } catch (e) {} finally { this.setData({ loading: false }); }
  }
});
