# 交接报告 —— 公交到站（老人版）

> 写给下一个接手的人（包括换一台设备继续干的他自己）。
> 最后更新：2026-10-30　版本：网页 V1.0 / 安卓壳 V1.0.0

---

## 一、这东西是干什么的

给家里老人用的公交车到站查询。老人要解决的问题只有一个：

> **36 路还有几站到石坦？我该什么时候出门？**

所以全部设计都围着这一句话转：字大、按钮少、不用注册、不看广告、三步查完。

**不做的事**：不做全城公交地图、不做换乘规划、不做用户账号、不做定位导航、不做轻轨（数据质量差，已决定去掉）。

---

## 二、现在到哪一步了

| 部分 | 状态 | 说明 |
| --- | --- | --- |
| 网页版（手机浏览器可用） | ✅ 可用 | `bus-app/启动.bat` 一键起服务，同一 WiFi 下手机浏览器就能用 |
| 查询流程 | ✅ 定稿 | 首页搜索 → 直接列出两个方向 → 点方向 → 到站卡片 |
| 白卡界面 | ✅ 定稿 | `skins.py` 里的 skin `c`（白卡 + V2 优化层） |
| 手机配色可选 | ✅ 可用 | 设置面板里三套（深蓝 / 暖橘 / 晴空），选完记在 cookie 里 |
| 点站看到达时间 | ✅ 可用 | 在到站卡片里点任意一站，看车还有几站/几分钟到那一站 |
| 到站响铃（页面开着时） | ✅ 可用 | 网页合成音 + 震动 + 横幅 |
| **到站响铃（App 在后台）** | ✅ V1.0.0 已打通 | 安卓壳 + 前台服务轮询，`dist/bus-arrival-1.0.0-<sha8>.apk` |
| 安装包分发 | ✅ 可用 | 打 tag 自动发 Release，手机可直链下载（见 7.4） |
| 语音输入 | ⏸ 暂缓 | 老人念不准（「石坦站」说成「石坦村」），要做近义词匹配再说 |
| 定位「附近站牌」 | ⏸ 暂缓 | 家到石坦两个站台只隔 46 米，定位分不出来；先留接口 |

---

## 三、目录结构

```
项目根/
├── bus-app/                  网页版 + 本地服务（核心）
│   ├── server.py             单文件：Python 标准库 HTTP 服务 + 接口 + 页面 JS
│   ├── skins.py              界面皮肤：白卡 c / 暖橘 d / 晴空 e（+ 老皮肤 a、b）+ 配色映射表
│   └── 启动.bat              双击启动（会把局域网地址打印出来）
├── android/                  安卓壳（让响铃能在后台响）
│   ├── AndroidManifest.xml
│   ├── src/com/leina/bus/
│   │   ├── MainActivity.java WebView 壳 + 设置页 + 给网页的桥
│   │   ├── BusService.java   前台服务：轮询 + 响铃 + 通知
│   │   ├── Api.java          调本地服务 /api/board
│   │   └── Prefs.java        地址、线路、方向、站点、阈值（SharedPreferences）
│   ├── res/                  图标与文案
│   └── build.sh              一条命令打包 APK
├── dist/
│   ├── bus-arrival-1.0.0-<sha8>.apk   成品；文件名带哈希（见 7.4）
│   ├── apk-info.json         大小 / SHA-256 / 证书指纹，build.sh 自动生成
│   └── icon-192.png
├── .github/workflows/
│   ├── release.yml           打 tag 自动发 Release（安装包作为附件）
│   └── pages.yml             自动把下载页发到 GitHub Pages（只发页面和 apk）
├── index.html                对外的手机下载页（Pages 发布的是它的 site/ 副本）
├── APK安装与测试.html        手机端安装与验收步骤
├── 手机测试清单.html          人工验收清单
├── 查询流程说明.html          交互规格（改 UI 前必读）
├── 老人版公交App方案.html     立项期方案论证（历史文档，决策由来）
├── 老人版公交_离线演示.html   不联网也能看的界面演示
├── README.md                 快速上手
└── HANDOFF.md                本文件
```

---

## 四、怎么跑起来

### 4.1 网页版

1. 电脑装 Python 3（**第一步必须勾 "Add python.exe to PATH"**）
2. 双击 `bus-app/启动.bat`
3. 窗口里会打印两行地址：`http://127.0.0.1:8765`（电脑自己用）和
   `http://192.168.x.x:8765`（手机用）
