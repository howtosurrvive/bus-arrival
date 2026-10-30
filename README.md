# 公交到站（老人版）

一个给家里老人用的公交车到站查询：没有广告、没有弹窗、字大、三步查完。
数据来自温州「掌上公交」的公开接口。页面和全市站库都装在 App 里，**自己上网查，不依赖电脑**；
同一套前端也能在电脑上跑（），方便改代码时预览。

## 它解决什么问题

「掌上公交」查一趟车要点四五下、还要先看广告。这里只做一件事：
**知道 36 路还有几站到石坦，该什么时候出门。**

## 站库：全市 6909 个站

`bus-app/stations.json` 是从上游线路站表汇总下来的全市站点坐标表：**6909 个站名、
13793 个站台点**，覆盖市区、苍南、泰顺、永嘉、平阳、文成、洞头。

它撑着两件事：

- **附近的站** —— 按定位筛半径内的站，不用联网查，本地算距离
- **站名搜索** —— 本地秒出，按「距离 + 名字贴合度」排，全市 163 个跨县重名的站也不会点错

要更新（上游新开站了）就重跑抓取脚本，约 40 秒：

```bash
cd bus-app
python build_stations.py          # 全量重抓
python build_stations.py --merge  # 只补新站
```

> 乐清、瑞安不在这个数据源里（上游城市清单里没有这两个条目），站库里那点坐标只是过路站。

## 三样东西

| 是什么 | 在哪 | 怎么用 |
| --- | --- | --- |
| 网页 + 本地服务 | `bus-app/` | 电脑上双击 `bus-app/启动.bat`，手机浏览器打开窗口里显示的地址 |
| 前端（手机里跑的那份） | `bus-app/web/` | `index.html` + `app.js` + `api-local.js` + `skins/` + `stations.json`，打包进 APK 的 `assets/web` |
| 安卓 App | `android/` | 装到手机上，后台也能响铃 |
| 交付物 / 说明页 | 根目录 `*.html` | 直接双击用浏览器看 |

## 装到手机上：不依赖电脑

手机安装包在 `dist/bus-arrival-1.1.0-*.apk`（约 240 KB）。

**V1.1.0 起 App 自带页面和全市站库，自己上网查，不需要电脑、不需要服务器。**
出门在外只要有网就能用。想在家走电脑（局域网更快、更省流量）也行，在设置里填地址即可。

## 电脑上跑（开发预览 / 不想装 App 时）

```
1. 电脑装 Python 3（勾上 Add to PATH）
2. 双击 bus-app\启动.bat
3. 手机连同一个 WiFi，浏览器打开 http://<电脑IP>:8765
```

## 装成 App

手机安装包在 `dist/bus-arrival-1.0.0.apk`（25 KB，已 v1+v2 签名）。

**手机上怎么下载**：仓库根目录的 `index.html` 是专门的下载页，开了 GitHub Pages 之后，
手机浏览器打开 `https://howtosurrvive.github.io/bus-arrival/` 就能下载；
不装 Pages 也能用这三条现成直链：

- https://cdn.jsdelivr.net/gh/howtosurrvive/bus-arrival@v1.0.1/dist/bus-arrival-1.0.0.apk
- https://raw.githubusercontent.com/howtosurrvive/bus-arrival/v1.0.1/dist/bus-arrival-1.0.0.apk

默认服务器地址已经写进包里，手机和电脑在同一个 WiFi 下就不用再配置。

## 打包 APK

需要 JDK 17 和 Android SDK build-tools（工具链说明见 `HANDOFF.md`）。

```bash
cd android
bash build.sh              # 自动探测本机 IP 作为默认地址
bash build.sh 192.168.1.9  # 或者手动指定
```

产物：`android/build/bus-1.0.0.apk`

## 文档

- `HANDOFF.md` —— **交接报告**：架构、代码地图、构建方法、已知限制、换设备怎么接着干
- `查询流程说明.html` —— 三步查询流程的图示
- `手机测试清单.html` —— 手机上逐项验收
- `老人版公交_离线演示.html` —— 不联网也能看的界面演示
