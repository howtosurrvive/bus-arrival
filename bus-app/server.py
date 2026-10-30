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
import re
import socket
import struct
import time
import urllib.parse
import urllib.request
import zlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from skins import SKINS
except Exception:          # 皮肤文件缺失时退回内置样式，不影响可用
    SKINS = {}

API = "https://h5.mygolbs.com/ApiData.do"
CITY = "温州市"
HOME_STATION = "石坦"
HOME_LINE = "36路"
PORT = 8765

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
    return out


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


def build_home():
    """首页 = 附近站牌 + 搜索入口。

    「附近」现在还是写死的 HOME_STATION，等手机定位接上以后改成按距离选站，
    到时候换掉这一个参数就行，前端不用动。
    """
    data = build_station(HOME_STATION)
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
    """越小越靠前：0 完全命中，1 开头命中，2 只是包含。"""
    n = (name or "").strip()
    k = (kw or "").strip()
    base = n[:-1] if n.endswith("路") else n
    if n == k or base == k:
        return 0
    if n.startswith(k) or base.startswith(k):
        return 1
    return 2


def build_search(kw):
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

    try:
        raw = api_post({**_base(), "CMD": "110", "KEYWORD": kw})
        seen = set()
        for s in raw.get("busstations") or []:
            name = (s.get("stationName") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            stations.append({"name": name})
    except Exception:
        pass

    # 搜「5」时 5路 必须排在 50路、B105路 前面
    lines.sort(key=lambda v: (_rank(v["line"], kw), len(v["line"]), v["line"]))
    stations.sort(key=lambda v: (_rank(v["name"], kw), len(v["name"]), v["name"]))

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

CSS = r"""
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%}
body{
  font-family:system-ui,-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;
  background:#fff;color:#111;display:flex;flex-direction:column;overflow:hidden;
}
.nav{
  flex-shrink:0;display:flex;align-items:center;gap:10px;
  padding:15px 18px 13px;border-bottom:1px solid #EFEFEC;background:#fff;
}
.back{
  font-size:17px;color:#0B4F8A;background:none;border:none;
  font-family:inherit;padding:8px 12px 8px 0;cursor:pointer;font-weight:600;
}
.nav .t{font-size:22px;font-weight:700;letter-spacing:-.2px}
.nav .r{margin-left:auto;font-size:16px;color:#6A6A66;font-variant-numeric:tabular-nums}

.scroll{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:14px;min-height:0}
.scroll.flush{padding:0}
.scroll.home{display:flex;flex-direction:column;gap:12px;padding-bottom:6px}
.scroll.home .card{flex:none;min-height:200px;margin-bottom:0;padding:18px 20px}

.card{
  border-radius:22px;padding:20px 22px;margin-bottom:12px;
  border:1.5px solid transparent;position:relative;overflow:hidden;
  cursor:pointer;
}
.card.up{background:#EDF4FC;border-color:#A8C8EA}
.card.dn{background:#EDF7F2;border-color:#8FCFAE}
.card.urgent::before{content:"";position:absolute;left:0;right:0;top:0;height:5px;background:#E8860C}

.ctop{display:flex;align-items:center;gap:9px}
.lineno{font-size:27px;font-weight:700;letter-spacing:-.3px}
.lineno.up{color:#0B4F8A}
.lineno.dn{color:#0A6B45}
.toward{
  font-size:15px;color:#4A4A48;flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swapbtn{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:5px;
  border:1.5px solid currentColor;background:rgba(255,255,255,.82);
  border-radius:999px;padding:8px 13px;
  font-size:14px;font-weight:600;font-family:inherit;
  cursor:pointer;line-height:1;white-space:nowrap;
}
.swapbtn .si{font-size:15px;font-weight:700}
.swapbtn b{font-size:17px;font-weight:700}
.card.up .swapbtn{color:#0B4F8A}
.card.dn .swapbtn{color:#0A6B45}

.main{display:flex;align-items:flex-end;gap:5px;margin-top:6px}
.min{font-size:82px;font-weight:800;line-height:.86;letter-spacing:-2.5px}
.min.up{color:#0B4F8A}
.min.dn{color:#0A6B45}
.unit{font-size:25px;font-weight:700;padding-bottom:9px}
.unit.up{color:#0B4F8A}
.unit.dn{color:#0A6B45}
.stxt{font-size:50px;font-weight:800;line-height:1.1;margin-top:6px}
.stxt.up{color:#0B4F8A}
.stxt.dn{color:#0A6B45}
.sub{font-size:19px;color:#3A3A38;margin-top:5px}
.go{color:#C25E00}
.other{
  font-size:17px;color:#3A5A80;display:flex;align-items:center;gap:6px;
}
.other b{font-weight:700;font-size:20px}

.swin{margin-top:12px;padding-top:10px;border-top:1px dashed rgba(0,0,0,.12)}
.swabove{font-size:14px;color:#B06000;padding:2px 0 6px}
.swrow{
  position:relative;display:flex;align-items:center;gap:8px;
  height:38px;padding-left:24px;
}
.swrow::before{
  content:"";position:absolute;left:4px;top:0;bottom:0;
  width:2px;background:#AEC6DD;
}
.swrow:first-child::before{top:50%}
.swrow:last-child::before{bottom:50%}
.swrow .d{
  position:absolute;left:0;top:50%;transform:translateY(-50%);
  width:10px;height:10px;border-radius:50%;background:#fff;
  border:2px solid #A8BED4;box-sizing:border-box;
}
.swrow.mine .d{
  border-color:#0B4F8A;background:#0B4F8A;
  box-shadow:0 0 0 3px rgba(11,79,138,.16);
}
.swrow.bus .d{
  border-color:#D97706;background:#D97706;
  box-shadow:0 0 0 3px rgba(217,119,6,.18);
}
.swrow .n{
  font-size:18px;color:#3A3A38;flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.swrow.mine .n{font-weight:700;color:#0B4F8A}
.swrow .tb{font-size:12px;font-weight:700;color:#fff;background:#D97706;border-radius:6px;padding:2px 7px}
.swrow .tm2{font-size:12px;font-weight:700;color:#fff;background:#0B4F8A;border-radius:6px;padding:2px 7px}

.cfoot{
  display:flex;align-items:center;
  margin-top:10px;padding-top:10px;border-top:1px dashed rgba(0,0,0,.12);
  font-size:15px;line-height:1.3;
}
.swall{color:#0B4F8A;font-weight:600;white-space:nowrap}

.sec{font-size:15px;color:#777;margin:2px 0 10px}

.row{
  display:flex;align-items:center;gap:12px;
  padding:17px 16px;border-bottom:1px solid #F0EFEC;cursor:pointer;
}
.row:active{background:#F7F7F5}
.row .ln{font-size:22px;font-weight:700;color:#1A1A18;min-width:82px;letter-spacing:-.2px}
.row .dst{flex:1;font-size:16px;color:#5A5A56;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .tm{font-size:25px;font-weight:700;color:#1A1A18;text-align:right;white-space:nowrap}
.row .tm.hot{color:#C25E00}
.row .tm.wait{font-size:17px;font-weight:500;color:#8A8A86}
.row .arrow{color:#C0C0BC;font-size:19px}
.row.first{border-top:2px solid #F0EFEC}

.more{
  padding:20px;text-align:center;font-size:18px;color:#0B4F8A;
  cursor:pointer;font-weight:600;
}

.sbar{display:flex;gap:8px;padding:12px 14px;border-bottom:1px solid #EFEFEF;flex-shrink:0}
.sinput{
  flex:1;height:58px;border:2px solid #DDD;border-radius:12px;
  padding:0 14px;font-size:21px;font-family:inherit;outline:none;background:#fff;color:#111;
}
.sinput:focus{border-color:#378ADD}
.sbtn{
  width:84px;height:58px;border:none;border-radius:12px;background:#111;color:#fff;
  font-size:19px;font-weight:600;font-family:inherit;cursor:pointer;
}

.lhead{padding:14px 16px 12px;border-bottom:1px solid #EFEFEF;flex-shrink:0;background:#fff}
.lh1{display:flex;align-items:center;gap:12px}
.lh1 .ln{font-size:26px;font-weight:700}
.lh2{font-size:21px;font-weight:600;color:#1A1A18}
.lh2 b{font-weight:700}
.swap{
  margin-left:auto;flex-shrink:0;display:inline-flex;align-items:center;gap:5px;
  border:1.5px solid #0B4F8A;background:#fff;color:#0B4F8A;
  border-radius:999px;padding:10px 16px;
  font-size:15px;font-weight:700;font-family:inherit;cursor:pointer;line-height:1;
}
.lh3{font-size:14px;color:#8A8A86;margin-top:5px}
.noreal{
  background:#FFF4E5;color:#8A5200;border-radius:8px;
  padding:9px 12px;font-size:14px;margin-top:9px;line-height:1.4;
}

.tl{position:relative;padding:14px 0 40px}
.stop{
  display:flex;align-items:center;gap:14px;
  padding:0 16px 0 16px;height:62px;position:relative;
}
.stop .rail{position:absolute;left:30px;top:0;bottom:0;width:2px;background:#AEC6DD}
.stop:first-child .rail{top:50%}
.stop:last-child .rail{bottom:50%}
.dot{
  position:relative;z-index:1;width:14px;height:14px;border-radius:50%;
  background:#fff;border:2px solid #A8BED4;flex-shrink:0;margin-left:16px;
  box-sizing:border-box;
}
.dot.mine{border-color:#0B4F8A;background:#0B4F8A;box-shadow:0 0 0 5px rgba(11,79,138,.16)}
.dot.bus{border-color:#D97706;background:#D97706;box-shadow:0 0 0 5px rgba(217,119,6,.18)}
.sname{font-size:21px;color:#222;flex:1}
.sname.mine{font-weight:700;color:#0B4F8A}
.tagme{
  font-size:13px;font-weight:700;color:#fff;background:#0B4F8A;
  border-radius:6px;padding:3px 8px;
}
.tagbus{
  font-size:13px;font-weight:700;color:#fff;background:#D97706;
  border-radius:6px;padding:3px 8px;
}
.stop.mine{background:#F0F6FD}
.stop.busrow{background:#FFF9F0}
.stop.mine.busrow{background:#F0F6FD}
.busmeta{font-size:13px;color:#B06000;margin-left:8px}

.btnrow{display:flex;gap:10px;padding:12px 16px 14px;flex-shrink:0;border-top:1px solid #EFEFEC}
.btn{
  flex:1;height:70px;border:none;border-radius:18px;font-size:19px;
  font-weight:600;font-family:inherit;cursor:pointer;
}
.btn.p{background:#0B1F33;color:#fff}
.btn.s{background:#F2F1EE;color:#1A1A1A}
.btn.on{background:#0B4F8A;color:#fff}
.tip{font-size:13px;color:#999;text-align:center;padding:6px 0 2px}
.loading{padding:60px 20px;text-align:center;font-size:19px;color:#888}
.err{background:#FDECEC;border:2px solid #E88;border-radius:14px;padding:18px;margin:14px}
.err h3{font-size:21px;color:#A32D2D;margin-bottom:6px}
.err p{font-size:16px;color:#444;line-height:1.5}
"""

JS = r"""
var HOME_STATION = "__HOME_STATION__";
var HOME_LINE = "__HOME_LINE__";
var speakOn = false;
var timer = null;
var _fired = {};
var _bannerHot = false;

function pad(n){return n<10?"0"+n:""+n}
function esc(s){return (s||"").replace(/[&<>"]/g,function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c];});}

function ls(k,v){
  try{
    if(v===undefined) return localStorage.getItem(k);
    localStorage.setItem(k,v);
  }catch(e){ return null; }
}

function speak(text){
  if(!speakOn || !window.speechSynthesis || !text) return;
  window.speechSynthesis.cancel();
  var u = new SpeechSynthesisUtterance(text);
  u.lang="zh-CN"; u.rate=0.85; u.pitch=1.0;
  window.speechSynthesis.speak(u);
}

function api(url){
  var D = window.__DATA__ || null;
  if(D){
    if(D[url]) return Promise.resolve(D[url]);
    return Promise.resolve({ok:false, error:"演示版只内置了几个例子，跑本地服务才能查全部"});
  }
  return fetch(url,{cache:"no-store"}).then(function(r){return r.json();});
}

/* ---------------------------------------------------------- 到站提醒 */
function remAt(){
  var v = parseInt(ls("remAt") || "0", 10);
  return isNaN(v) ? 0 : v;
}

function initAudio(){
  if(window._ac) return;
  try{
    var AC = window.AudioContext || window.webkitAudioContext;
    if(AC) window._ac = new AC();
  }catch(e){}
}

/* 三声短促的提示音。用振荡器现场合成，不依赖任何音频文件 */
function beep(n){
  var ac = window._ac;
  if(!ac) return;
  try{
    if(ac.state === "suspended") ac.resume();
    var t0 = ac.currentTime + 0.02;
    for(var i = 0; i < n; i++){
      var o = ac.createOscillator(), g = ac.createGain();
      o.type = "sine";
      o.frequency.setValueAtTime(i % 2 ? 620 : 880, t0 + i * 0.40);
      g.gain.setValueAtTime(0.0001, t0 + i * 0.40);
      g.gain.exponentialRampToValueAtTime(0.45, t0 + i * 0.40 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + i * 0.40 + 0.30);
      o.connect(g); g.connect(ac.destination);
      o.start(t0 + i * 0.40); o.stop(t0 + i * 0.40 + 0.32);
    }
  }catch(e){}
}

function buzz(p){
  try{ if(navigator.vibrate) navigator.vibrate(p); }catch(e){}
}

function showBanner(t, s, hot){
  var b = document.getElementById("banner");
  if(!b) return;
  _bannerHot = !!hot;
  b.className = "banner" + (hot ? " hot" : "");
  b.innerHTML = '<div class="btext"><div class="bt">' + esc(t) + '</div>'
              + (s ? '<div class="bs">' + esc(s) + '</div>' : '') + '</div>'
              + '<button class="bx" onclick="hideBanner()">知道了</button>';
  void b.offsetWidth;
  b.className += " show";
}

function hideBanner(){
  var b = document.getElementById("banner");
  if(b) b.className = "banner" + (_bannerHot ? " hot" : "");
}

function openSheet(){
  var m = document.getElementById("mask"), s = document.getElementById("sheet");
  if(m) m.classList.add("show");
  if(s) s.classList.add("show");
  var at = remAt(), os = document.querySelectorAll(".opt");
  for(var i = 0; i < os.length; i++){
    os[i].className = "opt" + (parseInt(os[i].getAttribute("data-n"), 10) === at ? " sel" : "");
  }
}

function closeSheet(){
  var m = document.getElementById("mask"), s = document.getElementById("sheet");
  if(m) m.classList.remove("show");
  if(s) s.classList.remove("show");
}

function pickAt(n){
  initAudio();
  beep(1);
  ls("remAt", String(n));
  _fired = {};
  closeSheet();
  viewHome();
  syncWatch();
  showBanner("响铃已开", "车还有 " + n + " 站时会响一声", false);
  setTimeout(hideBanner, 2800);
}

function turnOff(){
  ls("remAt", "0");
  _fired = {};
  closeSheet();
  viewHome();
  syncWatch();
}

/* 每次轮询后检查。同一趟车只响一次，车走了再响下一趟 */
function checkRemind(main){
  var at = remAt();
  if(!at || !main) return;
  if(bridge()) return;   // App 里交给后台服务响，网页再响一次就成了两声
  var st = main.stations, k = main.dir || "1";

  if(st !== null && st > at){ delete _fired[k + "w"]; delete _fired[k + "n"]; }

  if(st !== null && st <= at && !_fired[k + "w"]){
    _fired[k + "w"] = 1;
    beep(3); buzz([280, 150, 280]);
    showBanner("车还有 " + st + " 站", "该出门了，往 " + (main.toShort || ""), false);
  }
  if((main.status === "here" || main.minutes === 0) && !_fired[k + "n"]){
    _fired[k + "n"] = 1; _fired[k + "w"] = 1;
    beep(4); buzz([300, 140, 300, 140, 300]);
    showBanner("车到站了", "快上车，往 " + (main.toShort || ""), true);
  }
}

/* --------------------------------------------------- 和 App（安卓壳）对接
   浏览器里没有 AndroidBridge，下面每个函数都静默跳过，网页行为一点不变。
   装成 App 之后，响铃由后台服务负责 —— 切出去、锁屏都还在看着。 */
var _watch = null;

function bridge(){
  return (typeof AndroidBridge !== "undefined" && AndroidBridge) ? AndroidBridge : null;
}

/* 把「现在在看哪条线、响几站」告诉 App。离开到站卡片就不动它：
   老人设好提醒往往直接按 Home 键，这时 _watch 还留着才是对的。 */
function syncWatch(){
  var B = bridge(); if(!B) return;
  try{
    if(!_watch){ B.setWatch("", "", "", 0); return; }
    B.setWatch(_watch.line, _watch.dir, _watch.station, remAt());
  }catch(e){}
}

function go(hash){
  if(location.hash === hash){ route(); } else { location.hash = hash; }
}

/* 一个站有哪些车：每行 = 一条线的一个方向。首页和站牌页共用这一份。
   点进去就是那张到站卡片，方向已经在行上选好了。 */
function stationRows(lines, station, limit){
  limit = limit || 6;
  var h = "";
  for(var i = 0; i < lines.length; i++){
    var v = lines[i];
    var hidden = i >= limit;
    var tm = "", tcls = "";
    if(v.status === "coming" && v.minutes !== null){
      tm = (v.minutes === 0 ? "马上到" : v.minutes + "′");
      if(v.minutes <= 2){ tcls = "hot"; }
    }
    else if(v.status === "here"){ tm = "在站上"; tcls = "hot"; }
    else if(v.status === "waiting"){ tm = "等发车"; tcls = "wait"; }
    else if(v.status === "closed"){ tm = "收班"; tcls = "wait"; }
    else { tm = "—"; tcls = "wait"; }

    var href = '#/b/' + encodeURIComponent(v.line) + '/' + v.dir
             + '?st=' + encodeURIComponent(station);
    h += '<div class="row' + (i === 0 ? " first" : "") + '" '
       + (hidden ? 'style="display:none"' : '') + ' data-late="' + (hidden ? 1 : 0) + '" '
       + 'onclick="go(\'' + href + '\')">'
       + '<span class="ln">' + esc(v.line) + '</span>'
       + '<span class="dst">往 ' + esc(v.toShort) + '</span>'
       + '<span class="tm ' + tcls + '">' + tm + '</span>'
       + '<span class="arrow">›</span></div>';
  }
  return h;
}

/* 首页 = 附近站牌 + 搜索。这里只负责选「哪条线哪个方向」，
   具体的到站大卡片在 #/b/线路/方向 那一页。 */
function viewHome(){
  var el = document.getElementById("app");
  el.innerHTML = '<div class="loading">正在查这站有哪些车…</div>';
  api("/api/home").then(function(p){
    if(!p.ok){ el.innerHTML = errBox("查不到", p.error); return; }
    var lines = p.lines || [];
    if(!lines.length){ el.innerHTML = errBox("这个站没有线路", "换个站试试"); return; }

    var html = '<div class="nav"><span class="t">'+esc(p.station)+'站</span>'
             + '<span class="r" id="clock"><i class="live"></i>'+p.updated+'</span></div>';

    html += '<div class="sbar">'
          + '<input id="hkw" class="sinput" type="search" inputmode="search" '
          + 'placeholder="搜线路号或站名" '
          + 'onkeydown="if(event.key===\'Enter\'){event.preventDefault();homeSearch();}">'
          + '<button class="sbtn" onclick="homeSearch()">搜</button></div>';

    html += '<div class="scroll flush">';
    html += '<div class="sec" style="padding:12px 16px 6px">附近站牌 · 有车的在前</div>';
    html += '<div id="lst">' + stationRows(lines, p.station) + '</div>';
    if(lines.length > 6){
      html += '<div class="more" id="more" onclick="showMore()">还有 '
            + (lines.length - 6) + ' 条线，点这里看 ›</div>';
    }
    if(lines.length <= 3){
      html += '<div class="tip" style="padding:26px 16px 10px">这站就这几趟车。'
            + '想查别的线路，用上面的搜索框</div>';
    }
    html += '</div>';
    el.innerHTML = html;
  }).catch(function(){ el.innerHTML = errBox("连不上", "检查电脑上的程序是否还在运行"); });
}

function homeSearch(){
  var v = (document.getElementById("hkw").value || "").trim();
  if(!v) return;
  go('#/search?kw=' + encodeURIComponent(v));
}

/* 到站卡片：一条线一个方向，就是原来首页那张卡，现在可以装任意线路 */
function viewBoard(line, dir, station){
  var el = document.getElementById("app");
  // 换了线路或方向，上一次选中的站就不作数了；同一条线刷新则保留
  if(_picked && _picked.key !== (line + "/" + dir)) _picked = null;
  el.innerHTML = '<div class="loading">正在查车…</div>';
  api("/api/board?line=" + encodeURIComponent(line)
    + "&dir=" + encodeURIComponent(dir)
    + "&station=" + encodeURIComponent(station || ""))
  .then(function(p){
    if(!p.ok){ el.innerHTML = errBox("没查到车", p.error); return; }

    var html = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
             + '<span class="t">'+esc(p.station)+'站</span>'
             + '<span class="r"><i class="live"></i>'+p.updated+'</span></div>';
    html += '<div class="scroll home">';
    html += homeCard(p.main, p.other, p.win, p.station);
    html += '</div>';
    html += '<div class="btnrow">'
          + '<button class="btn s" onclick="go(\'#/s/\'+encodeURIComponent(p.station))">这站的车</button>'
          + '<button class="btn p" onclick="toggleSpeak()">'+(speakOn?"念 ✓":"念一遍")+'</button>'
          + '</div>';
    el.innerHTML = html;

    centerMyStop();
    restorePick();
    window._speech = mainSpeech(p.main, p.other);
    if(speakOn) speak(window._speech);
    _watch = {line: line, dir: dir, station: p.station};
    syncWatch();
    checkRemind(p.main);
  }).catch(function(){ el.innerHTML = errBox("连不上", "检查电脑上的程序是否还在运行"); });
}

/* 把站点列表滚到合适的位置：
   - 车在我上方 5 站以内 → 连车那行一起带进视野，老人真正想知道的是车开到哪了
   - 车更远或已经过站 → 以「你在这」为锚，上方留一行半
   用 getBoundingClientRect 算，不用 offsetTop —— offsetParent 会算错。 */
function centerMyStop(){
  var box = document.getElementById("swscroll");
  if(!box) return;
  var me = box.querySelector(".swrow.mine");

  // 这条线不经过我的站：没有「你在这」，就把视野滚到最近一辆车那儿
  if(!me){
    var anyBus = box.querySelector(".swrow.bus");
    if(anyBus){
      var d0 = anyBus.getBoundingClientRect().top - box.getBoundingClientRect().top;
      box.scrollTop = Math.max(0, box.scrollTop + d0 - box.clientHeight * 0.30);
    }
    return;
  }

  var rowH = me.offsetHeight || 42;
  var anchor = me, pad = rowH * 1.5;
  var busRow = box.querySelector(".swrow.bus");
  if(busRow){
    var gap = me.getBoundingClientRect().top - busRow.getBoundingClientRect().top;
    if(gap > 0 && gap <= rowH * 5.5){ anchor = busRow; pad = rowH * 0.5; }
  }

  var delta = anchor.getBoundingClientRect().top - box.getBoundingClientRect().top;
  var target = box.scrollTop + delta - pad;
  // 对齐到整行：不对齐的话首行会卡在框边被切掉一半，看起来像和上面那行叠在一起
  target = Math.round(target / rowH) * rowH;
  box.scrollTop = Math.max(0, Math.min(target, box.scrollHeight - box.clientHeight));
}

/* 读屏用的整句描述：把一张卡的信息压成一句话 */
function ariaText(m, station){
  var t = m.line + " 往 " + (m.toShort || "");
  if(m.status === "noroute") t += "，这条线不经过" + (station || "这") + "站";
  else if(m.status === "here") t += "，车已经到站";
  else if(m.status === "coming" && m.minutes !== null){
    t += "，还有 " + m.minutes + " 分钟";
    if(m.stations !== null) t += "，" + m.stations + " 站";
  }
  else if(m.status === "waiting") t += "，等待发车";
  else if(m.status === "closed") t += "，已经收班";
  else t += "，暂时没有车";
  return t;
}

function mainSpeech(main, other){
  var t = "往"+main.toShort+"，";
  if(main.status==="noroute") t += "这条线不经过这站";
  else if(main.status==="here") t += "车在站上";
  else if(main.status==="coming" && main.minutes!==null) t += (main.minutes===0?"车马上到":"还有"+main.minutes+"分钟");
  else if(main.status==="waiting") t += "等发车";
  else if(main.status==="closed") t += "已收班";
  else t += "暂无车";
  if(other){
    t += "。反方向";
    if(other.status==="coming" && other.minutes!==null) t += (other.minutes===0?"车马上到":"还有"+other.minutes+"分钟");
    else if(other.status==="closed") t += "已收班";
    else t += "暂无车";
  }
  return t;
}

/* ---------------------------------------------- 点站点，看车多久到
   只改显示：不发请求、不动主数字、不新增块 —— 顶部「车现在在 X」那行就地变成估算，
   列表高度不变，所以不会跳。老人误触也就是多出一行，点 × 就回去了。 */
var _picked = null;      // {i, line, dir}：卡片每 15 秒重画一次，选中要能活过刷新

function pickStop(el){
  if(!el) return;
  var box = document.getElementById("swscroll");
  if(!box) return;

  var on = el.getAttribute("data-sel") === "1";
  var rows = box.querySelectorAll(".swrow");
  for(var i = 0; i < rows.length; i++){
    rows[i].removeAttribute("data-sel");
    rows[i].className = rows[i].className.replace(" sel", "");
  }
  if(on){ _picked = null; fillEta(null); return; }    // 再点一次就取消

  var r = rowOf(el);
  if(!r) return;
  _picked = {i: r.i, key: window._winKey || ""};
  el.setAttribute("data-sel", "1");
  el.className += " sel";
  fillEta(el);        // 先用本地算的，立刻有数
  etaFetch(el);       // 再问一次这一站，用真实到站覆盖
}

/* 问上游这一站的实时到站。点得快时只认最后一次，旧响应直接丢掉 */
var _etaSeq = 0;

function etaFetch(el){
  var r = rowOf(el);
  if(!r || !window._winKey) return;
  if(r.mine) return;                       // 就是我这站，主数字已经准了
  if(window.__DATA__) return;              // 离线演示页没有接口，用本地估算就够了
  var parts = window._winKey.split("/");
  var seq = ++_etaSeq;

  api("/api/eta?line=" + encodeURIComponent(parts[0])
      + "&dir=" + encodeURIComponent(parts[1])
      + "&station=" + encodeURIComponent(r.name))
  .then(function(p){
    if(seq !== _etaSeq) return;            // 已经点了别的站
    if(!p || !p.ok){
      r.status = "noroute";
      if(el.getAttribute("data-sel") === "1") fillEta(el);
      return;
    }
    r.status = p.status;
    r.eta = p.minutes;
    r.left = p.stations;
    r.passed = (p.status === "passed");
    if(el.getAttribute("data-sel") === "1") fillEta(el);
  })
  .catch(function(){});
}

function rowOf(el){
  var i = parseInt(el.getAttribute("data-i"), 10);
  var rows = (window._win && window._win.rows) || [];
  for(var k = 0; k < rows.length; k++){
    if(rows[k].i === i) return rows[k];
  }
  return null;
}

function fillEta(el){
  var bar = document.getElementById("swabove");
  if(!bar) return;

  if(!el){
    bar.className = "swabove";
    bar.innerHTML = (window._win && window._win.busHere)
      ? '车现在在 ' + esc(window._win.busHere) + ' · 点站点看多久到'
      : '点站点看车多久到';
    return;
  }

  var r = rowOf(el);
  if(!r) return;

  /* 上游的 status 优先于本地的「已过站」判断 —— 本地说的是当前这班车开过去了，
     上游回答的是「最近一班什么时候到这一站」，后者才是老人问的事。 */
  var st = r.status || "";
  var tail;
  if(st === "passed"){
    tail = '<b class="t">车已过站</b><span class="x">等下一班</span>';
  } else if(st === "closed"){
    tail = '<b class="t">今天收班了</b><span class="x">明天再来</span>';
  } else if(st === "waiting"){
    tail = '<b class="t">车还没发车</b><span class="x">等发车</span>';
  } else if(st === "here"){
    tail = '<b class="t">车在站上</b><span class="x">快上车</span>';
  } else if(st === "noroute"){
    tail = '<b class="t">查不到</b><span class="x">这站没车</span>';
  } else if(r.passed){
    tail = '<b class="t">车已过站</b><span class="x">等下一班</span>';
  } else if(r.eta !== null && r.eta !== undefined){
    tail = '<b class="t">约 ' + r.eta + ' 分钟</b><span class="x">· ' + r.left + ' 站</span>';
  } else if(r.left !== null && r.left !== undefined){
    tail = '<b class="t">还有 ' + r.left + ' 站</b><span class="x">无实时车</span>';
  } else {
    tail = '<b class="t">正在查…</b><span class="x">马上好</span>';
  }

  bar.className = "swabove hot";
  bar.innerHTML = '<span class="to">到 ' + esc(r.name) + '</span>' + tail
                + '<button class="bx" onclick="clearStop(event)" aria-label="取消选中">×</button>';
}

function clearStop(e){
  if(e && e.stopPropagation) e.stopPropagation();
  _picked = null;
  var box = document.getElementById("swscroll");
  if(box){
    var s = box.querySelector('.swrow[data-sel="1"]');
    if(s){ s.className = s.className.replace(" sel", ""); s.removeAttribute("data-sel"); }
  }
  fillEta(null);
}

/* 刷新后把选中接回来，并把视野停在那一站，别让老人重新找 */
function restorePick(){
  if(!_picked) return;
  var box = document.getElementById("swscroll");
  if(!box) return;
  var el = box.querySelector('.swrow[data-i="' + _picked.i + '"]');
  if(!el) return;
  el.setAttribute("data-sel", "1");
  el.className += " sel";
  fillEta(el);
  etaFetch(el);       // 15 秒刷新过一轮，这一站的数也要重问

  var rowH = el.offsetHeight || 42;
  var delta = el.getBoundingClientRect().top - box.getBoundingClientRect().top;
  var target = box.scrollTop + delta - box.clientHeight * 0.4;
  box.scrollTop = Math.max(0, Math.min(Math.round(target / rowH) * rowH,
                                       box.scrollHeight - box.clientHeight));
}

function homeCard(main, other, win, station){
  station = station || HOME_STATION;
  var cls = main.dir==="1" ? "up" : "dn";
  var urgent = (main.status==="coming" && main.minutes!==null && main.minutes<=3);
  var h = '<div class="card '+cls+(urgent?' urgent':'')+'">';

  var swapHtml = "";
  if(other){
    var otxt = "暂无车";
    if(other.status==="coming" && other.minutes!==null){
      otxt = (other.minutes===0?"马上到":other.minutes+"分");
    } else if(other.status==="here"){ otxt = "在站上"; }
    else if(other.status==="waiting"){ otxt = "等发车"; }
    else if(other.status==="closed"){ otxt = "已收班"; }
    // 只写动作，不写反方向的终点和分钟 —— 宽度留给「往 XX」，
    // 不然像「往 浙江东方学院」这种长站名会被拆成「…学」「院」两行
    swapHtml = '<button class="swapbtn" aria-label="换到往' + esc(other.toShort) + '的方向，' + otxt + '" '
             + 'onclick="swapDir(\'' + other.dir + '\',\'' + esc(main.line) + '\',\'' + esc(station) + '\')">'
             + '<span class="si">⇄</span> 换方向</button>';
  }

  h += '<div class="ctop"><span class="lineno '+cls+'">'+esc(main.line)+'</span>'
     + '<span class="toward">往 '+esc(main.toShort)+'</span>'
     + swapHtml + '</div>';

  h += '<div class="cmid" role="img" aria-label="' + esc(ariaText(main, station)) + '">';
  if(main.status==="noroute"){
    h += '<div class="stxt '+cls+'" style="font-size:30px;line-height:1.25">不经过 '+esc(station)+'站</div>'
       + '<div class="sub">下面是全程站点和车开到哪了</div>';
  } else if(main.status==="here"){
    h += '<div class="stxt '+cls+'">车在站上</div><div class="sub">快上车</div>';
  } else if(main.status==="coming" && main.minutes!==null){
    if(main.minutes===0){
      h += '<div class="stxt '+cls+'">马上到</div><div class="sub"><b class="go">快上车</b>车就在附近</div>';
    } else {
      h += '<div class="main"><span class="min '+cls+'">'+main.minutes+'</span>'
         + '<span class="unit '+cls+'">分钟</span></div>'
         + '<div class="sub">'+(urgent?'<b class="go">该出门了</b> · ':'')
         + '还有 <b>'+(main.stations!==null?main.stations+" 站":"几站")+'</b></div>';
    }
  } else if(main.status==="waiting"){
    h += '<div class="stxt '+cls+'">等发车</div><div class="sub">'+esc(main.dist)+'</div>';
  } else if(main.status==="closed"){
    h += '<div class="stxt '+cls+'">已收班</div><div class="sub">明天再来</div>';
  } else {
    h += '<div class="stxt '+cls+'">'+esc(main.node||"暂无车")+'</div>';
  }
  h += '</div>';

    if(win && win.rows && win.rows.length){
    h += '<div class="swin">';
    h += '<div class="swabove" id="swabove">'
       + (win.busHere ? '车现在在 '+esc(win.busHere)+' · 点站点看多久到' : '点站点看车多久到')
       + '</div>';
    h += '<div class="swscroll" id="swscroll">';
    for(var wi = 0; wi < win.rows.length; wi++){
      var r = win.rows[wi];
      h += '<div class="swrow' + (r.mine ? ' mine' : '') + (r.bus ? ' bus' : '') + '"'
         + ' data-i="' + r.i + '" onclick="pickStop(this)">'
         + '<span class="d"></span>'
         + '<span class="n">' + esc(r.name) + '</span>'
         + (r.mine ? '<span class="tm2">你在这</span>' : '')
         + (r.bus ? '<span class="tb">车</span>' : '')
         + '</div>';
    }
    h += '</div></div>';
    window._win = win;
    window._winKey = main.line + "/" + main.dir;
  }

  var remTxt = remAt() ? ('响铃中 · ' + remAt() + ' 站') : '到站响铃';
  var remCls = remAt() ? 'remlink on' : 'remlink';
  var remHtml = '<button class="' + remCls + '" aria-pressed="' + (remAt() ? 'true' : 'false')
              + '" onclick="openSheet()">'
              + remTxt + '</button>';
  h += '<div class="cfoot"><span>' + (win ? '全程 ' + win.total + ' 站' : '') + '</span>' + remHtml + '</div>';
  h += '</div>';
  return h;
}

/* 换反方向：换的是同一张卡片的方向，不是回首页重新选。
   用 replace 不新增历史 —— 否则连点几次换方向，返回要按好几下才回得到首页。 */
function swapDir(d, line, station){
  ls("prefDir", d);
  if(line){
    location.replace('#/b/' + encodeURIComponent(line) + '/' + d
      + '?st=' + encodeURIComponent(station || HOME_STATION));
  } else {
    viewHome();
  }
}

function toggleSpeak(){
  speakOn = !speakOn;
  var b = document.getElementById("spk");
  if(b){ b.textContent = speakOn?"自动念 ✓":"念一遍"; b.className = "btn "+(speakOn?"on":"p"); }
  if(speakOn && window._speech){ speak(window._speech); }
}

function errBox(t, m){
  return '<div class="err"><h3>'+esc(t)+'</h3><p>'+esc(m||"稍后再试")+'</p></div>';
}

function viewStation(name){
  var el = document.getElementById("app");
  el.innerHTML = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
    + '<span class="t">'+esc(name)+'</span></div><div class="scroll"><div class="loading">正在查…</div></div>';
  api("/api/station?name="+encodeURIComponent(name)).then(function(p){
    if(!p.ok){ el.innerHTML = errBox("查不到这个站", p.error); return; }
    var lines = p.lines || [];
    if(!lines.length){ el.innerHTML = errBox("这个站没有线路", "换个站试试"); return; }

    var LIMIT = 6;
    var html = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
             + '<span class="t">'+esc(p.station)+'</span>'
             + '<button class="navlink" onclick="go(\'#/search\')">换站 ›</button></div>';

    html += '<div class="scroll flush"><div class="sec" style="padding:12px 16px 6px">'
          + '有车的排在前面</div>';
    html += '<div id="lst">';
    html += '<div id="lst">' + stationRows(lines, name, LIMIT) + '</div>';
    if(lines.length > LIMIT){
      html += '<div class="more" id="more" onclick="showMore()">还有 '+(lines.length-LIMIT)+' 条线，点这里看 ›</div>';
    }
    html += '<div class="tip">更新于 '+p.updated+'</div></div>';
    el.innerHTML = html;
  }).catch(function(){ el.innerHTML = errBox("连不上", "稍后再试"); });
}

function showMore(){
  var rows = document.querySelectorAll('[data-late="1"]');
  for(var i=0;i<rows.length;i++){ rows[i].style.display="flex"; }
  var m = document.getElementById("more");
  if(m) m.style.display="none";
}

function viewSearch(kwArg){
  var el = document.getElementById("app");
  if(kwArg) window._kw = kwArg;
  var kw = window._kw || "";
  el.innerHTML = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
    + '<span class="t">查线路</span></div>'
    + '<div class="sbar"><input id="kw" class="sinput" type="search" inputmode="search" '
    + 'placeholder="输线路号，比如 36" value="' + esc(kw) + '" '
    + 'onkeydown="if(event.key===\'Enter\'){event.preventDefault();doSearch();}">'
    + '<button class="sbtn" onclick="doSearch()">搜</button></div>'
    + '<div class="scroll" id="sres"></div>';
  if(kw){ doSearch(); }
  else {
    document.getElementById("sres").innerHTML =
      '<div class="panel"><div class="sec">输线路号或站名，比如 36、159、石坦</div></div>';
  }
  var inp = document.getElementById("kw");
  if(inp && !kw){ setTimeout(function(){ inp.focus(); }, 120); }
}

function doSearch(){
  var kw = (document.getElementById("kw").value || "").trim();
  if(!kw) return;
  window._kw = kw;
  var box = document.getElementById("sres");
  box.innerHTML = '<div class="loading">正在搜…</div>';
  api("/api/search?kw=" + encodeURIComponent(kw)).then(function(p){
    if(!p.ok){ box.innerHTML = errBox("搜不了", p.error); return; }
    var h = "";
    var lines = p.lines || [], stations = p.stations || [];
    if(lines.length){
      var lt = p.linesTotal || lines.length;
      h += '<div class="sec">线路 ' + (lt > lines.length ? lines.length + ' / 共 ' + lt + ' 条' : lines.length + ' 条') + '</div>';
      for(var i = 0; i < lines.length; i++){
        var v = lines[i];
        if(v.dirs && v.dirs.length > 1){
          // 线路号精确命中的，两个方向直接摊开 —— 点了就是那张到站卡片
          for(var j = 0; j < v.dirs.length; j++){
            var dd = v.dirs[j];
            var hr = '#/b/' + encodeURIComponent(v.line) + '/' + dd.dir;
            h += '<div class="row srow" onclick="go(\'' + hr + '\')">'
               + '<span class="ln">' + esc(v.line) + '</span>'
               + '<span class="dst">往 ' + esc(dd.toShort)
               + '　<span class="dstop">' + dd.stopCount + ' 站</span></span>'
               + '<span class="arrow">›</span></div>';
          }
        } else {
          // 同名的其他线路：只列一行，点进去再选方向
          var href = '#/d/' + encodeURIComponent(v.line);
          h += '<div class="row srow" onclick="go(\'' + href + '\')">'
             + '<span class="ln">' + esc(v.line) + '</span>'
             + '<span class="dst">' + esc(v.from) + ' → ' + esc(v.to) + '</span>'
             + '<span class="arrow">›</span></div>';
        }
      }
    }
    if(stations.length){
      var st = p.stationsTotal || stations.length;
      h += '<div class="sec">站点 ' + (st > stations.length ? stations.length + ' / 共 ' + st + ' 个' : stations.length + ' 个') + '</div>';
      for(var j = 0; j < stations.length; j++){
        var s = stations[j];
        var sh = '#/s/' + encodeURIComponent(s.name);
        h += '<div class="row" onclick="go(\'' + sh + '\')">'
           + '<span class="ln" style="font-size:19px;min-width:auto;flex:1">'
           + esc(s.name) + '</span><span class="arrow">›</span></div>';
      }
    }
    if(p.skipped){
      h += '<div class="sec">另有 ' + p.skipped + ' 条线路没有实时到站数据，已隐藏</div>';
    }
    if((p.linesTotal || 0) > lines.length || (p.stationsTotal || 0) > stations.length){
      h += '<div class="sec">结果比较多，只列出最相近的几条。把线路号或站名输完整一些更准</div>';
    }
    if(!h){
      h = '<div class="sec">没搜到。站名要写全 —— '
        + '比如温州不叫「火车站」，叫「火车温州站」</div>';
    }
    box.innerHTML = '<div class="panel">' + h + '</div>';
  }).catch(function(){ box.innerHTML = errBox("连不上", "稍后再试"); });
}

/* 返回：优先回上一页，没有上一页才回首页。
   以前一律回首页，从站牌页点进来再返回就丢了原来的站位。 */
function back(){
  if(history.length > 1){ history.back(); }
  else { go('#/'); }
}

/* 选方向 —— 只有「知道坐几路、不知道往哪边开」的时候才走这一页。
   从站牌页点进来的人，那一行本来就写了「往 浙南科技城 还有 3 分钟」，
   方向已经选完了，不会再经过这里。 */
function viewDirs(line, from){
  var el = document.getElementById("app");
  el.innerHTML = '<div class="loading">正在查这条线…</div>';
  api("/api/dirs?line=" + encodeURIComponent(line) + "&from=" + encodeURIComponent(from||""))
  .then(function(p){
    if(!p.ok || !p.dirs || !p.dirs.length){
      el.innerHTML = errBox("查不到这条线", p.error || "换个线路号试试"); return;
    }

    // 环线之类只有一个方向，就别让他白选一次
    if(p.dirs.length === 1){
      go('#/l/' + encodeURIComponent(p.line) + '/' + p.dirs[0].dir
         + '?f=' + encodeURIComponent(from||""));
      return;
    }

    var html = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
             + '<span class="t">'+esc(p.line)+'</span></div>';

    html += '<div class="scroll">';
    html += '<div class="dhint">'
          + (from ? '从'+esc(from)+'上车，选往哪边开' : '选往哪边开')
          + '</div>';

    for(var i=0;i<p.dirs.length;i++){
      var v = p.dirs[i];
      var href = '#/l/' + encodeURIComponent(p.line) + '/' + v.dir
               + '?f=' + encodeURIComponent(from||"");
      var live = "";
      if(v.minutes !== null && v.minutes !== undefined){
        live = '<span class="dmin">' + (v.minutes === 0 ? "马上到" : v.minutes + " 分钟") + '</span>';
        if(v.stations) live += '<span class="dst2">还有 ' + v.stations + ' 站</span>';
      } else if(v.busCount){
        live = '<span class="dnum">' + v.busCount + ' 辆车在路上</span>';
      } else if(!v.hasReal){
        live = '<span class="dnum">这条线没有实时数据</span>';
      }

      html += '<div class="dircard" onclick="go(\''+href+'\')">'
            + '<div class="dto"><span class="dtoward">往</span>'+esc(v.toShort)+'</div>'
            + '<div class="dmeta">共 '+v.stopCount+' 站'
            + (v.begin ? '　'+esc(v.begin)+'–'+esc(v.end) : '') + '</div>'
            + (live ? '<div class="dlive">'+live+'</div>' : '')
            + '</div>';
    }
    html += '</div>';
    el.innerHTML = html;
  }).catch(function(){ el.innerHTML = errBox("连不上", "检查电脑上的程序是否还在运行"); });
}

function viewLine(line, dir, focus){
  var el = document.getElementById("app");
  el.innerHTML = '<div class="loading">正在查线路…</div>';
  api("/api/line?name="+encodeURIComponent(line)+"&dir="+dir+"&focus="+encodeURIComponent(focus||""))
  .then(function(p){
    if(!p.ok || !p.stops || !p.stops.length){
      el.innerHTML = errBox("查不到这条线", p.error); return;
    }
    var other = dir==="1" ? "2" : "1";
    var stopMap = {};
    for(var i=0;i<p.buses.length;i++){
      if(p.focus && p.buses[i].index >= p.focus) continue;
      stopMap[p.buses[i].index] = p.buses[i];
    }

    var hrefSwap = '#/l/' + encodeURIComponent(p.line) + '/' + other + '?f=' + encodeURIComponent(focus||"");
    var meta = [];
    if(p.begin) meta.push('首班 ' + p.begin);
    if(p.end) meta.push('末班 ' + p.end);
    meta.push('共 ' + p.stops.length + ' 站');

    var html = '<div class="nav"><button class="back" onclick="back()">‹ 返回</button>'
             + '<span class="t">'+esc(p.line)+'</span></div>';

    html += '<div class="lhead"><div class="lh1">'
          + '<div class="lh2">往 <b>'+esc(p.toShort)+'</b></div>'
          + '<button class="swap" onclick="go(\''+hrefSwap+'\')">⇄ 换个方向</button></div>'
          + '<div class="lh3">'+esc(meta.join('　'))+'</div>'
          + (p.hasReal ? '' : '<div class="noreal">这条线没有实时到站数据，只能看站点顺序</div>')
          + '</div>';

    html += '<div class="scroll flush">';
    html += '<div class="tl">';
    for(var i=0;i<p.stops.length;i++){
      var s = p.stops[i];
      var mine = (p.focus && s.i === p.focus);
      var bus = stopMap[s.i];
      var dotcls = "dot" + (mine?" mine":"") + (bus?" bus":"");
      var rowcls = "stop" + (mine?" mine":"") + (bus?" busrow":"");
      html += '<div class="'+rowcls+'" id="s'+s.i+'">'
            + '<div class="rail"></div>'
            + '<div class="'+dotcls+'"></div>'
            + '<div class="sname'+(mine?" mine":"")+'">'+esc(s.name)+'</div>';
      if(mine) html += '<span class="tagme">你在这</span>';
      if(bus)  html += '<span class="tagbus">车</span>';
      html += '</div>';
    }
    html += '</div>';
    html += '<div class="tip">更新于 '+p.updated+'　'
          + (p.hasReal ? ('在途 '+p.buses.length+' 辆') : '暂无实时数据') + '</div>';
    html += '</div>';
    el.innerHTML = html;

    if(p.focus){
      var node = document.getElementById("s"+p.focus);
      if(node){
        setTimeout(function(){
          var sc = el.querySelector(".scroll");
          var top = node.offsetTop - sc.clientHeight/2 + node.offsetHeight/2;
          sc.scrollTop = Math.max(0, top);
        }, 60);
      }
    }
  }).catch(function(){ el.innerHTML = errBox("连不上", "稍后再试"); });
}

function route(){
  var h = location.hash || "#/";
  var el = document.getElementById("app");
  if(timer){ clearInterval(timer); timer = null; }

  var q = "";
  var qi = h.indexOf("?");
  if(qi >= 0){ q = h.slice(qi+1); h = h.slice(0,qi); }
  var params = {};
  q.split("&").forEach(function(kv){
    if(!kv) return; var a = kv.split("=");
    params[decodeURIComponent(a[0])] = decodeURIComponent(a[1]||"");
  });

  var parts = h.replace(/^#\/?/, "").split("/");

  if(parts[0] === "" ){ viewHome(); timer = setInterval(viewHome, 20000); return; }
  if(parts[0] === "s"){ viewStation(decodeURIComponent(parts[1]||"")); timer = setInterval(function(){ viewStation(decodeURIComponent(parts[1]||"")); }, 20000); return; }
  if(parts[0] === "b"){
    var bl = decodeURIComponent(parts[1]||""), bd = parts[2]||"1", bs = params.st||"";
    viewBoard(bl, bd, bs);
    timer = setInterval(function(){ viewBoard(bl, bd, bs); }, 15000);
    return;
  }
  if(parts[0] === "d"){ viewDirs(decodeURIComponent(parts[1]||""), params.from || ""); return; }
  if(parts[0] === "l"){ viewLine(decodeURIComponent(parts[1]||""), parts[2]||"1", params.f||""); return; }
  if(parts[0] === "search"){ viewSearch(params.kw || ""); return; }

  viewHome();
}

/* 手机浏览器要求先有一次点击才允许出声。进来先建好，点屏幕任意处解锁 */
initAudio();
document.addEventListener("pointerdown", function(){
  initAudio();
  if(window._ac && window._ac.state === "suspended"){
    try{ window._ac.resume(); }catch(e){}
  }
}, {passive:true});

window.addEventListener("hashchange", route);
route();



/* 调试用：地址加 ?sheet=1 直接弹出响铃面板，方便截图核对 */
if(location.search.indexOf("sheet=1") >= 0){
  setTimeout(function(){ try{ openSheet(); }catch(e){} }, 2600);
}

/* 调试用：地址加 ?pick=站序 自动选中那一站，方便截图核对估算条
   （只点一次 —— pickStop 是开关，点两下就取消了） */
(function(){
  var m = location.search.match(/[?&]pick=(\d+)/);
  if(!m) return;
  var hit = false;
  var t = setInterval(function(){
    if(hit) return;
    var row = document.querySelector('.swrow[data-i="' + m[1] + '"]');
    if(row){ hit = true; clearInterval(t); pickStop(row); }
  }, 250);
  setTimeout(function(){ clearInterval(t); }, 9000);
})();

/* 装成 App 之后，响铃的那行说明要换掉 —— 后台也响是这个版本的主要卖点。
   顺便在面板最下面露一行服务器地址，点一下能改。 */
(function nativeUI(){
  var B = bridge(); if(!B) return;
  var l = document.getElementById("limitline");
  if(l){
    l.textContent = "切到后台、锁屏也会响";
    l.style.cssText = "background:#EAF5EE;color:#1B7A46;border-color:#CDE6D8";
  }
  var s = document.getElementById("srvline");
  if(s){
    var addr = "";
    try{ addr = B.server(); }catch(e){}
    s.style.cssText = "margin-top:14px;padding-top:12px;border-top:1px solid #EFEEE8;"
                    + "text-align:center;font-size:13px;color:#8A8F94;line-height:1.6";
    s.textContent = "服务器 " + addr + " · 点了能改";
    s.onclick = function(){ try{ B.settings(); }catch(e){} };
  }
})();
"""

REMIND_DOM = (
    '<div class="banner" id="banner"></div>'
    '<div class="mask" id="mask" onclick="closeSheet()"></div>'
    '<div class="sheet" id="sheet">'
    '<h4>到站响铃</h4>'
    '<div class="hint">车还有几站时，提示一次并响一声</div>'
    '<div class="opts">'
    '<button class="opt" data-n="2" onclick="pickAt(2)">2 站<small>推荐</small></button>'
    '<button class="opt" data-n="3" onclick="pickAt(3)">3 站<small>早点出门</small></button>'
    '<button class="opt" data-n="5" onclick="pickAt(5)">5 站<small>更早</small></button>'
    '</div>'
    '<button class="off" onclick="turnOff()">关掉响铃</button>'
    '<div class="limit" id="limitline">现在只有页面开着才响。锁屏、切到别的应用就不响了</div>'
    '<div id="srvline"></div>'
    '</div>'
)


def page_html(skin="a", pwa=False):
    """按皮肤生成页面。skin 不认识时退回 a。

    pwa=True 时才挂 manifest 和主屏图标 —— 离线单文件（file://）挂这些只会报错。
    """
    css = SKINS.get(skin) or SKINS.get("a") or CSS
    # 图标与状态栏底色跟着皮肤走，别让暖橘页面顶着深蓝图标
    theme = {"b": "#E9EAE4", "d": "#FFF8F1", "e": "#F6FAFF"}.get(skin, "#FAFAF7")
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
            "<body><div id=\"app\" style=\"flex:1;display:flex;flex-direction:column;"
            "overflow:hidden;min-height:0\"></div>" + REMIND_DOM +
            "<script>" + JS.replace("__HOME_STATION__", HOME_STATION)
            .replace("__HOME_LINE__", HOME_LINE) + "</script></body></html>")


PAGE = page_html("c")



# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype, extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {"Cache-Control": "no-store"}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, code, data, ctype, extra=None):
        self._send(code, data, ctype, extra)

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        q = urllib.parse.parse_qs(u.query)

        try:
            if path in ("/", "/index.html"):
                # 默认 c = 白卡 + V2 优化层；想对比旧版可以加 ?skin=a
                skin = (q.get("skin") or ["c"])[0].lower()
                self._send(200, page_html(skin, pwa=True), "text/html; charset=utf-8")

            elif path == "/api/home":
                self._json(build_home())

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
                    self._json(build_search(kw))

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
                skin = (q.get("skin") or ["a"])[0].lower()
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
                page = (
                    '<html><body style="margin:0;background:#777;display:flex;'
                    'justify-content:center;align-items:flex-start">'
                    '<iframe src="/?skin=%s%s" style="width:%dpx;height:%dpx;border:0;'
                    'background:#fff"></iframe></body></html>' % (sk, sub, w, hgt)
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

    try:
        import webbrowser
        webbrowser.open("http://127.0.0.1:%d" % PORT)
    except Exception:
        pass

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