4. 手机连**同一个 WiFi**，浏览器打开第二个地址

> 手机打不开？八成是 Windows 防火墙拦了 8765 端口。允许 Python 通过专用网络即可。
> 数据全部由电脑上的这个服务转发到 `h5.mygolbs.com`，所以电脑不开，手机就查不了。

### 4.2 安卓 App

安装包在 `dist/bus-arrival-1.0.0-<sha8>.apk`（文件名里的哈希见 7.4）。传到手机的方式有三种：

- **手机上直接下载**（推荐）：打开 `index.html` 这个下载页（Pages 地址见 7.4），点按钮；
  或直接用 Release 直链：
  `https://github.com/howtosurrvive/bus-arrival/releases/download/v1.0.1/bus-arrival-1.0.0-624ec3d1.apk`
- **电脑传过去**：微信「文件传输助手」发给自己、数据线拷、网盘，都行；
- **数据线直连**（手机开了 USB 调试时）：`adb install dist/bus-arrival-*.apk`，
  顺便 `adb reverse tcp:8765 tcp:8765`，手机就能用 `http://127.0.0.1:8765` 访问电脑上的服务，
  绕开「手机和电脑不在同一网段」的问题。adb 在 `D:\dev\platform-tools`。

装上之后：

1. 手机上点安装（会提示「未知来源」，允许一次）
2. 打开「公交到站」，默认地址已经写好了；连不上就点「改地址」填电脑上的那个地址
3. 进到站卡片 → 右上角「到站响铃」→ 选 2 站 / 3 站 / 5 站

**后台响铃怎么发生的**：网页把「看哪条线、还剩几站响」通过 `AndroidBridge` 交给原生层 →
原生前台服务每 30 秒问一次本地服务 → 到条件就响铃 + 震动 + 弹通知。
网页自己被切后台冻结了也不影响，因为真正干活的是原生服务。

---

## 五、数据从哪来

全部来自掌上公交的公开接口，**没有第三方依赖库**（Python 标准库直接发 HTTP 请求）。

- 接口地址：`https://h5.mygolbs.com/ApiData.do`
- 城市：`温州市`
- 常用命令号：

| CMD | 干什么 | 缓存在哪 |
| --- | --- | --- |
| 103 | 线路站表（上下行站序） | 长缓存，站表基本静态 |
| 104 | 该方向在途车辆（车开到第几站） | 短缓存 |
| 110 | 站名搜索 | 短 |
| 114 | 线路搜索 | 短 |
| 115 | 某站所有经过线路的实时到站 | 短 |
| 209 | 同名站台坐标（马路哪一侧） | 短 |

> 接口属于第三方公开服务，**没有公开的稳定性承诺**。哪天真挂了，改的是
> `server.py` 里 `api_post()` 上面的 `API` 常量 —— 换成别的数据源时，
> 只要把 `fetch_station_lines / fetch_stops / fetch_buses` 三个函数返回结构保住，
> 页面一行都不用改。

### 5.1 本地服务的接口契约

浏览器和安卓壳都只跟这 8 个接口打交道，不直接碰上游。路由在 `server.py` 的 `do_GET`：

| 接口 | 参数 | 返回 | 谁在用 |
| --- | --- | --- | --- |
| `/` | `?skin=c\|d\|e`；无参数时读 cookie `sk` | 整页 HTML | 浏览器 / WebView |
| `/api/board` | `line`、`dir`(1\|2)、`station` | 到站卡片（见下） | WebView、安卓后台服务 |
| `/api/station` | `name` | 某站所有线路的实时到站 | 站牌页 |
| `/api/line` | `name`、`dir`、`focus` | 一条线一个方向的完整站表 | 逐站详情页 |
| `/api/home` | 无 | 首页站牌列表 | 首页 |
| `/api/dirs` | `line`、`station` | 一条线的两个方向 | 选方向那一步 |
| `/api/search` | `kw` | 搜线路 / 搜站名（各截断 10 / 8 条） | 搜索页 |
| `/api/platforms` | `station` | 同名站台坐标 | 未接（定位用） |

`/api/board` 的返回结构（安卓壳 `Api.java` 只取其中 4 个字段）：

