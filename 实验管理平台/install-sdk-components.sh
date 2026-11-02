#!/usr/bin/env bash
set -e
export JAVA_HOME=$HOME/android-build/jdk-17.0.21+9
export PATH=$JAVA_HOME/bin:$PATH

SDKM=$HOME/Android/Sdk/cmdline-tools/latest/bin/sdkmanager

echo "==> 修复可执行权限"
chmod -R +x $HOME/Android/Sdk/cmdline-tools/latest/bin
ls -l $SDKM

echo "==> 接受许可"
yes | $SDKM --licenses >/dev/null 2>&1 || true

echo "==> 安装 platforms;android-34 / build-tools;34.0.0 / platform-tools"
$SDKM "platforms;android-34" "build-tools;34.0.0" "platform-tools"

echo "==> 完成"
ls $HOME/Android/Sdk/
