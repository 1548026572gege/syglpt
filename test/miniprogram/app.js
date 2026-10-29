App({
  globalData: {
    // 部署时改为后端 HTTPS 域名（需 ICP 备案）；开发期可在微信开发者工具勾选"不校验合法域名"
    baseUrl: "http://192.168.1.100:8000",
    token: "",
    user: null
  },
  onLaunch() {
    this.globalData.token = wx.getStorageSync("token") || "";
    this.globalData.user = wx.getStorageSync("user") || null;
  }
});