```json
{
  "ok": true,
  "station": "石坦",
  "line": "36路", "dir": "1",
  "main":  { "status": "coming", "stations": 17, "minutes": 28,
             "toShort": "浙南科技城", "node": "17站", "dist": "28分钟/9.3公里",
             "order": 29 },
  "other": { "status": "waiting", "stations": null, "minutes": null,
             "toShort": "九山", ... },
  "win":  { "rows": [ {"i": 1, "name": "...", "mine": false, "bus": false} ] },
  "passes": true,        // 这条线是否经过这个站
  "total": 40,
  "hasReal": true,
  "updated": "16:42"
}
```

`status` 的取值只有这几个：`coming`（在途，有分钟和站数）、`here`（就在本站）、
`waiting`（等待发车）、`passed`（已过站）、`closed`（收班）、`unknown`（查不到）、
`noroute`（这站不走这条线）。**安卓壳的响铃判断完全依赖 `status` 与 `stations`**，
改这两个字段的含义会直接影响后台响铃。

### 5.2 硬编码配置项

现在**没有任何环境变量**，全部是 `server.py` 顶部的常量（要改就改这里，然后重启服务）：

| 常量 | 当前值 | 含义 |
| --- | --- | --- |
| `API` | `https://h5.mygolbs.com/ApiData.do` | 上游接口 |
| `CITY` | `温州市` | 城市名，换城市改这里 |
| `HOME_STATION` | `石坦` | 首页默认站点 |
| `HOME_LINE` | `36路` | 默认线路 |
| `PORT` | `8765` | 本地服务端口 |
| `SEARCH_MAX_LINES` / `SEARCH_MAX_STATIONS` | `10` / `8` | 搜索结果截断 |

安卓侧的配置在 `Prefs.java`（SharedPreferences，5 个字段：`server`/`line`/`dir`/`station`/`at`），
其中 `server` 的默认值由 `build.sh` 在打包时写死成本机局域网地址。

### 5.3 本项目没有数据库

全部状态都在内存和手机本地存储里，没有 schema、没有迁移、没有持久化。
**别去找数据库结构**，也别为了「存历史记录」引入数据库 —— 需求里没有这件事。

---

## 六、代码地图

### 6.1 `bus-app/server.py`（约 1750 行，Python）

```
常量       CITY / HOME_STATION(石坦) / HOME_LINE(36路) / PORT(8765)
工具       api_post() 发请求并解析 JSON
           _minutes/_meters/_num   把「小于1分钟」「9.3公里」这类文本解析成数
           _status()               把接口的节点状态归一成 coming/here/waiting/...
           short_name()            去掉「(不用于上下客)」这类括号、去掉「首末站」后缀
取数       fetch_station_lines()   CMD115  某站所有线路的实时到站
           fetch_stops()           CMD103  某线某方向的站序
           fetch_buses()           CMD104  在途车辆
           fetch_platforms()       CMD209  站台坐标
组装       window_stops()          截出「我附近 ±5 站」的窗口；只收车还没过的
           build_home()             首页：站牌列表
           build_board()            到站卡片数据（本项目的主对象）
           build_station()          某个站有哪些车
           build_dirs()             一条线的两个方向（搜线路时用）
           build_line()             一条线一个方向的完整详情
           build_search()           搜线路 / 搜站名（各截断 10 / 8 条，带排序）
页面       page_html()             组 HTML（CSS 来自 skins.py，JS 是常量）
           JS 常量                 页面全部前端逻辑，见下
HTTP       Handler.do_GET          路由：/ /api/* /icon.png /manifest.json /demo /_preview
```

**前端 JS 的关键函数**（都在 `server.py` 的 `JS` 常量里）：

```
viewHome()      首页（站牌列表 + 搜索框）
viewBoard()     到站卡片（进线路详情后看到的那个页面）
viewStation()   站牌页（某站所有车）
viewSearch()    搜索结果页
homeCard()      生成到站卡片的 HTML
checkRemind()   每轮轮询后判断要不要响铃
pickAt(n)/turnOff()  响铃阈值设置
syncWatch()     ★ 新增：把「看哪条线、响几站」同步给安卓壳
bridge()        ★ 新增：检测 AndroidBridge，没有就静默跳过
centerMyStop()  把「你在这」滚到屏幕合适的位置
```

### 6.2 `bus-app/skins.py`

皮肤都基于白卡的 CSS，只换颜色不改布局。**用户能选的是三套**（其余是历史遗留，只在地址栏手动指定时可用）：

