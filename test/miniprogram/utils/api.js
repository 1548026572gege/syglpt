// 后端 API 封装：统一携带 JWT Token
const app = getApp();

function request(url, method = "GET", data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: app.globalData.baseUrl + url,
      method,
      data,
      header: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + (app.globalData.token || "")
      },
      success(res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync("token");
          wx.reLaunch({ url: "/pages/login/login" });
          return reject(new Error("登录已过期"));
        }
        const body = res.data || {};
        if (res.statusCode >= 400 || body.code !== 0) {
          wx.showToast({ title: body.msg || "操作失败", icon: "none" });
          return reject(new Error(body.msg || "操作失败"));
        }
        resolve(body.data);
      },
      fail() {
        wx.showToast({ title: "网络异常", icon: "none" });
        reject(new Error("网络异常"));
      }
    });
  });
}

function badgeClass(status) {
  const map = {
    "正常": "badge-green", "已通过": "badge-green", "已归还": "badge-green", "已审批": "badge-green",
    "待审核": "badge-yellow", "申请中": "badge-yellow", "维修中": "badge-yellow", "报修中": "badge-yellow", "已提交": "badge-yellow",
    "已驳回": "badge-red", "损耗": "badge-red",
    "已借出": "badge-blue", "借出": "badge-blue", "已完成": "badge-blue", "已采购": "badge-blue"
  };
  return map[status] || "";
}

/* 时间显示：2026-11-07 08:00 → 2026 年 11 月 7 日 08:00；只有日期时省略时分 */
function formatDateTime(v) {
  const m = (v || "").trim().replace("T", " ").match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}:\d{2}))?/);
  if (!m) return v || "";
  const s = m[1] + " 年 " + Number(m[2]) + " 月 " + Number(m[3]) + " 日";
  return m[4] ? s + " " + m[4] : s;
}

module.exports = { request, badgeClass, formatDateTime };
