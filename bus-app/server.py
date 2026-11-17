#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
石坦站 · 36 路 老人版公交 V0.3
功能：首页到站 / 站牌页(该站所有线路) / 线路详情(逐站站名+换向+车在哪站)
运行: python server.py
数据源: h5.mygolbs.com 公开查询接口（仅限家庭自用，不对外分发）
"""

import json
import math
import os
import re
import socket
import struct
import threading
import time
import urllib.parse
import urllib.request
import zlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from skins import SKINS, THEME_CHOICES
except Exception as e:     # 皮肤文件是源码的一部分，缺了就是装错了 —— 别静默降级
    raise SystemExit("skins.py 导入失败（%s）：这个文件是配色的唯一来源，不能缺" % e)

API = "https://h5.mygolbs.com/ApiData.do"
CITY = "温州市"
HOME_STATION = "石坦"
HOME_LINE = "36路"
DEFAULT_SKIN = "c"         # 没选过配色时用这套（白卡 + V2 优化层）
PORT = 8765

# 这一版是什么时候起的。写进页面的 data-build，设置面板底部显示出来 ——
# 用户问「你到底改了没有」的时候，看一眼这行字就知道手机拿到的是不是新的。
BUILD = time.strftime("%m-%d %H:%M")

# 主屏图标：不依赖 Pillow，用标准库直接编 PNG。
# 造型是一辆正面小巴 —— 白色圆润车身、两只圆窗当眼睛、两个车轮，圆角底色。
# 比原来那条竖线更像「车」、更软。三版只换底色和细节色，形状完全一致。
ICON_BG = (14, 58, 99)       # 旧版底色，保留给老链接
_icon_cache = {}

ICON_THEMES = {
    # 暖橘：最亲和，暖色不刺眼
    "warm": {"top": (255, 199, 122), "bot": (255, 143, 77),
             "body": (255, 255, 255), "glass": (63, 43, 31),
             "wheel": (63, 43, 31), "lamp": (255, 209, 102)},
    # 晴空：清亮，和蓝白卡一脉，但明度拉高
    "sky":  {"top": (152, 215, 247), "bot": (77, 167, 232),
             "body": (255, 255, 255), "glass": (17, 69, 106),
             "wheel": (17, 69, 106), "lamp": (255, 209, 102)},
    # 深蓝：原来的观感，作为对照保留
    "deep": {"top": (24, 80, 128), "bot": (14, 58, 99),
             "body": (255, 255, 255), "glass": (14, 58, 99),
             "wheel": (14, 58, 99), "lamp": (255, 209, 102)},
}
ICON_DEFAULT = "warm"


def _rr(px, py, x0, y0, x1, y1, r):
    """点是否落在圆角矩形里。"""
    if px < x0 or px > x1 or py < y0 or py > y1:
        return False
    cx = min(max(px, x0 + r), x1 - r)
    cy = min(max(py, y0 + r), y1 - r)
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def _ci(px, py, cx, cy, r):
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def _png_icon(size=192, variant=None):
    variant = variant or ICON_DEFAULT
    key = (size, variant)
    if key in _icon_cache:
        return _icon_cache[key]

    t = ICON_THEMES.get(variant) or ICON_THEMES[ICON_DEFAULT]
    S = float(size)
    bx0, by0, bx1, by1 = S * .190, S * .265, S * .810, S * .700      # 车身
    br = S * .145
    wins = [(S * .248, S * .333, S * .466, S * .503),                 # 两只窗，圆角大一点更像「眼睛」
            (S * .534, S * .333, S * .752, S * .503)]
    wr = S * .058
    wheels = [(S * .312, S * .728, S * .090),
              (S * .688, S * .728, S * .090)]
    # 一条前脸横杠，代替两颗车灯 —— 小尺寸下更干净，也不像鼻孔
    bar = (S * .330, S * .548, S * .670, S * .586, S * .019)

    def shade(px, py):
        """这一点的颜色；圆角外返回 None。"""
        if not _rr(px, py, 0, 0, S, S, S * .235):
            return None
        for cx, cy, cr in wheels:
            if _ci(px, py, cx, cy, cr):
                return t["wheel"]
        if _rr(px, py, bx0, by0, bx1, by1, br):
            for x0, y0, x1, y1 in wins:
                if _rr(px, py, x0, y0, x1, y1, wr):
                    return t["glass"]
            if _rr(px, py, *bar[:4], bar[4]):
                return t["lamp"]
            return t["body"]
        k = py / S
        return tuple(int(t["top"][i] + (t["bot"][i] - t["top"][i]) * k) for i in range(3))

    raw = bytearray()
    for y in range(size):
        raw.append(0)                       # 每行的过滤器字节
        for x in range(size):
            hits = []
            for sy in (0.25, 0.75):          # 2×2 超采样，边缘不出锯齿
                for sx in (0.25, 0.75):
                    c = shade(x + sx, y + sy)
                    if c:
                        hits.append(c)
            if not hits:
                raw += b"\x00\x00\x00\x00"
                continue
            n = len(hits)
            raw += bytes((sum(c[0] for c in hits) // n,
                          sum(c[1] for c in hits) // n,
                          sum(c[2] for c in hits) // n,
                          int(255 * n / 4)))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    _icon_cache[key] = png
    return png

CACHE_RT = 12        # 实时数据缓存秒数
CACHE_STOPS = 3600   # 站表缓存秒数（基本静态）
PLATFORM_NEAR = 40   # 距站台多少米内才用定位判断方向

_rt_cache = {}
_stops_cache = {}

# ---------------------------------------------------------------- 接口层


def api_post(params):
    body = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        API, data=body,
        headers={
            "Origin": "https://h5.mygolbs.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": ("Mozilla/5.0 (Linux; Android 12; SM-G991B) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Mobile Safari/537.36"),
        })
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def _base():
    return {"CITYNAME": CITY, "CITYKEY": ""}


def _minutes(text):
    if not text:
        return None
    if "小于" in text and "分钟" in text:
        return 0
    m = re.search(r"(\d+)\s*分钟", text)
    return int(m.group(1)) if m else None


def _meters(text):
    m = re.search(r"([\d.]+)\s*公里", text or "")
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"(\d+)\s*米", text or "")
    return int(m.group(1)) if m else None


def _num(text):
    m = re.search(r"(\d+)", text or "")
    return int(m.group(1)) if m else None


def _status(node, dist):
    t = (node or "") + (dist or "")
    if "非运营" in t or "收班" in t:
        return "closed"
    if "等待发车" in t or "待发" in t:
        return "waiting"
    if "已到站" in t:
        return "here"
    if "已过" in t:
        return "passed"
    if _minutes(dist) is not None:
        return "coming"
    return "unknown"


_BRACKET_NOTE = re.compile(r"[（(]([^)）]{0,16})[)）]")
_KEEP_BRACKET = re.compile(r"^[东南西北中前后]{1,2}$")


def short_name(s):
    """把接口给的脏站名收拾成能直接念出来的样子。

    「三桥下首末站(不用于上下客)」→「三桥下」
    「会展中心首末站(工商银行)」→「会展中心」
    但「新城站(东)」这种用来分辨站台的方位括号要留着，否则两个站会同名。
    """
    s = s or ""

    def _drop(m):
        return m.group(0) if _KEEP_BRACKET.match(m.group(1).strip()) else ""

    s = _BRACKET_NOTE.sub(_drop, s)
    s = re.sub(r"(首末站|公交枢纽|公交站)$", "", s)
    return s.strip()


def fetch_station_lines(station):
    """CMD 115：该站所有经过线路的实时到站。"""
    cache_key = ("st", station)
    hit = _rt_cache.get(cache_key)
    if hit and time.time() - hit[0] < CACHE_RT:
        return hit[1]

    raw = api_post({**_base(), "CMD": "115", "STATIONNAME": station,
                    "MYLAT": "", "MYLNG": "", "ALL": "1"})
    if str(raw.get("status")) != "1":
        raise RuntimeError(raw.get("msg") or "接口返回异常")

    seen = set()
    lines = []
    for x in raw.get("data") or []:
        name = x.get("lineName") or ""
        d = str(x.get("upperOrDown") or "")
        key = (name, d)
        if key in seen:
            continue
        seen.add(key)
        node = x.get("neartext") or ""
        dist = x.get("neardis") or ""
        lines.append({
            "line": name,
            "dir": d,
            "to": x.get("to") or "",
            "toShort": short_name(x.get("to")),
            "node": node,
            "dist": dist,
            "minutes": _minutes(dist),
            "meters": _meters(dist),
            "stations": _num(node),
            "status": _status(node, dist),
            "order": x.get("stationOrder") or 0,
        })
    _rt_cache[cache_key] = (time.time(), lines)
    return lines


def fetch_stops(line, d):
    """CMD 103：线路站表。基本静态，长缓存。"""
    ck = (line, d)
    hit = _stops_cache.get(ck)
    if hit and time.time() - hit[0] < CACHE_STOPS:
        return hit[1]

    raw = api_post({**_base(), "CMD": "103", "LINENAME": line, "DIRECTION": d})
    stops = []
    for i, s in enumerate(raw.get("data") or [], 1):
        stops.append({
            "i": i,
            "name": s.get("stationName") or "",
            "lat": s.get("station_lat") or 0,
            "lon": s.get("station_lon") or 0,
        })
    detail = {
        "line": line,
        "dir": d,
        "begin": raw.get("beginTime") or "",
        "end": raw.get("endTime") or "",
        "from": stops[0]["name"] if stops else "",
        "to": stops[-1]["name"] if stops else "",
        "stops": stops,
    }
    # 站表自带坐标，顺手攒进站库 —— 附近站点功能的数据就是从这儿来的
    changed = False
    for s in stops:
        if station_db_put(s["name"], s["lat"], s["lon"]):
            changed = True
    if changed:
        station_db_flush()
    _stops_cache[ck] = (time.time(), detail)
    return detail


def fetch_buses(line, d):
    """CMD 104：该方向在途车辆，index = 正在驶向的站序。"""
    raw = api_post({**_base(), "CMD": "104", "LINENAME": line,
                    "DIRECTION": d, "STATIONORDER": "1"})
    buses = []
    for b in raw.get("list") or []:
        try:
            idx = int(b.get("index"))
        except (TypeError, ValueError):
            continue
        buses.append({
            "index": idx,
            "plate": b.get("busNumber") or "",
            "toNext": round(float(b.get("busToStationNiheDistance") or 0)),
        })
    buses.sort(key=lambda v: v["index"])
    return {"hasReal": raw.get("hasReal") == 1 or raw.get("hasReal") == "1",
            "buses": buses}


def fetch_platforms(station):
    """CMD 209：同名站台坐标，用于按距离判断用户在马路哪一侧。"""
    raw = api_post({**_base(), "CMD": "209", "STATIONNAME": station,
                    "MYLAT": "", "MYLNG": "", "LAT": "", "LNG": ""})
    info = raw.get("info")
    if not info and isinstance(raw.get("data"), dict):
        info = raw["data"].get("info")
    out = []
    for x in info or []:
        try:
            out.append({"lat": float(x.get("lat")), "lon": float(x.get("lon"))})
        except (TypeError, ValueError):
            continue
    # 顺手入库：收藏一个站的时候靠这里把坐标补上，
    # 否则「常去的站」永远算不出距离
    if out:
        changed = False
        for p in out:
            if station_db_put(station, p["lat"], p["lon"]):
                changed = True
        if changed:
            station_db_flush()
    return out


# ---------------------------------------------------------------- 站库
# 上游没有「给坐标反查站点」的接口（CMD 209 只能按站名查，dis 恒为 -1），
# 所以「附近有哪些站」必须自己算。好在 CMD 103 的站表里直接带 station_lat/lon，
# 一条线一次请求就能拿到全线站名和坐标 —— 看过哪条线，那条线的站就进库。
STATION_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.json")

# 「手机里自己算」那一版的前端（web/）。电脑上也能直接跑它，用来验证手机上
# 的行为：/static/index.html 打开就是 App 里那个页面，/api/data 由下面转发。
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
_WEB_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".mp3": "audio/mpeg",
    ".svg": "image/svg+xml",
}
_st_db = None
_st_dirty = False


def station_db():
    global _st_db
    if _st_db is None:
        try:
            with open(STATION_DB, encoding="utf-8") as f:
                _st_db = json.load(f)
        except Exception:
            _st_db = {}
    return _st_db


def station_db_put(name, lat, lon):
    """记一个站的坐标。返回 True 表示库里有变化（需要写盘）。"""
    global _st_dirty
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    if not name or not lat or not lon:
        return False
    db = station_db()
    pts = db.setdefault(name, [])
    p = [round(lat, 6), round(lon, 6)]
    # 同名站常有两个站台，坐标差十几米。都留着，算距离时取近的那个。
    for q in pts:
        if abs(q[0] - p[0]) < 1e-5 and abs(q[1] - p[1]) < 1e-5:
            return False
    pts.append(p)
    _st_dirty = True
    return True


def station_db_flush():
    """攒一批再写盘 —— 一张站表能带来 40 个站，逐个写太浪费。"""
    global _st_dirty
    if not _st_dirty:
        return
    try:
        tmp = STATION_DB + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(station_db(), f, ensure_ascii=False)
        os.replace(tmp, STATION_DB)
        _st_dirty = False
    except Exception:
        pass


def _dist_m(lat1, lon1, lat2, lon2):
    """两点直线距离（米）。筛附近站点用这个就够，不需要路网距离。"""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def station_dist(name, lat, lon):
    """某个站离她多远（米）。站库没有它时返回 None —— 不编一个数出来。"""
    pts = station_db().get(name)
    if not pts:
        return None
    return int(round(min(_dist_m(lat, lon, p[0], p[1]) for p in pts)))


def build_nearby(lat, lon, radius=500, limit=30, faves=None):
    """半径内的站 + 收藏的站。

    收藏的站**不受半径限制** —— 这是故意的：老人真正要坐的就是那两三个站，
    走远一点也还是它。而且家里信号差、定位偏，半径算进来算不进来都不可靠。
    """
    db = station_db()
    out = {}
    for name in (faves or []):
        pts = db.get(name)
        if not pts:
            continue                     # 站库里还没有它，跳过（不能编坐标）
        d = min(_dist_m(lat, lon, p[0], p[1]) for p in pts)
        out[name] = {"name": name, "dist": int(round(d)), "fave": True}

    for name, pts in db.items():
        if name in out or not pts:
            continue
        d = min(_dist_m(lat, lon, p[0], p[1]) for p in pts)
        if d <= radius:
            out[name] = {"name": name, "dist": int(round(d)), "fave": False}

    items = sorted(out.values(), key=lambda x: (0 if x["fave"] else 1, x["dist"], x["name"]))
    return {"ok": True, "stations": items[:limit], "total": len(items),
            "radius": radius, "known": len(db)}


def warm_nearby_db():
    """第一次跑时，把默认线路两个方向的站表各取一次，站点坐标自动进库。
    40 个站、两次请求，之后启动不会再发 —— 这是「附近站点」的数据底座。"""
    try:
        if len(station_db()) >= 10:
            return
        for d in ("1", "2"):
            try:
                fetch_stops(HOME_LINE, d)
            except Exception:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------- 业务层


def _pace(main):
    """每站大约几分钟。

    只用最近一班车到我这站的实测均速（minutes / stations）反推，
    不拿首末班时间硬除 —— 那是运营时段，不是全程耗时。
    拿不到就返回 None，宁可不给分钟数，也不编一个。
    """
    try:
        m, n = main.get("minutes"), main.get("stations")
        if m is not None and n:
            v = float(m) / float(n)
            return min(6.0, max(1.0, v))
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def _eta_for(i, detail, main, pace):
    """车到第 i 站还要几站、约几分钟。

    index 是「正在驶向的站序」，所以 index <= i 的车都还没开过这站；
    取其中最靠前的一辆，和卡片上那个大数字是同一班车。
    """
    focus = detail.get("focus")
    buses = detail.get("buses") or []

    live = [b for b in buses if b["index"] <= i]
    if not live:
        return None, None, True          # 车已经开过去了，等下一班

    bus = max(live, key=lambda b: b["index"])
    left = i - bus["index"] + 1

    # 就是我这站：必须和卡片主数字同一个来源，同一个站不能给出两个答案
    if focus is not None and i == focus and main:
        if main.get("stations") is not None:
            left = main["stations"]
        if main.get("minutes") is not None:
            return main["minutes"], left, False

    if pace is None:
        return None, left, False         # 没有实时均速就不给分钟
    return int(round(pace * left)), left, False


def window_stops(detail, main=None):
    """首页/卡片用的站点列表：整条线全给，由前端在固定高度的框里滚动。

    detail["focus"] 为 None 时表示这条线不经过我的站 —— 这时候不能把第 1 站
    当成「你在这」，只把在途车辆的位置标出来。

    每行顺带给出「车到这一站还有几站、约几分钟」，供前端点选查看。
    """
    stops = detail["stops"]
    focus = detail.get("focus")

    bus_at = {}
    for b in detail.get("buses") or []:
        # 知道我站在哪：只标还没开过我站的车，过站的不标（标了会白等）
        # 不知道我站在哪：全标，让老人看见车开到哪了
        if focus is None or b["index"] < focus:
            bus_at.setdefault(b["index"], b)

    pace = _pace(main)

    rows = []
    for s in stops:
        eta, left, passed = _eta_for(s["i"], detail, main, pace)
        rows.append({"i": s["i"], "name": s["name"],
                     "mine": focus is not None and s["i"] == focus,
                     "bus": s["i"] in bus_at,
                     "eta": eta, "left": left, "passed": passed})

    # 最近一辆车停在哪一站，顶部一句话说清楚
    bus_here = None
    if bus_at:
        nearest = max(bus_at)
        for s in stops:
            if s["i"] == nearest:
                bus_here = s["name"]
                break

    return {"rows": rows, "busHere": bus_here,
            "total": len(stops), "focus": focus,
            "pace": None if pace is None else round(pace, 1)}


def build_home(station=None):
    """首页 = 附近站牌 + 搜索入口。

    station 由前端按定位结果传进来（附近列表里选中的那个站）；
    没传就退回 HOME_STATION —— 定位失败也得能用。
    """
    data = build_station((station or "").strip() or HOME_STATION)
    data["isHome"] = True
    return data


def build_board(line, d, station):
    """到站卡片：一条线、一个方向、一个上车站。

    station 是「我在哪一站」。这条线不经过它时 passes=False，
    卡片就不显示分钟数，只显示全程和车开到哪了 —— 不硬编一个到站时间。
    """
    station = (station or "").strip() or HOME_STATION

    entries = []
    try:
        entries = fetch_station_lines(station)
    except Exception:
        pass

    mine = [v for v in entries if v["line"] == line]
    main = next((v for v in mine if v["dir"] == d), None)
    other = next((v for v in mine if v["dir"] != d), None)

    det = build_line(line, d, station)
    win = window_stops(det, main)
    passes = bool(det.get("focus"))

    # 反方向在这个站没有记录（比如环线）时，单独查一次拿终点名
    if other is None:
        try:
            d2 = "2" if str(d) == "1" else "1"
            det2 = build_line(line, d2, station)
            other = {"line": line, "dir": d2, "toShort": det2["toShort"],
                     "status": "unknown", "minutes": None, "stations": None,
                     "node": None, "dist": None, "label": ""}
        except Exception:
            other = None

    if main:
        card = dict(main)
    else:
        card = {"line": line, "dir": d, "toShort": det["toShort"],
                "status": "noroute", "minutes": None, "stations": None,
                "node": None, "dist": None, "label": ""}

    return {"ok": True, "station": station, "line": line, "dir": d,
            "main": card, "other": other, "win": win,
            "passes": passes, "total": len(det["stops"]),
            "hasReal": det.get("hasReal", False),
            "updated": datetime.now().strftime("%H:%M")}


def build_station(station):
    lines = fetch_station_lines(station)
    rank = {"coming": 0, "here": 0, "waiting": 1, "unknown": 2,
            "passed": 3, "closed": 4}
    lines.sort(key=lambda v: (rank.get(v["status"], 5),
                              v["minutes"] if v["minutes"] is not None else 999))
    return {"ok": True, "station": station, "lines": lines,
            "updated": datetime.now().strftime("%H:%M")}


def build_dirs(line, station=""):
    """一条线路的两个方向，给「选方向」这一步用。

    这一步是给「搜线路号」的人准备的 —— 他只知道要坐几路，不知道往哪边开。
    知道上车站（从站牌页过来）就顺带给出「还有几分钟」；不知道就只给站数、
    首末班、在途车数，不编一个到站时间骗人。
    """
    station = (station or "").strip()

    live = {}
    if station:
        try:
            for v in fetch_station_lines(station):
                if v["line"] == line:
                    live[v["dir"]] = v
        except Exception:
            pass

    out = []
    for d in ("1", "2"):
        try:
            det = build_line(line, d, station)
        except Exception:
            continue
        if not det.get("stops"):
            continue
        item = {
            "dir": d,
            "toShort": det["toShort"],
            "fromShort": det["fromShort"],
            "begin": det["begin"],
            "end": det["end"],
            "stopCount": len(det["stops"]),
            "busCount": len(det.get("buses") or []),
            "hasReal": det.get("hasReal", False),
        }
        v = live.get(d)
        if v:
            item["minutes"] = v.get("minutes")
            item["stations"] = v.get("stations")
            item["status"] = v.get("status")
        out.append(item)

    return {"ok": True, "line": line, "station": station, "dirs": out}


def build_line(line, d, focus):
    stops = fetch_stops(line, d)
    rt = fetch_buses(line, d)
    focus_idx = None
    for s in stops["stops"]:
        if s["name"] == focus:
            focus_idx = s["i"]
            break
    return {"ok": True, "line": line, "dir": d,
            "from": stops["from"], "to": stops["to"],
            "fromShort": short_name(stops["from"]),
            "toShort": short_name(stops["to"]),
            "begin": stops["begin"], "end": stops["end"],
            "stops": stops["stops"], "buses": rt["buses"],
            "hasReal": rt["hasReal"], "focus": focus_idx,
            "updated": datetime.now().strftime("%H:%M")}


def build_platforms(station):
    return {"ok": True, "station": station, "platforms": fetch_platforms(station)}


def build_eta(line, d, station):
    """车到某个指定站还要几站、几分钟。

    不走「按站数乘平均时长」的推算，而是直接问上游这一站的实时到站 ——
    和卡片上那个大数字是同一个来源，所以同一个站不会给出两个答案。
    选任意站都成立，不依赖「我的站」，线路不经过家门口也一样能用。
    """
    station = (station or "").strip()
    if not station:
        return {"ok": False, "error": "缺少站名"}

    try:
        entries = fetch_station_lines(station)
    except Exception:
        return {"ok": False, "error": "这一站暂时查不到"}

    for v in entries:
        if v["line"] == line and v["dir"] == d:
            return {"ok": True, "station": station, "line": line, "dir": d,
                    "status": v["status"], "minutes": v["minutes"],
                    "stations": v["stations"], "toShort": v["toShort"],
                    "node": v["node"], "dist": v["dist"],
                    "updated": datetime.now().strftime("%H:%M")}

    # 车已经开过这一站，或这条线今天不再经过这里
    return {"ok": False, "error": "这站没有这趟车"}


SEARCH_MAX_LINES = 10     # 搜「5」会返回 77 条，全列出来老人只会退出去
SEARCH_MAX_STATIONS = 8


def _local_stations(kw, lat=None, lon=None):
    """在本地站库里找站名。

    上游 CMD 110 一次最多回 30 条，本地库有全市 6900 多个站 —— 站名搜索
    改走本地，又快又全，还省掉一次网络往返（老人家里网差的时候差别很大）。

    返回的 name 是**原始站名**，站牌页要拿它去查 CMD 115；
    short 只是给人看的（「东明路口（温州口腔医院）（BRT）」念出来太啰嗦）。
    """
    db = station_db()
    k = (kw or "").strip()
    if not k:
        return []
    out = []
    for name, pts in db.items():
        sn = short_name(name)
        if k not in name and k not in sn:
            continue
        d = None
        if lat is not None and lon is not None and pts:
            d = int(round(min(_dist_m(lat, lon, p[0], p[1]) for p in pts)))
        out.append({"name": name, "short": sn, "dist": d})
    return out


def _station_sort(hits, kw, has_pos):
    """站名搜索的排序。

    有定位时按「距离 + 命中质量」合起来排，而不是先分档：

        分数 = 距离(米) + 命中档次 × 1500

    1500 米是「名字更贴」值多少路的折算 —— 名字完全一样的站，宁可多走
    1.5 公里也去；名字只是沾边的，近 1.5 公里才抵得过。

    为什么不能纯按命中排：全市 163 个站名跨县重复，搜「人民医院」时
    纯按命中会把 54 公里外的「人民医院（洞头）」顶到最前面。
    为什么不能纯按距离排：搜「石坦」时「石坦路」可能比「石坦」近几十米，
    但老人要去的是「石坦」，不该被「石坦路」挡在前面。

    没定位就只按命中质量排，不编距离。
    """
    BONUS = 1500

    def key(v):
        rank = _rank_station(v["name"], kw)
        d = v["dist"] if (has_pos and v["dist"] is not None) else None
        if d is None:
            return (0, rank, 10 ** 7, len(v["name"]), v["name"])
        return (0, d + rank * BONUS, len(v["name"]), v["name"])
    hits.sort(key=key)
    return hits


def build_search(kw, lat=None, lon=None):
    lines, stations = [], []
    skipped = 0
    try:
        raw = api_post({**_base(), "CMD": "114", "KEYWORD": kw})
        seen = set()
        for b in raw.get("buslines") or []:
            name = (b.get("lineName") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            # 没有实时数据的线路（轻轨 S1/S2 等）不列出，点进去只有空壳
            if str((b.get("routeBean") or {}).get("hasReal")) != "1":
                skipped += 1
                continue
            lines.append({
                "line": name,
                "from": short_name(b.get("from")),
                "to": short_name(b.get("to")),
                "hasReal": True,
            })
    except Exception:
        pass

    has_pos = lat is not None and lon is not None
    stations = _station_sort(_local_stations(kw, lat, lon), kw, has_pos)

    # 本地库没命中时再问一次上游 —— 万一它那边新加了站，本地还没抓到
    if not stations:
        try:
            raw = api_post({**_base(), "CMD": "110", "KEYWORD": kw})
            seen = set()
            for s in raw.get("busstations") or []:
                name = (s.get("stationName") or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                d = None
                if has_pos:
                    pts = station_db().get(name)
                    if pts:
                        d = int(round(min(_dist_m(lat, lon, p[0], p[1]) for p in pts)))
                stations.append({"name": name, "short": short_name(name), "dist": d})
            stations.sort(key=lambda v: (_rank_station(v["name"], kw), len(v["name"]), v["name"]))
        except Exception:
            pass

    # 搜「5」时 5路 必须排在 50路、B105路 前面
    lines.sort(key=lambda v: (_rank(v["line"], kw), len(v["line"]), v["line"]))

    # 用户真正想坐的那条（线路号精确命中）直接把两个方向摊开，
    # 不用再点进去选一次。同名的其他线路（苍南JD36路之类）只列一行。
    for v in lines:
        if _rank(v["line"], kw) == 0:
            try:
                v["dirs"] = _light_dirs(v["line"])
            except Exception:
                v["dirs"] = []

    lines_total, stations_total = len(lines), len(stations)

    return {"ok": True, "kw": kw,
            "lines": lines[:SEARCH_MAX_LINES],
            "stations": stations[:SEARCH_MAX_STATIONS],
            "linesTotal": lines_total, "stationsTotal": stations_total,
            "skipped": skipped}


def _light_dirs(line):
    """只查站表，给出两个方向的终点和站数。

    给搜索结果用的：查车辆数据太慢，一次搜索要展开好几条线，
    这里只拿「往哪、几站」，实时到站等进到卡片页再说。
    """
    out = []
    for d in ("1", "2"):
        try:
            st = fetch_stops(line, d)
        except Exception:
            continue
        if not st.get("stops"):
            continue
        out.append({"dir": d,
                    "toShort": short_name(st["to"]),
                    "stopCount": len(st["stops"])})
    return out


def _rank(name, kw):
    """越小越靠前：0 完全命中，1 开头命中，2 只是包含。

    去掉结尾的「路」是为了线路号：搜「36」时「36路」要算完全命中。
    站名不能这么比 —— 那会把「石坦路」当成「石坦」，所以站名走 _rank_station。
    """
    n = (name or "").strip()
    k = (kw or "").strip()
    base = n[:-1] if n.endswith("路") else n
    if n == k or base == k:
        return 0
    if n.startswith(k) or base.startswith(k):
        return 1
    return 2


def _rank_station(name, kw):
    """站名的命中档次：0 一模一样，1 开头，2 只是包含。不砍「路」字。"""
    n = (name or "").strip()
    k = (kw or "").strip()
    if n == k:
        return 0
    if n.startswith(k):
        return 1
    return 2


def snapshot():
    """抓一份真实数据快照，供离线 demo 用。"""
    q = urllib.parse.quote
    d = {}
    try:
        d["/api/home"] = build_home()
    except Exception:
        pass
    for st in (HOME_STATION, "新城站"):
        u = "/api/station?name=" + q(st)
        try:
            d[u] = build_station(st)
        except Exception:
            pass
    for dr in ("1", "2"):
        u = "/api/line?name=%s&dir=%s&focus=%s" % (q(HOME_LINE), dr, q(HOME_STATION))
        try:
            d[u] = build_line(HOME_LINE, dr, HOME_STATION)
        except Exception:
            pass
        ub = "/api/board?line=%s&dir=%s&station=%s" % (q(HOME_LINE), dr, q(HOME_STATION))
        try:
            d[ub] = build_board(HOME_LINE, dr, HOME_STATION)
        except Exception:
            pass
    for kw in ("159", "36", "S1", "石坦"):
        try:
            d["/api/search?kw=" + q(kw)] = build_search(kw)
        except Exception:
            pass
    return d


def build_demo(skin="c"):
    data = json.dumps(snapshot(), ensure_ascii=False).replace("</", "<\\/")
    inject = "<script>window.__DATA__=" + data + ";</script>"
    return page_html(skin).replace("<script>", inject + "<script>", 1)


# ---------------------------------------------------------------- 前端

def _theme_buttons():
    """设置面板里的三个配色按钮。色块直接用各套的主色，不交给皮肤替换。"""
    swatch = {"c": "#0E3A63", "d": "#A8461C", "e": "#1B5FB0"}
    out = []
    for key, name, note in THEME_CHOICES:
        out.append('<button class="th" data-sk="' + key + '" onclick="setSkin(\'' + key + '\')">'
                   '<i style="background:' + swatch.get(key, "#0E3A63") + '"></i>'
                   '<b>' + name + '</b><small>' + note + '</small></button>')
    return "".join(out)


SPK_ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true"><path d="M4 9.5v5h3.5L13 19V5L7.5 9.5H4z"/>'
            '<path d="M16.5 8.5a5 5 0 0 1 0 7"/><path d="M19 6a9 9 0 0 1 0 12"/>'
            '</svg>')

REMIND_DOM = (
    # 底部常驻的「念一遍」：位置永远一样，不识字的人在哪个页面都能找到它
    '<div class="spkbar"><button class="spkbtn" id="spkbtn" onclick="speakPage()">'
    + SPK_ICON + '<span>念一遍</span></button></div>'
    '<div class="banner" id="banner"></div>'
    '<div class="mask" id="mask" onclick="closeSheet()"></div>'
    '<div class="sheet" id="sheet">'
    '<h4>设置</h4>'
    '<div class="sect-t">字大小</div>'
    '<div class="hint">点一下，整页的字跟着变</div>'
    '<div class="fss">'
    '<button class="fs" data-fs="1" onclick="setFs(1)">'
    '<i style="font-size:17px">站</i><small>标准</small></button>'
    '<button class="fs" data-fs="2" onclick="setFs(2)">'
    '<i style="font-size:25px">站</i><small>大</small></button>'
    '<button class="fs" data-fs="3" onclick="setFs(3)">'
    '<i style="font-size:33px">站</i><small>特大</small></button>'
    '</div>'
    '<div class="thhint">看不清就选最右边那个</div>'
    '<div class="sect-t">到站响铃</div>'
    '<div class="hint">车还有几站时，提示一次并响一声</div>'
    '<div class="opts">'
    '<button class="opt" data-n="2" onclick="pickAt(2)">2 站<small>推荐</small></button>'
    '<button class="opt" data-n="3" onclick="pickAt(3)">3 站<small>早点出门</small></button>'
    '<button class="opt" data-n="5" onclick="pickAt(5)">5 站<small>更早</small></button>'
    '</div>'
    '<button class="off" onclick="turnOff()">关掉响铃</button>'
    '<div class="limit" id="limitline">现在只有页面开着才响。锁屏、切到别的应用就不响了</div>'
    '<div class="sect-t">手机配色</div>'
    '<div class="themes">' + _theme_buttons() + '</div>'
    '<div class="thhint">点一下就换，换完自己记住</div>'
    '<div id="srvline"></div>'
    '<div id="buildline"></div>'
    '</div>'
)


def _web_file(rel):
    """读 web/ 下的文件。读不到就报错，**不退回任何内置副本**。

    V1.0 时代整份前端是塞在本文件里的字符串，抽成 web/ 之后那两个副本
    一直躺在文件末尾。它们的危害不是占行数，而是：web/ 一旦读不到，
    服务会安静地用 V1.0 的页面顶上去 —— 看起来一切正常，实际全是旧界面。
    宁可让请求当场失败，也不要静默降级。
    """
    path = os.path.join(WEB_DIR, rel)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise RuntimeError("读不到 %s（%s）。前端唯一真相在 bus-app/web/，"
                           "缺文件说明部署不完整，先把它补回来。" % (path, e))


def page_html(skin="c", pwa=False):
    """按皮肤生成页面。skin 不认识时调用方已经退回 DEFAULT_SKIN。

    pwa=True 时才挂 manifest 和主屏图标 —— 离线单文件（file://）挂这些只会报错。
    """
    # 前端只有一份真相：bus-app/web/ 。电脑上跑服务时也读那几个文件，
    # 免得改了一边忘了另一边（手机里跑的是同一份 app.js）。
    css = _web_file("skins/%s.css" % skin)
    js = _web_file("app.js")
    # 图标与状态栏底色跟着皮肤走，别让暖橘页面顶着深蓝图标
    theme = {"d": "#FFF8F1", "e": "#F6FAFF"}.get(skin, "#FAFAF7")
    icon_v = {"c": "deep", "d": "warm", "e": "sky"}.get(skin, "warm")
    head = ""
    if pwa:
        head = ("<link rel=\"manifest\" href=\"/manifest.json\">"
                "<link rel=\"icon\" href=\"/icon.png?size=192&v=" + icon_v + "\">"
                "<link rel=\"apple-touch-icon\" href=\"/icon.png?size=180&v=" + icon_v + "\">"
                "<meta name=\"mobile-web-app-capable\" content=\"yes\">"
                "<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">"
                "<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"default\">"
                "<meta name=\"apple-mobile-web-app-title\" content=\"公交到站\">")
    return ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,"
            "maximum-scale=1,user-scalable=no,viewport-fit=cover\">"
            "<meta name=\"theme-color\" content=\"" + theme + "\">" + head +
            "<title>公交到站</title><style>" + css + "</style></head>"
            "<body data-sk=\"" + skin + "\" data-build=\"" + BUILD + "\">"
            "<div id=\"app\" style=\"flex:1;display:flex;flex-direction:column;"
            "overflow:hidden;min-height:0\"></div>" + REMIND_DOM +
            "<script>" + js + "</script></body></html>")


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype, extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # 默认不许缓存：页面和接口一变，手机就该跟着变。
        # 传了 extra 时是「合并」不是「替换」—— 早先写成 extra or {...}，
        # 结果给首页加 Vary:Cookie 的那一刻，no-store 就被挤掉了，
        # WebView 有可能一直拿旧页面。extra 里的同名头仍然优先（图标要靠它缓存）。
        headers = {"Cache-Control": "no-store"}
        headers.update(extra or {})
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, code, data, ctype, extra=None):
        self._send(code, data, ctype, extra)

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _cookie(self, name):
        """取一个 cookie 的值，没有就返回空串。只用来记配色，不碰别的。"""
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v.strip()
        return ""

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        q = urllib.parse.parse_qs(u.query)

        try:
            if path in ("/", "/index.html"):
                # 配色优先级：地址栏 ?skin= ＞ 上次在「设置」里选的（cookie）＞ 默认
                # 用 cookie 而不是把 skin 写进网址：切完色刷新，hash 路由还在原地，
                # 老人不会因为换个颜色就被弹回首页。
                skin = (q.get("skin") or [""])[0].lower()
                if skin not in SKINS:
                    skin = self._cookie("sk") if self._cookie("sk") in SKINS else DEFAULT_SKIN
                self._send(200, page_html(skin, pwa=True), "text/html; charset=utf-8",
                           extra={"Vary": "Cookie"})

            elif path == "/api/home":
                st = (q.get("station") or [""])[0].strip()
                self._json(build_home(st))

            elif path == "/api/eta":
                # 点站点看车多久到：问的是「这一站」的实时到站
                line = (q.get("line") or [""])[0].strip()
                d = (q.get("dir") or ["1"])[0]
                station = (q.get("station") or [""])[0].strip()
                if not line:
                    self._json({"ok": False, "error": "缺少线路名"})
                else:
                    self._json(build_eta(line, d, station))

            elif path == "/api/board":
                line = (q.get("line") or [""])[0].strip()
                d = (q.get("dir") or ["1"])[0]
                station = (q.get("station") or [""])[0].strip()
                if not line:
                    self._json({"ok": False, "error": "缺少线路名"})
                else:
                    self._json(build_board(line, d, station))

            elif path == "/api/stloc":
                # 收藏一个站时调一次，把它的坐标补进站库。查不到就老实回 false。
                nm = (q.get("name") or [""])[0].strip()
                if not nm:
                    self._json({"ok": False, "error": "没给站名"})
                    return
                try:
                    pts = fetch_platforms(nm)
                except Exception as e:
                    self._json({"ok": False, "error": str(e)})
                    return
                self._json({"ok": bool(pts), "name": nm, "points": len(pts)})

            elif path == "/api/nearby":
                # 附近站点：前端把定位坐标传上来，本地站库算距离再筛。
                # 拿不到定位就不编一个坐标 —— 宁可回错，让页面说「定位不了」。
                try:
                    lat = float((q.get("lat") or [""])[0])
                    lon = float((q.get("lon") or [""])[0])
                except ValueError:
                    self._json({"ok": False, "error": "没有位置"})
                    return
                try:
                    rad = int((q.get("r") or ["500"])[0])
                except ValueError:
                    rad = 500
                # 收藏的站名由前端带上来（存在手机上，服务端不记）
                faves = []
                for raw in (q.get("faves") or [""])[0].split(","):
                    n = raw.strip()
                    if n and n not in faves:
                        faves.append(n)
                # 按范围给上限：原来写死 30，范围一大就等于瞒着用户截断
                # （2 公里在市区有 76 个站，界面却说「2 公里内就这些」）。
                # 真实总数一起给前端，让它被截时在列表末尾说清楚。
                # 「2 公里」这一档已从界面拿掉，>=2000 的分支留着 ——
                # 将来要恢复，前端改 _RANGES 一行就够，后端不用动。
                rad = max(100, min(3000, rad))
                limit = 60 if rad >= 2000 else 40
                self._json(build_nearby(lat, lon, rad, limit=limit, faves=faves))

            elif path == "/api/station":
                name = (q.get("name") or [""])[0].strip()
                if not name:
                    self._json({"ok": False, "error": "缺少站名"})
                else:
                    self._json(build_station(name))

            elif path == "/api/line":
                line = (q.get("name") or [""])[0].strip()
                d = (q.get("dir") or ["1"])[0]
                focus = (q.get("focus") or [""])[0].strip()
                if not line:
                    self._json({"ok": False, "error": "缺少线路名"})
                else:
                    self._json(build_line(line, d, focus))

            elif path == "/api/dirs":
                line = (q.get("line") or [""])[0].strip()
                station = (q.get("from") or [""])[0].strip()
                if not line:
                    self._json({"ok": False, "error": "缺少线路名"})
                else:
                    self._json(build_dirs(line, station))

            elif path == "/api/platforms":
                name = (q.get("name") or [""])[0].strip()
                self._json(build_platforms(name))

            elif path == "/api/search":
                kw = (q.get("kw") or [""])[0].strip()
                if not kw:
                    self._json({"ok": False, "error": "缺少关键词"})
                else:
                    # 带上定位就把同名的站按远近排 —— 全市 163 个站名跨县重复，
                    # 不排的话市区的人搜「人民医院」先看到泰顺那个
                    try:
                        lat = float((q.get("lat") or [""])[0])
                        lon = float((q.get("lon") or [""])[0])
                    except ValueError:
                        lat = lon = None
                    self._json(build_search(kw, lat, lon))

            elif path == "/api/stdist":
                # 她到某个站多远。用来判断「现在出门赶不赶得上」，
                # 不编数：站库没这个站就回 ok:false
                nm = (q.get("name") or [""])[0].strip()
                try:
                    dla = float((q.get("lat") or [""])[0])
                    dlo = float((q.get("lon") or [""])[0])
                except ValueError:
                    self._json({"ok": False, "error": "缺少坐标"})
                else:
                    d = station_dist(nm, dla, dlo)
                    self._json({"ok": d is not None, "dist": d})

            elif path == "/api/data":
                # 给 web/ 那一版（手机里自己算）当中转。
                # 上游防盗链只认 Origin: https://h5.mygolbs.com，浏览器和 WebView
                # 里 JS 改不了这个头（禁止修改），所以由壳替它加上 —— 电脑上是这里，
                # 手机上是 WebView 的 shouldInterceptRequest。返回的东西完全一样。
                params = {k: v[0] for k, v in urllib.parse.parse_qs(
                    u.query, keep_blank_values=True).items()}
                try:
                    self._json(api_post(params))
                except Exception as e:
                    self._json({"status": "-1", "msg": str(e)[:120]})

            elif path.startswith("/static/"):
                rel = urllib.parse.unquote(path[len("/static/"):])
                full = os.path.normpath(os.path.join(WEB_DIR, rel))
                if not full.startswith(WEB_DIR) or not os.path.isfile(full):
                    self._send(404, "not found", "text/plain; charset=utf-8")
                else:
                    ext = os.path.splitext(full)[1].lower()
                    with open(full, "rb") as f:
                        blob = f.read()
                    self._send_bytes(200, blob,
                                     _WEB_MIME.get(ext, "application/octet-stream"))

            elif path == "/icon.png":
                try:
                    size = int((q.get("size") or ["192"])[0])
                except ValueError:
                    size = 192
                size = max(48, min(512, size))
                variant = (q.get("v") or [ICON_DEFAULT])[0].lower()
                self._send_bytes(200, _png_icon(size, variant), "image/png",
                                 extra={"Cache-Control": "public, max-age=86400"})

            elif path == "/manifest.json":
                self._json({
                    "name": "公交到站",
                    "short_name": "公交到站",
                    "start_url": "/",
                    "scope": "/",
                    "display": "standalone",
                    "orientation": "portrait",
                    "background_color": "#FAFAF7",
                    "theme_color": "#FAFAF7",
                    "lang": "zh-CN",
                    "icons": [
                        {"src": "/icon.png?size=192", "sizes": "192x192",
                         "type": "image/png", "purpose": "any"},
                        {"src": "/icon.png?size=384", "sizes": "384x384",
                         "type": "image/png", "purpose": "any"},
                        {"src": "/icon.png?size=192", "sizes": "192x192",
                         "type": "image/png", "purpose": "maskable"},
                    ],
                })

            elif path == "/demo":
                # 离线可看的单文件：数据内嵌，双击打开即可，不需要联网也不需要服务
                skin = (q.get("skin") or ["c"])[0].lower()
                if skin not in SKINS:
                    skin = DEFAULT_SKIN
                self._send(200, build_demo(skin), "text/html; charset=utf-8")

            elif path == "/_preview":
                # 移动端预览：/_preview?w=390&h=640&p=%23/l/36路/1
                # w/h 是 iframe 视口尺寸，p 是要打开的 hash 路由，skin 是皮肤
                w, hgt = 390, 780
                for key, tgt in (("w", "w"), ("h", "hgt")):
                    if key in q:
                        try:
                            if tgt == "w":
                                w = int(q[key][0])
                            else:
                                hgt = int(q[key][0])
                        except ValueError:
                            pass
                sub = (q.get("p") or [""])[0]
                sk = (q.get("skin") or ["c"])[0].lower()
                # src=static 时预览的是 web/ 那一版（手机里跑的就是它），
                # 顺带把字号档 fs 和假坐标 loc 透传进去
                if (q.get("src") or [""])[0] == "static":
                    arg = []
                    if "fs" in q: arg.append("fs=" + q["fs"][0])
                    if "loc" in q: arg.append("loc=" + q["loc"][0])
                    if "sheet" in q: arg.append("sheet=" + q["sheet"][0])
                    target = "/static/index.html" + ("?" + "&".join(arg) if arg else "") + sub
                else:
                    target = "/?skin=%s%s" % (sk, sub)
                page = (
                    '<html><body style="margin:0;background:#777;display:flex;'
                    'justify-content:center;align-items:flex-start">'
                    '<iframe src="%s" style="width:%dpx;height:%dpx;border:0;'
                    'background:#fff"></iframe></body></html>' % (target, w, hgt)
                )
                self._send(200, page, "text/html; charset=utf-8")

            else:
                self._send(404, "not found", "text/plain; charset=utf-8")

        except Exception as e:
            self._json({"ok": False, "error": str(e)[:160]})


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("223.5.5.5", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


if __name__ == "__main__":
    try:
        p = build_home()
        d0 = p["dirs"][0] if p["dirs"] else {}
        print("[OK] 接口连通：%s站 %s 往%s %s %s" % (
            HOME_STATION, HOME_LINE, short_name(d0.get("to")),
            d0.get("node"), d0.get("dist")))
    except Exception as e:
        print("[!] 首次取数失败：" + str(e))

    ip = lan_ip()
    print()
    print("  石坦站 · 公交到站  老人版 V1.0")
    print("  " + "-" * 44)
    print("  电脑打开:  http://127.0.0.1:%d" % PORT)
    if ip:
        print()
        print("  手机打开:  http://%s:%d" % (ip, PORT))
        print("            （手机连同一个 WiFi，在浏览器地址栏输这串）")
    print()
    print("  手机屏幕预览: http://127.0.0.1:%d/_preview?w=390" % PORT)
    print("  按 Ctrl+C 停止，关掉这个窗口也会停止")
    print()

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    except OSError:
        print("[!] 端口 %d 已经被占用了，八成是之前那个窗口还开着。" % PORT)
        print("    1) 先看看任务栏有没有另一个「公交到站」黑色窗口，关掉它再重开")
        print("    2) 或者直接在浏览器打开 http://127.0.0.1:%d 试试，能开就不用重开" % PORT)
        print()
        input("按回车键退出…")
        raise SystemExit(1)

    # 后台把默认线路的站坐标攒进库，别卡住启动
    threading.Thread(target=warm_nearby_db, daemon=True).start()

    try:
        import webbrowser
        webbrowser.open("http://127.0.0.1:%d" % PORT)
    except Exception:
        pass

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