| key | 是什么 | 用户能选 | 怎么切 |
| --- | --- | --- | --- |
| `c` | **默认**：白卡 + V2 优化层，深蓝 | ✅ 深蓝 | 默认 / `?skin=c` |
| `d` | 暖橘（底色暖白、主色深橘棕） | ✅ 暖橘 | `?skin=d` |
| `e` | 晴空（底色冷白、主色亮蓝，橙红点缀） | ✅ 晴空 | `?skin=e` |
| `a` | 早期白卡（无 V2 优化层） | — | `?skin=a` |
| `b` | 深色版 | — | `?skin=b` |

`d` / `e` 由 `_tint(css, 映射表)` 一次性正则替换 hex 生成（`_THEME_WARM` / `_THEME_SKY`），
**不复制 CSS、不改任何布局**。加一套新配色的成本就是再写一张颜色映射表，
再把 key 加进 `THEME_CHOICES`（设置面板里的按钮就自动多一个）。

**用户在设置里换色**（`设置 → 手机配色`）：
- 面板按钮由 `THEME_CHOICES` 生成，点击走 JS 的 `setSkin(v)`
- 写 cookie `sk=c|d|e`（一年有效），然后 `location.replace(pathname + hash)` 重进页面
- 服务端 `do_GET` 的 `/` 分支按 **`?skin=` ＞ cookie ＞ `DEFAULT_SKIN`** 决定用哪套
- 用 cookie 不用网址参数，是为了换色后**还停在原来那一页**（hash 不丢）；`setSkin` 顺手清掉地址里的 `?skin=`，否则从对比链接进来的人换了色、刷新还是老配色
- 当前皮肤会写在 `<body data-sk="...">` 上，前端 `curSkin()` 读它来标记选中态

白卡（`c`）配色：底 `#FAFAF7`、卡片纯白、主字 `#1A1C1E`、线路蓝 `#0E3A63`、紧急橙 `#DA6B1C`、正常绿 `#1F9E5A`。

**图标**：`server.py` 的 `_png_icon(size, variant)` 用标准库直接画 PNG，造型是圆润小巴
（白色车身 + 两只圆窗 + 黄色车头灯带 + 两个轮子）。`variant` 取 `deep` / `warm` / `sky`，
与皮肤一一对应（`c→deep`、`d→warm`、`e→sky`），页面的 favicon 与 `theme-color` 会跟着皮肤变。
`build.sh` 打包时按第二个参数重画 App 图标，默认 `deep`（对上默认的深蓝）。

> 换 APK 图标时要跟默认配色对上：用户把默认改成暖橘，打包就传 `warm`。
> 手机桌面的图标是装的时候定的，网页里换色不会改桌面图标 —— 这是正常的。

三套配色的对照图在根目录 `配色比较.png`（可直接发人），细版在 `配色方案对比.html`。

### 6.3 `android/src/com/leina/bus/`

| 文件 | 职责 |
| --- | --- |
| `MainActivity.java` | WebView 壳；首次启动显示地址设置页；连不上显示自救页；`Bridge` 类是网页能调的 4 个方法：`setWatch / getWatch / server / settings` |
| `BusService.java` | 前台服务。状态栏常驻一行「正在看着 36 路·石坦站」；每 30 秒轮询；到条件响铃（ToneGenerator 走闹钟音量）+ 震动 + 通知 |
| `Api.java` | 只做一件事：问 `http://<地址>/api/board?line=&dir=&station=`，解析成 `Board{status, stations, minutes, toShort}` |
| `Prefs.java` | 五个字段：server / line / dir / station / at |

**网页 ↔ 原生的桥**（`server.py` 的 `JS` 里）：

```js
function bridge(){ return (typeof AndroidBridge !== "undefined") ? AndroidBridge : null; }
```

浏览器里没有这个对象 → 所有调用静默跳过，**网页行为一行不变**。
App 里则会在进到站卡片时调 `setWatch(line, dir, station, 阈值)`，
阈值变化（`pickAt`/`turnOff`）时再同步一次。

---

## 七、怎么打包 APK

### 7.1 工具链（已经装在 D 盘）

```
D:\dev\jdk17\jdk-17.0.20.1+1     JDK 17（Temurin）
D:\dev\android-sdk\build-tools\34.0.0   aapt2 / d8 / zipalign / apksigner
D:\dev\android-sdk\platforms\android-34\android.jar
D:\dev\busapp.keystore            签名密钥（别删，删了更新装不上）
```

