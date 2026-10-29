# 生物实验室管理平台

面向中小学实验室的仪器与实验业务管理系统，包含 **Web 管理后台**（Flask + HTML）与 **微信小程序** 两端，支持仪器台账、实验预约、借还、维修、报损、采购、实验报告、实验通知单、配备目录、统计报表等全流程管理。

## 功能特性

| 模块 | 说明 |
|---|---|
| 工作台 | 数据概览、待办提醒、快捷入口 |
| 仪器台账 | 仪器增删改查、批量导入/导出/打印、批量删除与清空、按筛选结果汇总总金额；字段含国资编号、分类代码、规格、单位、数量、单价、存放位置、状态、金额、备注 |
| 实验预约 | 教师预约实验室，管理员审核（通过/驳回），支持编辑、删除与时间冲突校验 |
| 仪器借还 | 借出登记、归还登记、逾期跟踪 |
| 维修管理 | 报修登记、维修进度与结果记录 |
| 报损管理 | 仪器报损申请与审核 |
| 采购管理 | 采购申请、审批与到货登记 |
| 实验报告 | 手工登记；支持标准模板导入与自定义 Excel 自动识别导入；单份/汇总导出与打印 |
| 实验通知单 | 科目、班级（可多个）、任教教师、实验时间自选、实验内容、仪器用品；表格展示、Excel 导出、单页打印 |
| 仪器配备目录 | 内置初中新版仪器配备目录（生物/物理/化学/地理/数学），支持按学科筛选、Excel 导入（兼容新旧表头）、批量与按筛选清空 |
| 统计报表 | 按分类、状态、借还与报修等维度统计 |
| 用户与日志 | 角色权限（教师 / 管理员 / 系统管理员）、操作日志审计 |

## 技术栈

- 后端：Python 3、Flask 3、Flask-SQLAlchemy
- 数据库：默认 SQLite（开箱即用），可通过环境变量切换 MySQL 5.7+
- 认证：JWT（`pyjwt`），密码使用 PBKDF2 哈希存储
- Excel：`openpyxl`（导入/导出/模板下载）
- 前端：原生 HTML + CSS + JavaScript，打印通过浏览器打印窗口生成规范表单
- 小程序：微信小程序原生框架，通过 REST API 与后端交互

## 目录结构

```
生物实验室管理系统/
├─ README.md
├─ LICENSE
├─ sync-repo.ps1                # 每 2 小时自动同步 GitHub / Gitee 的脚本
└─ test/                        # 应用主目录
   ├─ app.py                    # 应用入口（默认监听 0.0.0.0:8000）
   ├─ config.py                 # 配置（密钥、数据库、上传目录）
   ├─ models.py                 # 数据模型
   ├─ auth.py                   # 认证与权限工具
   ├─ requirements.txt          # 依赖清单
   ├─ routes/                   # API 蓝图（仪器、预约、借还、维修、报损、采购、报告、通知、目录、统计）
   ├─ templates/                # Web 管理后台页面
   ├─ static/                   # 静态资源（样式与脚本）
   ├─ miniprogram/              # 微信小程序
   └─ uploads/                  # 上传附件（运行时生成）
```

## 快速开始

```bash
cd test
pip install -r requirements.txt
python app.py
```

启动后访问：

- 本机：http://127.0.0.1:8000
- 局域网：http://<服务器IP>:8000

## 初始账号

首次启动且数据库为空时，会自动创建管理员与教师账号：

- 优先读取环境变量 `ADMIN_INIT_PASSWORD`、`TEACHER_INIT_PASSWORD`
- 未设置时随机生成，并仅在首次启动的控制台打印一次

```powershell
# 示例：通过环境变量指定初始密码
$env:ADMIN_INIT_PASSWORD = "请换成强密码"
$env:TEACHER_INIT_PASSWORD = "请换成强密码"
python app.py
```

> 首次登录后请尽快修改密码。登录页不展示任何初始账号信息。

## 配置项（环境变量）

| 变量 | 说明 | 默认值 |
|---|---|---|
| `SECRET_KEY` | 应用与 JWT 签名密钥 | 首次启动随机生成，保存到 `test/secret.key`（不入版本库） |
| `JWT_SECRET` | JWT 专用密钥 | 同 `SECRET_KEY` |
| `JWT_EXPIRE_HOURS` | 登录有效期（小时） | `12` |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///test/bio_lab.db` |
| `ADMIN_INIT_PASSWORD` | 初始管理员密码 | 随机生成 |
| `TEACHER_INIT_PASSWORD` | 初始教师密码 | 随机生成 |

MySQL 示例：

```powershell
$env:DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/bio_lab?charset=utf8mb4"
```

## Excel 导入说明

- 仪器台账模板列：`国资编号 | 分类代码 | 器材名称 | 规格 | 单位 | 数量 | 单价 | 存放位置 | 状态 | 金额 | 备注`
  - 只要"器材名称"不为空即导入；分类代码为空自动生成 `AUTO-行号`；代码重复自动加后缀（如 `-2`）
  - "金额"留空时按 `单价 × 数量` 计算
- 实验报告支持两种导入：标准模板，或按表头别名自动识别列名的自定义表格
- 配备目录导入兼容新旧两种表头结构与多学科工作表

## 微信小程序

用微信开发者工具打开 `test/miniprogram` 目录，修改 `utils/api.js` 中的服务地址为服务器局域网 IP 后即可预览与真机调试。

## 生产部署建议

```bash
pip install gunicorn pymysql
gunicorn -w 4 -b 0.0.0.0:8000 "app:app"
```

- 建议使用 MySQL 并定期备份数据库
- 通过环境变量设置 `SECRET_KEY`、初始密码等敏感配置，不要写入代码
- 反向代理（Nginx）监听 HTTPS，将 8000 端口置于内网

## 自动同步

`sync-repo.ps1` 配合 Windows 任务计划（`BioLab-Sync-GitHub`）每 2 小时执行一次：

1. 拉取 GitHub 与 Gitee 的最新提交
2. 自动提交本地改动（排除 `sync.log`）
3. 推送到 GitHub 与 Gitee

日志写入仓库根目录 `sync.log`。

## 许可证

本项目采用仓库根目录 `LICENSE` 中的许可条款。
