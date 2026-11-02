# 实验管理平台 - 安卓 APP

基于 WebView 的安卓客户端，连接生物实验室管理系统后端。

## 功能

- WebView 加载后端页面（Flask 管理端）
- 支持文件下载（Excel 导出）
- 返回键网页后退 / 双击退出
- 网络错误自动提示，可修改服务器地址
- 默认连接云服务器 `http://144.48.240.125:8000`

## 构建方法

### 方式一：Android Studio（推荐）

1. 安装 [Android Studio](https://developer.android.com/studio)
2. 打开本目录（`实验管理平台`）
3. 等待 Gradle 同步完成
4. 点击 **Build > Build Bundle(s) / APK(s) > Build APK(s)**
5. 生成的 APK 在 `app/build/outputs/apk/debug/app-debug.apk`

### 方式二：命令行构建

```powershell
# 进入项目目录
cd "c:\Users\18897\Desktop\生物实验室管理系统\实验管理平台"

# 使用 Gradle Wrapper 构建（自动下载 Gradle）
.\gradlew.bat assembleDebug

# 构建完成后 APK 位置：
# app\build\outputs\apk\debug\app-debug.apk
```

### 方式三：WSL / Linux 构建

```bash
cd "/mnt/c/Users/18897/Desktop/生物实验室管理系统/实验管理平台"
chmod +x gradlew
./gradlew assembleDebug
```

## 安装到手机

1. 将 `app-debug.apk` 复制到安卓手机
2. 手机设置 → 安全 → 允许安装未知来源应用
3. 点击 APK 安装
4. 打开「实验管理平台」APP

## 修改服务器地址

首次打开默认连接云服务器。如需修改：

1. 打开 APP → 网络错误时点击「设置」
2. 或卸载后重新安装，修改 `MainActivity.java` 中的默认地址后重新构建

## 目录结构

```
实验管理平台/
├── app/
│   ├── src/main/
│   │   ├── java/com/biolab/app/
│   │   │   ├── MainActivity.java      # 主页面（WebView）
│   │   │   └── SettingsActivity.java  # 服务器设置页
│   │   ├── res/
│   │   │   ├── layout/                # 布局文件
│   │   │   ├── values/                # 字符串/样式
│   │   │   ├── drawable/              # 图标
│   │   │   └── mipmap-*/              # 自适应图标
│   │   └── AndroidManifest.xml
│   └── build.gradle
├── gradle/wrapper/
│   └── gradle-wrapper.properties
├── build.gradle
├── settings.gradle
└── gradlew.bat
```

## 系统要求

- Android 7.0 (API 24) 及以上
- 网络权限（已自动声明）

## 注意事项

1. 当前使用 HTTP 明文传输（`usesCleartextTraffic="true"`），如后端启用 HTTPS 请移除
2. 如需发布到应用商店，请配置签名并构建 Release 版本
3. 内网穿透或公网部署时，建议配置 HTTPS 和域名