> 不用 Gradle、不用 Android Studio、不用联网下依赖 —— 一条 `build.sh` 全搞定，
> 一分钟出包。改一行 Java 就能出包，是这个方案最大的好处。

### 7.2 命令

```bash
cd android
bash build.sh              # 自动探测本机 IP 写进默认地址
bash build.sh 192.168.1.9  # 手动指定
```

产物：`android/build/bus-1.0.0.apk`，同时归档到 `dist/bus-arrival-1.0.0-<sha8>.apk`
（`<sha8>` = 该包 SHA-256 的前 8 位，脚本自动算，见 7.4）。

`build.sh` 干的事（和 Gradle 等价，只是手写）：

```
aapt2 compile/link   资源 + AndroidManifest → base.apk + R.java
javac --release 8    Java → class
d8                   class → classes.dex
zip                  classes.dex 塞进 base.apk
zipalign -f 4        对齐
apksigner sign       用 D:\dev\busapp.keystore 签名（v1+v2）
再拷一份到 dist/，写 apk-info.json，并改写 index.html 里的文件名与校验值
```

### 7.3 换设备重新装工具链

1. JDK 17：清华镜像 `https://mirrors.tuna.tsinghua.edu.cn/Adoptium/17/jdk/x64/windows/`
   （GitHub 的 release 直连在这台机器上不通，别在那儿耗时间）
2. build-tools：`https://dl.google.com/android/repository/build-tools_r34-windows.zip`
   解压后目录名是 `android-14`，**要改名成 `34.0.0`** 再放进 `build-tools/`
3. platform：`https://dl.google.com/android/repository/platform-34-ext7_r03.zip`
   解压后是 `android-34`，放进 `platforms/`
4. 签名密钥丢了就用 `keytool` 重新生成一个（换密钥会导致覆盖安装失败，先卸载再装）

### 7.4 发版流程与版本约定

```bash
cd android && bash build.sh      # 出包，并自动同步 dist/ 与下载页
git add -A && git commit -m "..."
git push origin master
git tag -f -a v<版本号> -m "..." && git push --force origin refs/tags/v<版本号>
```

推完 tag，`release.yml` 会自动建一条 Release 并把安装包作为附件传上去。

三条约定，改之前先看一眼：

1. **文件名带哈希**（`bus-arrival-1.0.0-<sha8>.apk`）。因为 GitHub 与 CDN 会缓存同名文件 ——
   同名覆盖后用户会下到旧包，页面上的 SHA-256 就对不上。名字唯一就不会错配。
2. **不要手改下载页上的哈希和证书指纹**，`build.sh` 会自动改写。手改必然对不上。
3. **仓库 tag 与 APK 版本号目前不对齐**：tag 是 `v1.0.1`，包内 `versionName` 是 `1.0.0`。
   历史 tag 不动（改了 Release 链接会全失效）；**往后打 tag 用 APK 的真实版本号**，
   并同步改 `android/build.sh` 里的 `version-code` / `version-name` 和 `Prefs` 的默认地址。

### 7.5 改完必跑的三条校验

项目没有自动化测试（不想为它新增一堆实体），靠这三条守住底线：

```bash
# 1. Python 语法
python -c "import ast;ast.parse(open('bus-app/server.py',encoding='utf-8').read())"

# 2. 前端 JS 语法（server.py 里的 JS 常量导出后校验）
cd bus-app && python -c "
import server; open('_p.js','w',encoding='utf-8').write(server.JS)" && node --check _p.js && rm _p.js

# 3. 服务起得来，接口返回的是事实不是编的
cd bus-app && python server.py &
curl -s "http://127.0.0.1:8765/api/board?line=36路&dir=1&station=石坦"
# 看 main.status / main.stations / main.minutes 是否自洽：
# 有分钟数时 stations 不能是 null；stations 不该是负数或离谱的大数
```

改安卓侧则多一条：`cd android && bash build.sh` 必须跑通（编译 + 签名 + 校验通过）。

---

## 八、几个关键决定（改之前先看一眼，别走回头路）

