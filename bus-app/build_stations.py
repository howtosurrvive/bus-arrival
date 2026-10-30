#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把温州全市公交站点收进 stations.json。

上游没有「列出所有站」的接口（CMD 110 只按站名模糊搜，一次最多 30 条），
但有两件事可以做：

  1. CMD 114 传空关键字，会把温州所有线路一次性列出来（1000+ 条，含上下行）
  2. CMD 103 每条线的站表里直接带 station_lat / station_lon

于是全量站点 = 所有线路站表的并集。约 1000 次请求，并发跑几分钟。

用法：
    python build_stations.py              # 全量抓，覆盖 stations.json
    python build_stations.py --limit 30   # 只抓前 30 条线路，先验一下
    python build_stations.py --merge      # 只补新站，不删旧站

跑完 stations.json 里是 {站名: [[lat, lon], ...]}，同名多站台会留多个点。
"""

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://h5.mygolbs.com/ApiData.do"

# 上游按「城市条目」分库，不是按行政区。CMD 101 里属于温州的条目就这四个 ——
# 「温州市」那本已经含市区、苍南、泰顺、洞头（交运集团统一运营），
# 永嘉、平阳、文成各自单列。乐清、瑞安不在这套数据里（CMD 101 查无此条目）。
CITIES = ["温州市", "永嘉县", "平阳县", "文成县"]

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stations.json")

WORKERS = 6          # 上游是公益查询口，别开太大
RETRY = 2
TIMEOUT = 20

_lock = threading.Lock()
_stat = {"req": 0, "err": 0, "stops": 0, "nocoord": 0}


def post(params):
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
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def base(city):
    return {"CITYNAME": city, "CITYKEY": ""}


def all_routes():
    """CMD 114 空关键字 = 该城市条目下的全部线路。按 (城市, 线路名, 方向) 去重。"""
    seen, out = set(), []
    for city in CITIES:
        try:
            raw = post({**base(city), "CMD": "114", "KEYWORD": ""})
        except Exception as e:
            print("   %s 线路表拉取失败：%s" % (city, e))
            continue
        if str(raw.get("status")) != "1":
            print("   %s 线路表返回异常（status=%s），跳过" % (city, raw.get("status")))
            continue
        got = 0
        for b in raw.get("buslines") or []:
            name = (b.get("lineName") or "").strip()
            d = str(b.get("upperOrDown") or "").strip()
            if not name or not d:
                continue
            key = (city, name, d)
            if key in seen:
                continue
            seen.add(key)
            bean = b.get("routeBean") or {}
            out.append({
                "city": city,
                "line": name,
                "dir": d,
                "hasReal": str(bean.get("hasReal")) == "1",
                "company": (bean.get("company") or "").strip(),
            })
            got += 1
        print("   %-6s %4d 条" % (city, got))
    return out


def one_route(route):
    """拉一条线一个方向的站表，返回 [(名字, lat, lon), ...]。"""
    for attempt in range(RETRY + 1):
        try:
            raw = post({**base(route["city"]), "CMD": "103",
                        "LINENAME": route["line"], "DIRECTION": route["dir"]})
            rows = raw.get("data") or []
            got = []
            for s in rows:
                name = (s.get("stationName") or "").strip()
                if not name:
                    continue
                try:
                    lat = float(s.get("station_lat") or 0)
                    lon = float(s.get("station_lon") or 0)
                except (TypeError, ValueError):
                    lat = lon = 0.0
                got.append((name, lat, lon))
            with _lock:
                _stat["req"] += 1
                _stat["stops"] += len(got)
                _stat["nocoord"] += sum(1 for _, a, o in got if not a or not o)
            return route, got
        except Exception:
            if attempt >= RETRY:
                with _lock:
                    _stat["err"] += 1
                return route, []
            time.sleep(1.0 + attempt)
    return route, []


def merge_into(db, name, lat, lon):
    try:
        lat, lon = round(float(lat), 6), round(float(lon), 6)
    except (TypeError, ValueError):
        return False
    if not name or not lat or not lon:
        return False
    pts = db.setdefault(name, [])
    for q in pts:
        if abs(q[0] - lat) < 1e-5 and abs(q[1] - lon) < 1e-5:
            return False
    pts.append([lat, lon])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条线路，试水用")
    ap.add_argument("--merge", action="store_true", help="保留旧库里已有的站")
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    t0 = time.time()
    print("① 取各城市条目的线路表 …")
    routes = all_routes()
    real = [r for r in routes if r["hasReal"]]
    print("   共 %d 条（其中带实时数据 %d 条）" % (len(routes), len(real)))
    if args.limit:
        routes = routes[:args.limit]
        print("   试水模式：只跑前 %d 条" % len(routes))

    db = {}
    if args.merge and os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                db = json.load(f)
            print("   并入旧库 %d 个站名" % len(db))
        except Exception:
            db = {}

    print("② 逐条取站表（%d 并发）…" % args.workers)
    done = 0
    last = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for route, got in pool.map(one_route, routes):
            done += 1
            before = len(db)
            for name, lat, lon in got:
                merge_into(db, name, lat, lon)
            now = time.time()
            if now - last > 2 or done == len(routes):
                last = now
                print("   %4d/%d 线  站名 %d  (%d%%)  %.0fs"
                      % (done, len(routes), len(db),
                         done * 100 // max(1, len(routes)), now - t0))
            del before

    # 按站名排一下，文件更稳定，diff 也干净
    ordered = {k: db[k] for k in sorted(db)}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)

    pts = sum(len(v) for v in ordered.values())
    size = os.path.getsize(OUT)
    print("③ 完成")
    print("   线路 %d 条 / 请求 %d 次 / 失败 %d 次" % (len(routes), _stat["req"], _stat["err"]))
    print("   站名 %d 个 / 站台点 %d 个 / 无坐标 %d 条"
          % (len(ordered), pts, _stat["nocoord"]))
    print("   %s  %.1f KB  耗时 %.0fs" % (OUT, size / 1024.0, time.time() - t0))
    if _stat["err"]:
        print("   有失败请求，再跑一次 --merge 可以补齐")


if __name__ == "__main__":
    sys.exit(main())
