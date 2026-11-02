#!/usr/bin/env bash
# 实验管理平台 APK 构建脚本（WSL/Ubuntu）
set -e

export JAVA_HOME=$HOME/android-build/jdk-17.0.21+9
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH

SRC="/mnt/c/Users/18897/Desktop/生物实验室管理系统/实验管理平台"
WORK=$HOME/android-build/proj
APK_OUT="/mnt/c/Users/18897/Desktop/实验管理平台.apk"

echo "==> [1/4] 同步项目源码到 WSL"
mkdir -p "$WORK"
rsync -a --delete --exclude='build' --exclude='.gradle' "$SRC/" "$WORK/" 2>/dev/null || {
  rm -rf "$WORK"; mkdir -p "$WORK"; cp -r "$SRC/." "$WORK/"
}

echo "==> [2/4] 准备 gradle-wrapper.jar"
cp -f ~/android-build/gradle-wrapper.jar "$WORK/gradle/wrapper/gradle-wrapper.jar"
chmod +x "$WORK/gradlew"

echo "==> [3/4] Gradle 构建 assembleDebug"
cd "$WORK"
./gradlew assembleDebug --no-daemon -q

APK="$WORK/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
  echo "错误：未找到 APK 产物" >&2
  exit 1
fi

echo "==> [4/4] 复制 APK 到 Windows 桌面"
cp -f "$APK" "$APK_OUT"
ls -lh "$APK_OUT"
echo ""
echo "构建成功：$APK_OUT"