1. **不拆别人的 APK、不去广告、不重签名。** 侵权且不稳。自己写一层壳，数据走公开接口。
2. **不重定位、不自建小程序。** 定位在局域网 http 页面上浏览器不给权限；小程序审核和开发成本都不划算。
3. **接口层全在 Python 一侧。** 网页和 App 共用同一套逻辑，改数据解析只改一个文件。
4. **响铃阈值用「还有几站」而不是分钟。** 温州堵车，分钟数不可信；站数是硬的。
5. **`build_board` 里 `bus_at` 只收 `index < focus` 的车。** 早先用 `<=`，会出现
   「还有 18 站」和「车在本站」同时显示的自相矛盾。
6. **车还有几站拿不到时，宁可显示「—」，也不编一个分钟数。**
7. **搜「5」会命中 77 条线路**，所以截断到 10 条并排序，标题写「线路 10 / 共 77 条」。
8. **网页里响铃和原生响铃不能同时开。** `checkRemind()` 里 `if(bridge()) return;`，
   由原生统一负责，避免响两遍。
9. **换方向用 `replaceState`**，不往浏览历史里压记录，否则返回键会一层层退回去。

---

## 九、已知限制（不是 bug，是现状）

| 限制 | 说明 | 影响的场景 |
| --- | --- | --- |
| 电脑必须开着 | App 的数据来自电脑上的 `server.py` | 电脑关机 → App 连不上、提醒不响 |
| 手机必须和电脑同一 WiFi | 地址是局域网 IP | 出门在外就用不了 |
| 后台被杀 | 小米/华为/OPPO 会杀后台应用 | 需要在系统里给「公交到站」加「后台运行 / 省电策略白名单」 |
| 重启手机后提醒要手动恢复 | 没做开机自启 | 重启后打开一次 App 就会自动接回来 |
| 通知权限 | Android 13+ 要用户授权 | 不授权就不弹通知（铃声和震动仍会响） |
| 静音/勿扰 | 闹钟音量在勿扰下可能被拦 | 提醒时把手机调成响铃 |
| 数据源无保证 | 第三方公开接口 | 接口若改协议，要改 `server.py` 里的取数函数 |
| 轻轨没有 | 轻轨站表查得到但没有实时数据 | 已决定不做 |
| 下载页还没上线 | GitHub Pages 需要在仓库 Settings → Pages 里把 Source 选成「GitHub Actions」，`pages.yml` 才会跑 | 在此之前手机走 Release 直链下载 |
| 手机和电脑可能不在同一网段 | 电脑只有有线网卡（192.168.110.x），手机走 WiFi，网段不同就访问不到 | 用数据线 `adb reverse`，或让路由器关掉 AP 隔离 |

---

## 十、下一步建议（按性价比排）

1. **把服务搬到一个常开的机器上**（家里的小主机 / 云服务器 / NAS）。
   这一步做完，「电脑必须开着」这个最大限制就消失了，App 只剩下一个壳。
2. **开机自启 + 省电白名单引导页**：装好后弹一次提示，教用户把 App 加进白名单。
3. **接口做缓存与降级**：上游超时或返回异常时，页面要显示「暂时查不到」而不是空白。
4. **近义词匹配做语音输入**：先做「石坦村 → 石坦」这种站名纠错，再谈语音。
5. **多城市**：现在写死了「温州市」，改成按定位或手选城市即可，`CITY` 一个常量的事。

---

## 十一、换一台设备怎么接着干

```bash
git clone <仓库地址>            # 或直接下载 zip
cd <项目目录>
cd bus-app && python server.py  # 网页版立刻能跑（Python 3.8+ 即可）
```

要改界面 → 改 `bus-app/skins.py`，刷新浏览器即可。
要改数据逻辑 → 改 `bus-app/server.py` 的 `fetch_*` / `build_*`。
要改 App → 改 `android/src/com/leina/bus/*.java`，然后：

```bash
cd android && bash build.sh
```

**唯一需要重新准备的是构建工具链**（见 7.3），源码本身不依赖任何第三方包。

---

## 十二、给下一个自己的提醒

- 改完界面**一定要在真手机上再看一眼** —— 桌面浏览器和 360px 宽的手机差别很大，
  `skins.py` 里的 `V2_OVERRIDE` 就是为 374px / 359px 小屏补的断点。
- 服务端的「还有几站」是**站数**，不是分钟；分钟只是顺带给的参考值。
- 任何时候都不要在文档或代码注释里写「已发出」「客户已读」这类没法验证的话 ——
  这个项目里也一样：能验证的写事实，不能验证的写「未确认」。
