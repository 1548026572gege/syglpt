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

/* 时间显示：2026-11-07 08:00 → 2026 年 11 月 7 日 08:00 */
function fmtDateTime(v) {
  const m = (v || "").trim().replace("T", " ").match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}:\d{2}))?/);
  if (!m) return v || "";
  const s = `${m[1]} 年 ${+m[2]} 月 ${+m[3]} 日`;
  return m[4] ? `${s} ${m[4]}` : s;
}

/* blob 转 base64（安卓 App 保存导出文件用） */
function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",")[1] || "");
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsDataURL(blob);
  });
}

/* 带鉴权的文件下载：安卓 App 走原生保存，浏览器走 <a download> */
async function downloadFile(url) {
  const resp = await fetch(url, { headers: { "Authorization": "Bearer " + getToken() } });
  if (!resp.ok) { toast("下载失败", "error"); return; }
  const dispo = resp.headers.get("Content-Disposition") || "";
  let fname = "download.xlsx";
  const star = dispo.match(/filename\*=UTF-8''([^;]+)/i);
  if (star) {
    fname = decodeURIComponent(star[1].trim());
  } else {
    const m = dispo.match(/filename="?([^";]+)"?/i);
    if (m) fname = m[1].trim();
  }
  const blob = await resp.blob();

  // 安卓 App：WebView 无法保存 blob 文件，交给原生 DownloadBridge 保存并打开
  if (window.AndroidDownload && typeof window.AndroidDownload.saveFile === "function") {
    try {
      const base64 = await blobToBase64(blob);
      window.AndroidDownload.saveFile(fname, blob.type || "application/octet-stream", base64);
    } catch (e) {
      toast("保存失败：" + e.message, "error");
    }
    return;
  }

  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------- 初中生物实验名单：选择后自动填入实验名称与材料器具 ---------- */
const BIOLOGY_EXPERIMENTS = [
  { name: "探究影响鼠妇分布的环境因素", materials: "若干只鼠妇（或蚯蚓等），湿土，铁盘（或塑料盘、纸盒等），纸板，玻璃板，电子秒表（或其他计时工具）" },
  { name: "制作并观察植物细胞临时装片", materials: "洋葱鳞片叶，碘液，显微镜，载玻片，盖玻片，镊子，刀片（使用时请注意安全），滴管，纱布，清水，擦镜纸，吸水纸" },
  { name: "观察人的口腔上皮细胞", materials: "生理盐水，碘液，一次性水杯，凉开水，无菌牙签（有钝端），滴管，纱布，镊子，吸水纸，载玻片，盖玻片，显微镜" },
  { name: "观察人体的基本组织", materials: "人体四种基本组织的永久玻片标本，显微镜" },
  { name: "观察草履虫", materials: "草履虫培养液，显微镜，放大镜，纱布，镊子，载玻片，盖玻片，滴管，少许棉花纤维" },
  { name: "观察种子的结构", materials: "浸软的菜豆种子（或大豆、蚕豆等）和玉米种子，碘液，放大镜，刀片（使用时请注意安全），滴管" },
  { name: "探究种子萌发的环境条件", materials: "培养皿、吸水纸、标签纸、胶水、清水、种子" },
  { name: "观察根毛和根尖的结构", materials: "显微镜、放大镜、镊子、培养皿、根尖的永久切片、已经长出根毛的幼苗" },
  { name: "观察和解剖花的结构", materials: "桃花（洋桔梗花或其他类似的花），放大镜，解剖刀，镊子，培养皿，胶带纸、解剖针、铅笔、尺子、小木板" },
  { name: "观察叶片横切面结构", materials: "新鲜叶片；显微镜，双面刀片（两片，并排在一起，一侧用胶布粘牢），镊子，载玻片，盖玻片，盛有清水的培养皿，滴管，吸水纸，纱布，毛笔，小木板" },
  { name: "制作并观察叶片下表皮的临时装片", materials: "新鲜叶片（如菠菜、蚕豆叶片）、显微镜、镊子、载玻片、盖玻片、滴管、吸水纸、纱布" },
  { name: "绿叶在光下制造有机物", materials: "已经过预处理的铜钱草叶片（或天竺葵等）（保留遮光的黑纸片）、酒精、碘液、小烧杯、培养皿、镊子、清水、恒温水浴锅（或酒精灯、大烧杯、三脚架、陶土网、火柴）" },
  { name: "测定某种食物中的能量", materials: "花生种子（或者其他种子），水，锥形瓶，铁架台，温度计，酒精灯，电子天平，解剖针，火柴，陶土网（石棉网）" },
  { name: "探究口腔对馒头的消化作用", materials: "新鲜馒头块，碘液，凉开水，小试管3支，标签纸，量筒，小烧杯，镊子，玻璃棒，试管刷，滴管，恒温水浴锅，刀片，垫板" },
  { name: "观察人血的永久涂片", materials: "人血的永久涂片，显微镜" },
  { name: "观察小鱼尾鳍内血管及血液的流动", materials: "尾鳍色素少的活的小鱼，显微镜，培养皿，滴管，棉絮(纱布)，载玻片，烧杯" },
  { name: "检测不同环境中的细菌和真菌", materials: "硬币、已高温灭菌的装有牛肉汁培养基的培养皿、标签纸、笔、无菌棉棒、蒸馏水" },
  { name: "观察酵母菌", materials: "酵母菌培养液；显微镜，擦镜纸，纱布，镊子，吸水纸，滴管，载玻片，盖玻片，碘液" },
  { name: "观察霉菌", materials: "青霉，显微镜，放大镜，纱布，镊子，解剖针，吸水纸，滴管，载玻片，盖玻片" },
  { name: "模拟人的性别决定过程", materials: "黑围棋子（10粒）、白围棋子（30粒）、纸盒（2个）" },
  { name: "探究酒精对水蚤心率的影响", materials: "活水蚤，显微镜、纱布、计数器，计时工具（带倒计时功能）、小烧杯，滴管，载玻片、盖玻片，酒精(10%)，蒸馏水" },
];

/* 下拉选项：0 = 手动填写；传入已选名称可自动选中 */
function experimentOptions(selectedName) {
  const opts = BIOLOGY_EXPERIMENTS.map((e, i) =>
    `<option value="${i + 1}" ${e.name === selectedName ? "selected" : ""}>${i + 1}、${esc(e.name)}</option>`).join("");
  return `<option value="">— 手动填写 / 从初中实验名单选择 —</option>${opts}`;
}

/* 选中名单后自动填入名称与材料器具 */
function fillExperiment(selectEl, nameId, materialId) {
  const idx = Number(selectEl.value);
  if (!idx) return;
  const e = BIOLOGY_EXPERIMENTS[idx - 1];
  if (!e) return;
  const nameEl = document.getElementById(nameId);
  const matEl = document.getElementById(materialId);
  if (nameEl) nameEl.value = e.name;
  if (matEl) matEl.value = e.materials;
}
