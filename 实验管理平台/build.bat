@echo off
chcp 65001 >nul
echo ==========================================
echo   实验管理平台 - 安卓 APP 一键构建
echo ==========================================
echo.

REM 检查 Java
java -version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Java，请先安装 JDK 17+
    echo 下载地址：https://adoptium.net/
    pause
    exit /b 1
)

echo [1/4] 检测到 Java 环境
echo.

REM 检查 Android SDK
if not defined ANDROID_HOME (
    echo [警告] 未设置 ANDROID_HOME 环境变量
    echo 尝试自动检测...
    if exist "%LOCALAPPDATA%\Android\Sdk" (
        set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk
        echo 检测到 SDK：%ANDROID_HOME%
    ) else (
        echo [错误] 未找到 Android SDK
        echo 请先安装 Android Studio 或 SDK Command Line Tools
        pause
        exit /b 1
    )
) else (
    echo [2/4] 检测到 Android SDK：%ANDROID_HOME%
)
echo.

REM 创建 gradle-wrapper.jar 如果不存在
if not exist "gradle\wrapper\gradle-wrapper.jar" (
    echo [3/4] 下载 Gradle Wrapper...
    if not exist "gradle\wrapper" mkdir gradle\wrapper
    powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/gradle/gradle/v8.4.0/gradle/wrapper/gradle-wrapper.jar' -OutFile 'gradle\wrapper\gradle-wrapper.jar'" 2>nul
    if errorlevel 1 (
        echo [错误] 下载失败，请检查网络或手动下载 gradle-wrapper.jar
        pause
        exit /b 1
    )
) else (
    echo [3/4] Gradle Wrapper 已就绪
)
echo.

echo [4/4] 开始构建 APK...
echo.

call gradlew.bat assembleDebug --no-daemon

if errorlevel 1 (
    echo.
    echo [错误] 构建失败，请检查上方错误信息
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   构建成功！
echo ==========================================
echo.
echo APK 路径：app\build\outputs\apk\debug\app-debug.apk
echo.

if exist "app\build\outputs\apk\debug\app-debug.apk" (
    echo 文件大小：
    for %%A in ("app\build\outputs\apk\debug\app-debug.apk") do echo   %%~zA 字节
    echo.
    set /p COPY=是否复制 APK 到桌面？(Y/N)
    if /i "%COPY%"=="Y" (
        copy "app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\实验管理平台.apk" >nul
        echo 已复制到桌面：实验管理平台.apk
    )
)

echo.
pause
