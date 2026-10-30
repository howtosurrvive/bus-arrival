#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 web/ 里由 Python 生成的那几个文件刷新一遍。

web/ 是前端的唯一真相（手机里跑的就是它）。但有三样东西的源头在 Python 里：

  · index.html 里的设置面板  ← server.py 的 REMIND_DOM
  · skins/*.css              ← skins.py 的三套配色
  · stations.json            ← bus-app/stations.json

改了其中任何一个，都要跑一次这个脚本，否则手机上还是旧的。
app.js / api-local.js 是手写的前端代码，不归这里管。

    python sync_web.py

打包时 android/build.sh 会自动调它，所以正常流程不用手动跑。
"""

import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import server          # noqa: E402
import skins           # noqa: E402

WEB = os.path.join(HERE, "web")


def main():
    os.makedirs(os.path.join(WEB, "skins"), exist_ok=True)

    # ── 三套配色
    for k in ("c", "d", "e"):
        css = skins.SKINS.get(k)
        if not css:
            print("!! 皮肤 %s 不存在，跳过" % k)
            continue
        with open(os.path.join(WEB, "skins", k + ".css"), "w", encoding="utf-8") as f:
            f.write(css)

    # ── index.html
    build = time.strftime("%m-%d %H:%M")
    html = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,'
            'maximum-scale=1,user-scalable=no,viewport-fit=cover">'
            '<meta name="theme-color" content="#FAFAF7">'
            '<title>公交到站</title>'
            '<link rel="stylesheet" href="skins/c.css" id="sk">'
            '</head><body data-sk="c" data-assets="1" data-build="' + build + '">'
            '<div id="app" style="flex:1;display:flex;flex-direction:column;'
            'overflow:hidden;min-height:0"></div>'
            + server.REMIND_DOM +
            '<script src="api-local.js"></script>\n'
            '<script src="app.js"></script></body></html>')
    with open(os.path.join(WEB, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # ── 站库
    src = os.path.join(HERE, "stations.json")
    if os.path.exists(src):
        shutil.copyfile(src, os.path.join(WEB, "stations.json"))
        size = os.path.getsize(src) / 1024.0
    else:
        size = 0

    print("web/ 已同步：index.html、skins/*.css、stations.json（%.0f KB）" % size)


if __name__ == "__main__":
    main()
