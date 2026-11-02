#!/usr/bin/env bash
set -e
export JAVA_HOME=$HOME/android-build/jdk-17.0.21+9
export PATH=$JAVA_HOME/bin:$PATH

cd ~/android-build

echo "==> 解压 cmdline-tools"
if command -v unzip >/dev/null 2>&1; then
  unzip -q -o cmdline-tools.zip
else
  python3 - <<'PYEOF'
import zipfile
zipfile.ZipFile("cmdline-tools.zip").extractall()
PYEOF
fi

mkdir -p ~/Android/Sdk/cmdline-tools
rm -rf ~/Android/Sdk/cmdline-tools/latest
mv cmdline-tools ~/Android/Sdk/cmdline-tools/latest
ls ~/Android/Sdk/cmdline-tools/latest/bin/

echo "==> 下载 gradle-wrapper.jar"
curl -sL -o gradle-wrapper.jar "https://raw.githubusercontent.com/gradle/gradle/v8.4.0/gradle/wrapper/gradle-wrapper.jar"
ls -lh gradle-wrapper.jar

echo "==> 接受许可并安装 SDK 组件"
yes | ~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null 2>&1 || true
~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"

echo "==> SDK 安装完成"
ls ~/Android/Sdk/
