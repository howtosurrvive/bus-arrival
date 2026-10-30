#!/bin/bash
# 打包 APK。工具链在 D 盘，源码在本目录。
#   D:\dev\jdk17        JDK 17
#   D:\dev\android-sdk  build-tools 34.0.0 + platforms/android-34
set -e

BASE=/d/dev
JDK="$BASE/jdk17/jdk-17.0.20.1+1"
SDK="$BASE/android-sdk"
BT="$SDK/build-tools/34.0.0"
ANDROID_JAR="$SDK/platforms/android-34/android.jar"
OUT="build"

export PATH="$JDK/bin:$PATH"
JAVA="$JDK/bin/java.exe"

# 电脑的局域网地址，写进 App 当默认值（手机在同一 WiFi 下就免配置）
DEF_IP="${1:-}"
if [ -z "$DEF_IP" ]; then
  DEF_IP=$(python -c "
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
try:
    s.connect(('223.5.5.5',80)); print(s.getsockname()[0])
except Exception: print('')
finally: s.close()" 2>/dev/null)
fi
DEF_SERVER=""
[ -n "$DEF_IP" ] && DEF_SERVER="http://$DEF_IP:8765"

echo "==> 默认服务器地址: ${DEF_SERVER:-（留空，装好后手填）}"

rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex" "$OUT/src"

# 0. 图标：跟网页配色同源，形状一致，只换底色。
#    第二个参数选 deep / warm / sky，要跟默认配色对上：
#    深蓝 c → deep（默认）、暖橘 d → warm、晴空 e → sky。
ICON_V="${2:-deep}"
python - "$ICON_V" <<'PY'
import sys
sys.path.insert(0, "../bus-app")
import server
v = sys.argv[1]
for sz, d in ((192, "res/mipmap-xxhdpi"), (96, "res/mipmap-hdpi")):
    open(d + "/ic_launcher.png", "wb").write(server._png_icon(sz, v))
open("../dist/icon-192.png", "wb").write(server._png_icon(192, v))
print("==> 图标已更新（%s）" % v)
PY

# 1. 生成一份改了默认地址的 Prefs.java
sed "s|@DEFAULT_SERVER@|$DEF_SERVER|" src/com/leina/bus/Prefs.java > "$OUT/src/Prefs.java"
for f in src/com/leina/bus/*.java; do
  [ "$(basename "$f")" = "Prefs.java" ] && continue
  cp "$f" "$OUT/src/"
done

# 2. 资源
"$BT/aapt2.exe" compile --dir res -o "$OUT/res.zip"
"$BT/aapt2.exe" link \
  -o "$OUT/base.apk" \
  -I "$ANDROID_JAR" \
  --manifest AndroidManifest.xml \
  -R "$OUT/res.zip" \
  --java "$OUT/gen" \
  --min-sdk-version 21 \
  --target-sdk-version 34 \
  --version-code 1 \
  --version-name 1.0.0 \
  --auto-add-overlay
echo "==> 资源编译完成"

# 3. javac
if ! "$JDK/bin/javac.exe" --release 8 -nowarn -encoding UTF-8 \
  -classpath "$ANDROID_JAR" \
  -d "$OUT/classes" \
  "$OUT/src"/*.java "$OUT/gen"/com/leina/bus/R.java > "$OUT/javac.log" 2>&1; then
  echo "！！Java 编译失败："
  cat "$OUT/javac.log"
  exit 1
fi
echo "==> Java 编译完成"

# 4. dex
CLASSES=$(find "$OUT/classes" -name "*.class" | tr '\n' ' ')
"$JAVA" -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \
  --lib "$ANDROID_JAR" --release --min-api 21 \
  --output "$OUT/dex" $CLASSES
echo "==> dex 生成完成"

# 5. 把 classes.dex 塞进 apk
python - "$OUT/base.apk" "$OUT/dex/classes.dex" <<'PY'
import sys, zipfile
apk, dex = sys.argv[1], sys.argv[2]
z = zipfile.ZipFile(apk, 'a', zipfile.ZIP_DEFLATED)
z.write(dex, 'classes.dex')
z.close()
print("   dex 已入包")
PY

# 6. 对齐
"$BT/zipalign.exe" -f 4 "$OUT/base.apk" "$OUT/aligned.apk"

# 7. 签名（首次运行时生成一个本地 keystore，放在 D 盘，别删）
KS="$BASE/busapp.keystore"
if [ ! -f "$KS" ]; then
  "$JDK/bin/keytool.exe" -genkeypair -v -keystore "$KS" \
    -alias bus -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass bus123456 -keypass bus123456 \
    -dname "CN=LeiNa Valve, OU=Bus, O=LeiNa, L=Wenzhou, ST=Zhejiang, C=CN" >/dev/null 2>&1
  echo "==> 新建签名文件 $KS"
fi

"$JAVA" -jar "$BT/lib/apksigner.jar" sign \
  --ks "$KS" --ks-pass pass:bus123456 --key-pass pass:bus123456 \
  --v1-signing-enabled true --v2-signing-enabled true \
  --out "$OUT/bus-1.0.0.apk" "$OUT/aligned.apk"

"$JAVA" -jar "$BT/lib/apksigner.jar" verify "$OUT/bus-1.0.0.apk"
echo "==> 签名校验通过"

# 8. 归档到 dist/，并记下校验值与证书指纹（手机下载页要显示这两样）
mkdir -p ../dist
cp "$OUT/bus-1.0.0.apk" "../dist/bus-arrival-1.0.0.apk"
"$JAVA" -jar "$BT/lib/apksigner.jar" verify --print-certs "../dist/bus-arrival-1.0.0.apk" > "$OUT/certs.txt"
python - "$OUT" <<'PY'
import hashlib, json, os, re, sys, datetime
out = sys.argv[1]
apk = os.path.join(os.path.dirname(out), "..", "dist", "bus-arrival-1.0.0.apk")
apk = os.path.abspath(apk)
data = open(apk, "rb").read()
cert = ""
for line in open(os.path.join(out, "certs.txt"), encoding="utf-8", errors="ignore"):
    if "SHA-256 digest" in line:
        cert = line.split("digest:")[1].strip()
        break
info = {
    "file": os.path.basename(apk),
    "version": "1.0.0", "versionCode": 1,
    "size": len(data),
    "sha256": hashlib.sha256(data).hexdigest(),
    "cert": cert, "signed": "v1+v2",
    "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
}
p = os.path.join(os.path.dirname(apk), "apk-info.json")
open(p, "w", encoding="utf-8").write(json.dumps(info, ensure_ascii=False, indent=2))
print("==> dist/apk-info.json 已更新")

# 文件名带上哈希：同名文件被替换时，GitHub/CDN 会把旧内容缓存住，
# 用户会下到旧包，页面上「对不上就别装」就成了空话。名字唯一就不会错配。
import glob, shutil
dist_dir = os.path.dirname(apk)
sha8 = info["sha256"][:8]
newname = "bus-arrival-%s-%s.apk" % (info["version"], sha8)
target = os.path.join(dist_dir, newname)
shutil.copyfile(apk, target)          # 先复制，再清理旧的
for f in glob.glob(os.path.join(dist_dir, "bus-arrival-*.apk")):
    if os.path.abspath(f) != os.path.abspath(target):
        os.remove(f)
print("==> dist/%s" % newname)

# 把下载页上的文件名、校验值、证书指纹同步过来
idx = os.path.abspath(os.path.join(os.path.dirname(apk), "..", "index.html"))
try:
    html = open(idx, encoding="utf-8").read()
    html = re.sub(r"bus-arrival-[0-9.]+(-[0-9a-f]{8})?\.apk", newname, html)
    html = re.sub(r"(对不上就别装<br><code>)[0-9a-f]{64}", r"\g<1>" + info["sha256"], html)
    html = re.sub(r"(证书指纹<br><code>)[0-9a-f]{64}", r"\g<1>" + cert, html)
    open(idx, "w", encoding="utf-8").write(html)
    print("==> index.html 上的文件名 / SHA-256 / 证书指纹已同步")
except Exception as e:
    print("!! 同步 index.html 失败：", e)
PY

ls -lh "$OUT/bus-1.0.0.apk" ../dist/
