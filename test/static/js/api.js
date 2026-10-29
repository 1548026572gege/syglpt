/* ===== API 封装与公共 UI 组件 ===== */
const TOKEN_KEY = "bio_lab_token";
const USER_KEY = "bio_lab_user";

function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }
function getUser() { try { return JSON.parse(localStorage.getItem(USER_KEY) || "{}"); } catch (e) { return {}; } }
function isAdmin() { const r = getUser().role; return r === "admin" || r === "sysadmin"; }

async function api(url, options = {}) {
  const opts = { method: options.method || "GET", headers: {} };
  if (getToken()) opts.headers["Authorization"] = "Bearer " + getToken();
  if (options.body instanceof FormData) {
    opts.body = options.body;
  } else if (options.body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(options.body);
  }
  const resp = await fetch(url, opts);
  if (resp.status === 401) { logout(); throw new Error("登录已过期"); }
  let data;
  try { data = await resp.json(); } catch (e) { throw new Error("服务响应异常"); }
  if (!resp.ok || data.code !== 0) {
    toast(data.msg || "操作失败", "error");
    throw new Error(data.msg || "操作失败");
  }
  return data.data;
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  location.href = "/";
}

/* 需要登录的页面调用：校验 token 并填充用户信息 */
async function requireAuth() {
  if (!getToken()) { location.href = "/"; return null; }
  try {
    const user = await api("/api/profile");
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  } catch (e) { return null; }
}

/* ---------- Toast ---------- */
function toast(msg, type = "success") {
  let box = document.getElementById("toast-box");
  if (!box) { box = document.createElement("div"); box.id = "toast-box"; document.body.appendChild(box); }
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

/* ---------- Modal ---------- */
function openModal(title, bodyHtml, opts = {}) {
  closeModal();
  const mask = document.createElement("div");
  mask.className = "modal-mask show";
  mask.id = "modal-mask";
  mask.innerHTML = `<div class="modal ${opts.large ? "modal-lg" : ""}">
    <div class="modal-title">${title}</div>
    <div class="modal-body">${bodyHtml}</div>
    ${opts.hideFooter ? "" : `<div class="modal-footer">
      <button class="btn btn-outline" onclick="closeModal()">取消</button>
      <button class="btn btn-primary" id="modal-ok">确定</button>
    </div>`}
  </div>`;
  mask.addEventListener("click", e => { if (e.target === mask) closeModal(); });
  document.body.appendChild(mask);
  if (opts.onOpen) opts.onOpen();
  if (opts.onOk) document.getElementById("modal-ok").onclick = opts.onOk;
}
function closeModal() { const m = document.getElementById("modal-mask"); if (m) m.remove(); }
function formVal(id) { const el = document.getElementById(id); return el ? el.value.trim() : ""; }

/* ---------- 状态徽章 ---------- */
const STATUS_COLOR = {
  "正常": "green", "借出": "blue", "维修中": "yellow", "损耗": "red", "报废": "gray",
  "待审核": "yellow", "已通过": "green", "已驳回": "red", "已完成": "blue", "已取消": "gray",
  "申请中": "yellow", "已借出": "blue", "已归还": "green",
  "报修中": "yellow", "草稿": "gray", "已提交": "yellow", "已审批": "green", "已采购": "blue",
  "完好": "green",
};
function badge(status) {
  const color = STATUS_COLOR[status] || "gray";
  return `<span class="badge badge-${color}">${status ?? ""}</span>`;
}

/* ---------- 表格渲染 ---------- */
function renderTable(containerId, columns, rows, emptyTip = "暂无数据") {
  const box = document.getElementById(containerId);
  if (!rows || !rows.length) {
    box.innerHTML = `<div class="empty-tip">${emptyTip}</div>`;
    return;
  }
  const thead = columns.map(c => `<th>${c.title}</th>`).join("");
  const tbody = rows.map(r => "<tr class='" + (r._rowClass || "") + "'>" +
    columns.map(c => `<td>${c.render ? c.render(r) : (r[c.key] ?? "")}</td>`).join("") + "</tr>").join("");
  box.innerHTML = `<div class="table-wrap"><table class="data-table"><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table></div>`;
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* 带鉴权的文件下载 */
async function downloadFile(url) {
  const resp = await fetch(url, { headers: { "Authorization": "Bearer " + getToken() } });
  if (!resp.ok) { toast("下载失败", "error"); return; }
  const dispo = resp.headers.get("Content-Disposition") || "";
  let fname = "download.xlsx";
  const m = dispo.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  if (m) fname = decodeURIComponent(m[1].replace(/"/g, ""));
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  a.click();
  URL.revokeObjectURL(a.href);
}
