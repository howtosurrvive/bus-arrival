/* 手机里自己算 —— server.py 那套后端逻辑的 JS 版。
 *
 * 为什么要这一份：原来 App 只是个壳，数据全靠电脑上跑的 server.py，
 * 电脑一关、人一出门就查不了。而上游接口给的是 Access-Control-Allow-Origin: *，
 * 也就是说浏览器/WebView 可以直接请求它，不需要任何中转。
 *
 * 接口形状和 server.py 一模一样（/api/board 还是返回 {main, other, win...}），
 * 所以 app.js 一行都不用改 —— 它只认 window.localApi 在不在。
 *
 * 全部用 ES5 写：minSdk 21，老机器上的 WebView 可能没有 Promise 之外的
 * 新语法（箭头函数、模板字符串、Object.assign 都没有）。
 */
(function () {
  "use strict";

  // 告诉 app.js：这是没有 server.py 的环境，/api/* 由下面这个函数在本地算
  window.__ASSETS__ = true;

  var API = "https://h5.mygolbs.com/ApiData.do";
  var CITY = "温州市";
  var HOME_STATION = "石坦";
  var CACHE_RT = 12000;        // 实时数据 12 秒（和 server.py 一致）
  var CACHE_STOPS = 3600000;   // 站表 1 小时

  var rtCache = {};
  var stopsCache = {};
  var stationCacheP = null;
  var stationCache = null;

  function mix(a, b) {
    var o = {}, k;
    for (k in a) { if (a.hasOwnProperty(k)) o[k] = a[k]; }
    for (k in b) { if (b.hasOwnProperty(k)) o[k] = b[k]; }
    return o;
  }

  function hhmm() {
    var d = new Date();
    return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2);
  }

  /* ---------------------------------------------------------- 接口层 */

  function apiPost(params) {
    var parts = [], k;
    for (k in params) {
      if (params.hasOwnProperty(k)) {
        parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
      }
    }
    /* 走本地 /api/data，不直接打上游。
       上游有防盗链：只认 Origin: https://h5.mygolbs.com 的请求，别的来源
       一律回一串密文（实测是 base64，解不出 JSON）。浏览器和 WebView 里
       JS 改不了 Origin —— 它是禁止修改的请求头，所以只能由壳代发：
         · 电脑上跑：server.py 的 /api/data 转发
         · 手机上：WebView 的 shouldInterceptRequest 里用原生发
       两边返回的东西一模一样，所以这段代码在哪都能跑。 */
    return fetch(apiBase() + "?" + parts.join("&"), { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("接口返回 " + r.status);
        return r.json();
      });
  }

  /* 接口走哪儿：
     · 正常（https://bus.local 或电脑上的 /static/）→ 同源的 /api/data；
     · 万一页面是从 assets 直接以 file:// 打开的兜底路径 → 绝对地址，
       还得让原生拦截来发（file:// 下相对路径会变成 file:///api/data）。 */
  function apiBase() {
    return location.protocol === "file:"
      ? "https://bus.local/api/data"
      : "/api/data";
  }

  function base() { return { CITYNAME: CITY, CITYKEY: "" }; }

  function minutesOf(text) {
    if (!text) return null;
    if (text.indexOf("小于") >= 0 && text.indexOf("分钟") >= 0) return 0;
    var m = String(text).match(/(\d+)\s*分钟/);
    return m ? parseInt(m[1], 10) : null;
  }

  function metersOf(text) {
    var m = String(text || "").match(/([\d.]+)\s*公里/);
    if (m) return Math.round(parseFloat(m[1]) * 1000);
    m = String(text || "").match(/(\d+)\s*米/);
    return m ? parseInt(m[1], 10) : null;
  }

  function numOf(text) {
    var m = String(text || "").match(/(\d+)/);
    return m ? parseInt(m[1], 10) : null;
  }

  function statusOf(node, dist) {
    var t = (node || "") + (dist || "");
    if (t.indexOf("非运营") >= 0 || t.indexOf("收班") >= 0) return "closed";
    if (t.indexOf("等待发车") >= 0 || t.indexOf("待发") >= 0) return "waiting";
    if (t.indexOf("已到站") >= 0) return "here";
    if (t.indexOf("已过") >= 0) return "passed";
    if (minutesOf(dist) !== null) return "coming";
    return "unknown";
  }

  var BRACKET_NOTE = /[（(]([^)）]{0,16})[)）]/g;
  var KEEP_BRACKET = /^[东南西北中前后]{1,2}$/;

  /* 「三桥下首末站(不用于上下客)」→「三桥下」，「新城站(东)」保留方位 */
  function shortName(s) {
    s = s || "";
    return s.replace(BRACKET_NOTE, function (m, p1) {
      return KEEP_BRACKET.test(String(p1).replace(/\s/g, "")) ? m : "";
    }).replace(/(首末站|公交枢纽|公交站)$/, "").replace(/^\s+|\s+$/g, "");
  }

  function fetchStationLines(station) {
    var key = "st:" + station;
    var hit = rtCache[key];
    if (hit && Date.now() - hit[0] < CACHE_RT) return Promise.resolve(hit[1]);

    /* MYLAT/MYLNG 必须是空串 —— 传了坐标上游会直接返回 0 条，
       这是实测出来的坑，别"优化"成带坐标。 */
    return apiPost(mix(base(), {
      CMD: "115", STATIONNAME: station, MYLAT: "", MYLNG: "", ALL: "1"
    })).then(function (raw) {
      if (String(raw.status) !== "1") throw new Error(raw.msg || "接口返回异常");
      var seen = {}, lines = [];
      var arr = raw.data || [];
      for (var i = 0; i < arr.length; i++) {
        var x = arr[i];
        var name = x.lineName || "";
        var d = String(x.upperOrDown || "");
        var k = name + "|" + d;
        if (!name || seen[k]) continue;
        seen[k] = 1;
        var node = x.neartext || "";
        var dist = x.neardis || "";
        lines.push({
          line: name, dir: d,
          to: x.to || "", toShort: shortName(x.to),
          node: node, dist: dist,
          minutes: minutesOf(dist), meters: metersOf(dist),
          stations: numOf(node), status: statusOf(node, dist),
          order: x.stationOrder || 0
        });
      }
      rtCache[key] = [Date.now(), lines];
      return lines;
    });
  }

  function fetchStops(line, dir) {
    var ck = line + "|" + dir;
    var hit = stopsCache[ck];
    if (hit && Date.now() - hit[0] < CACHE_STOPS) return Promise.resolve(hit[1]);

    return apiPost(mix(base(), { CMD: "103", LINENAME: line, DIRECTION: dir }))
      .then(function (raw) {
        var stops = [], arr = raw.data || [];
        for (var i = 0; i < arr.length; i++) {
          var s = arr[i];
          stops.push({
            i: i + 1,
            name: s.stationName || "",
            lat: s.station_lat || 0,
            lon: s.station_lon || 0
          });
        }
        var detail = {
          line: line, dir: dir,
          begin: raw.beginTime || "", end: raw.endTime || "",
          from: stops.length ? stops[0].name : "",
          to: stops.length ? stops[stops.length - 1].name : "",
          stops: stops
        };
        stopsCache[ck] = [Date.now(), detail];
        return detail;
      });
  }

  function fetchBuses(line, dir) {
    return apiPost(mix(base(), {
      CMD: "104", LINENAME: line, DIRECTION: dir, STATIONORDER: "1"
    })).then(function (raw) {
      var buses = [], arr = raw.list || [];
      for (var i = 0; i < arr.length; i++) {
        var b = arr[i];
        var idx = parseInt(b.index, 10);
        if (isNaN(idx)) continue;
        buses.push({
          index: idx,
          plate: b.busNumber || "",
          toNext: Math.round(parseFloat(b.busToStationNiheDistance || 0) || 0)
        });
      }
      buses.sort(function (x, y) { return x.index - y.index; });
      return {
        hasReal: raw.hasReal === 1 || raw.hasReal === "1",
        buses: buses
      };
    });
  }

  function fetchPlatforms(station) {
    return apiPost(mix(base(), {
      CMD: "209", STATIONNAME: station, MYLAT: "", MYLNG: "", LAT: "", LNG: ""
    })).then(function (raw) {
      var info = raw.info;
      if (!info && raw.data && raw.data.info) info = raw.data.info;
      var out = [];
      for (var i = 0; i < (info || []).length; i++) {
        var x = info[i];
        var lat = parseFloat(x.lat), lon = parseFloat(x.lon);
        if (!isNaN(lat) && !isNaN(lon)) out.push({ lat: lat, lon: lon });
      }
      return out;
    });
  }

  /* ---------------------------------------------------------- 站库 */

  function stationDb() {
    if (stationCache) return Promise.resolve(stationCache);
    if (stationCacheP) return stationCacheP;
    stationCacheP = fetch("stations.json", { cache: "force-cache" })
      .then(function (r) { return r.json(); })
      .then(function (j) { stationCache = j || {}; return stationCache; })
      .catch(function () { stationCache = {}; return stationCache; });
    return stationCacheP;
  }

  function distM(lat1, lon1, lat2, lon2) {
    var R = 6371000.0;
    var p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
    var dp = p2 - p1;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dp / 2) * Math.sin(dp / 2) +
            Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function buildNearby(db, lat, lon, radius, limit, faves) {
    var out = {}, name, pts, i, d, best;
    faves = faves || [];

    for (i = 0; i < faves.length; i++) {
      name = faves[i];
      pts = db[name];
      if (!pts || !pts.length) continue;      // 库里没有就跳过，不编坐标
      best = Infinity;
      for (var j = 0; j < pts.length; j++) {
        d = distM(lat, lon, pts[j][0], pts[j][1]);
        if (d < best) best = d;
      }
      out[name] = { name: name, dist: Math.round(best), fave: true };
    }

    for (name in db) {
      if (!db.hasOwnProperty(name) || out[name]) continue;
      pts = db[name];
      if (!pts || !pts.length) continue;
      best = Infinity;
      for (var k = 0; k < pts.length; k++) {
        d = distM(lat, lon, pts[k][0], pts[k][1]);
        if (d < best) best = d;
      }
      if (best <= radius) out[name] = { name: name, dist: Math.round(best), fave: false };
    }

    var items = [];
    for (var n in out) { if (out.hasOwnProperty(n)) items.push(out[n]); }
    items.sort(function (a, b) {
      var fa = a.fave ? 0 : 1, fb = b.fave ? 0 : 1;
      if (fa !== fb) return fa - fb;
      if (a.dist !== b.dist) return a.dist - b.dist;
      return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
    });

    return {
      ok: true, stations: items.slice(0, limit), total: items.length,
      radius: radius, known: Object.keys(db).length
    };
  }

  /* ---------------------------------------------------------- 业务层 */

  /* 越小越靠前：0 完全命中，1 开头命中，2 只是包含。
     去掉结尾的「路」是为了线路号（搜 36 时「36路」要算完全命中）；
     站名不能这么比，走 rankStation。 */
  function rank(name, kw) {
    var n = (name || "").replace(/^\s+|\s+$/g, "");
    var k = (kw || "").replace(/^\s+|\s+$/g, "");
    var b = n.charAt(n.length - 1) === "路" ? n.slice(0, -1) : n;
    if (n === k || b === k) return 0;
    if (n.indexOf(k) === 0 || b.indexOf(k) === 0) return 1;
    return 2;
  }

  function rankStation(name, kw) {
    var n = (name || "").replace(/^\s+|\s+$/g, "");
    var k = (kw || "").replace(/^\s+|\s+$/g, "");
    if (n === k) return 0;
    if (n.indexOf(k) === 0) return 1;
    return 2;
  }

  function localStations(db, kw, lat, lon) {
    var k = (kw || "").replace(/^\s+|\s+$/g, "");
    if (!k) return [];
    var hasPos = (lat !== null && lat !== undefined && lon !== null && lon !== undefined);
    var out = [], name, pts, sn, d, best;
    for (name in db) {
      if (!db.hasOwnProperty(name)) continue;
      sn = shortName(name);
      if (name.indexOf(k) < 0 && sn.indexOf(k) < 0) continue;
      d = null;
      pts = db[name];
      if (hasPos && pts && pts.length) {
        best = Infinity;
        for (var i = 0; i < pts.length; i++) {
          var v = distM(lat, lon, pts[i][0], pts[i][1]);
          if (v < best) best = v;
        }
        d = Math.round(best);
      }
      out.push({ name: name, short: sn, dist: d });
    }
    return out;
  }

  /* 距离 + 命中档次 × 1500 米 —— 纯按命中排会把 54 公里外的
     「人民医院（洞头）」顶到最前；纯按距离排又会让「石坦路」压过「石坦」 */
  var BONUS = 1500;

  function stationSort(hits, kw, hasPos) {
    hits.sort(function (a, b) {
      var ra = rankStation(a.name, kw), rb = rankStation(b.name, kw);
      var da = (hasPos && a.dist !== null && a.dist !== undefined) ? a.dist : null;
      var db2 = (hasPos && b.dist !== null && b.dist !== undefined) ? b.dist : null;
      if (da === null || db2 === null) {
        if (ra !== rb) return ra - rb;
        if (a.name.length !== b.name.length) return a.name.length - b.name.length;
        return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
      }
      var sa = da + ra * BONUS, sb = db2 + rb * BONUS;
      if (sa !== sb) return sa - sb;
      return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
    });
    return hits;
  }

  function pace(main) {
    if (!main) return null;
    var m = main.minutes, n = main.stations;
    if (m === null || m === undefined || !n) return null;
    var v = m / n;
    if (!isFinite(v)) return null;
    return Math.min(6.0, Math.max(1.0, v));
  }

  /* 车到第 i 站还要几站、约几分钟。index 是「正在驶向的站序」。 */
  function etaFor(i, detail, main, p) {
    var focus = detail.focus === undefined ? null : detail.focus;
    var buses = detail.buses || [];
    var live = [];
    for (var b = 0; b < buses.length; b++) {
      if (buses[b].index <= i) live.push(buses[b]);
    }
    if (!live.length) return { eta: null, left: null, passed: true };

    var bus = live[0];
    for (var j = 1; j < live.length; j++) {
      if (live[j].index > bus.index) bus = live[j];
    }
    var left = i - bus.index + 1;

    if (focus !== null && i === focus && main) {
      if (main.stations !== null && main.stations !== undefined) left = main.stations;
      if (main.minutes !== null && main.minutes !== undefined) {
        return { eta: main.minutes, left: left, passed: false };
      }
    }
    if (p === null) return { eta: null, left: left, passed: false };
    return { eta: Math.round(p * left), left: left, passed: false };
  }

  function windowStops(detail, main) {
    var stops = detail.stops || [];
    var focus = detail.focus === undefined ? null : detail.focus;
    var busAt = {}, i, b;
    var buses = detail.buses || [];
    for (i = 0; i < buses.length; i++) {
      b = buses[i];
      if (focus === null || b.index < focus) {
        if (!busAt[b.index]) busAt[b.index] = b;
      }
    }
    var p = pace(main);
    var rows = [];
    for (i = 0; i < stops.length; i++) {
      var s = stops[i];
      var e = etaFor(s.i, detail, main, p);
      rows.push({
        i: s.i, name: s.name,
        mine: focus !== null && s.i === focus,
        bus: !!busAt[s.i],
        eta: e.eta, left: e.left, passed: e.passed
      });
    }
    var busHere = null;
    var keys = [];
    for (var k in busAt) { if (busAt.hasOwnProperty(k)) keys.push(parseInt(k, 10)); }
    if (keys.length) {
      var nearest = Math.max.apply(null, keys);
      for (i = 0; i < stops.length; i++) {
        if (stops[i].i === nearest) { busHere = stops[i].name; break; }
      }
    }
    return {
      rows: rows, busHere: busHere, total: stops.length, focus: focus,
      pace: p === null ? null : Math.round(p * 10) / 10
    };
  }

  function buildLine(line, dir, focus) {
    return Promise.all([fetchStops(line, dir), fetchBuses(line, dir).catch(function () {
      return { hasReal: false, buses: [] };
    })]).then(function (res) {
      var stops = res[0], rt = res[1];
      var focusIdx = null;
      for (var i = 0; i < stops.stops.length; i++) {
        if (stops.stops[i].name === focus) { focusIdx = stops.stops[i].i; break; }
      }
      return {
        ok: true, line: line, dir: dir,
        from: stops.from, to: stops.to,
        fromShort: shortName(stops.from), toShort: shortName(stops.to),
        begin: stops.begin, end: stops.end,
        stops: stops.stops, buses: rt.buses,
        hasReal: rt.hasReal, focus: focusIdx,
        updated: hhmm()
      };
    });
  }

  function buildBoard(line, dir, station) {
    station = (station || "").replace(/^\s+|\s+$/g, "") || HOME_STATION;

    return fetchStationLines(station).catch(function () { return []; })
      .then(function (entries) {
        var mine = [], other = null, main = null, i;
        for (i = 0; i < entries.length; i++) {
          if (entries[i].line === line) mine.push(entries[i]);
        }
        for (i = 0; i < mine.length; i++) {
          if (mine[i].dir === dir) main = mine[i];
          else other = mine[i];
        }
        return buildLine(line, dir, station).then(function (det) {
          var win = windowStops(det, main);
          var passes = !!det.focus;

          function finish(otherCard) {
            var card;
            if (main) {
              card = main;
            } else {
              card = {
                line: line, dir: dir, toShort: det.toShort,
                status: "noroute", minutes: null, stations: null,
                node: null, dist: null, label: ""
              };
            }
            return {
              ok: true, station: station, line: line, dir: dir,
              main: card, other: otherCard, win: win,
              passes: passes, total: det.stops.length,
              hasReal: det.hasReal, updated: hhmm()
            };
          }

          if (other) return finish(other);
          // 反方向在这个站没有记录（环线之类），单独查一次拿终点名
          var d2 = String(dir) === "1" ? "2" : "1";
          return buildLine(line, d2, station).then(function (det2) {
            return finish({
              line: line, dir: d2, toShort: det2.toShort,
              status: "unknown", minutes: null, stations: null,
              node: null, dist: null, label: ""
            });
          }).catch(function () { return finish(null); });
        });
      });
  }

  function buildStation(station) {
    return fetchStationLines(station).then(function (lines) {
      var rk = { coming: 0, here: 0, waiting: 1, unknown: 2, passed: 3, closed: 4 };
      lines.sort(function (a, b) {
        var ra = rk[a.status] === undefined ? 5 : rk[a.status];
        var rb = rk[b.status] === undefined ? 5 : rk[b.status];
        if (ra !== rb) return ra - rb;
        var ma = a.minutes === null ? 999 : a.minutes;
        var mb = b.minutes === null ? 999 : b.minutes;
        return ma - mb;
      });
      return { ok: true, station: station, lines: lines, updated: hhmm() };
    });
  }

  function buildHome(station) {
    var st = (station || "").replace(/^\s+|\s+$/g, "") || HOME_STATION;
    return buildStation(st).then(function (data) {
      data.isHome = true;
      return data;
    });
  }

  function buildDirs(line, station) {
    station = (station || "").replace(/^\s+|\s+$/g, "");
    var liveP = station
      ? fetchStationLines(station).catch(function () { return []; })
      : Promise.resolve([]);

    return liveP.then(function (entries) {
      var live = {}, i;
      for (i = 0; i < entries.length; i++) {
        if (entries[i].line === line) live[entries[i].dir] = entries[i];
      }
      return Promise.all(["1", "2"].map(function (d) {
        return buildLine(line, d, station).catch(function () { return null; });
      })).then(function (dets) {
        var out = [];
        for (var j = 0; j < dets.length; j++) {
          var det = dets[j];
          if (!det || !det.stops.length) continue;
          var item = {
            dir: det.dir, toShort: det.toShort, fromShort: det.fromShort,
            begin: det.begin, end: det.end,
            stopCount: det.stops.length,
            busCount: det.buses.length,
            hasReal: det.hasReal
          };
          var v = live[det.dir];
          if (v) {
            item.minutes = v.minutes;
            item.stations = v.stations;
            item.status = v.status;
          }
          out.push(item);
        }
        return { ok: true, line: line, station: station, dirs: out };
      });
    });
  }

  function buildEta(line, dir, station) {
    station = (station || "").replace(/^\s+|\s+$/g, "");
    if (!station) return Promise.resolve({ ok: false, error: "缺少站名" });
    return fetchStationLines(station).then(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        var v = entries[i];
        if (v.line === line && v.dir === dir) {
          return {
            ok: true, station: station, line: line, dir: dir,
            status: v.status, minutes: v.minutes, stations: v.stations,
            toShort: v.toShort, node: v.node, dist: v.dist,
            updated: hhmm()
          };
        }
      }
      return { ok: false, error: "这站没有这趟车" };
    }).catch(function () {
      return { ok: false, error: "这一站暂时查不到" };
    });
  }

  function buildSearch(kw, lat, lon) {
    var hasPos = (lat !== null && lat !== undefined && lon !== null && lon !== undefined);

    return Promise.all([
      apiPost(mix(base(), { CMD: "114", KEYWORD: kw })).catch(function () { return {}; }),
      stationDb()
    ]).then(function (res) {
      var raw = res[0], db = res[1];
      var lines = [], seen = {}, skipped = 0;
      var arr = raw.buslines || [];
      for (var i = 0; i < arr.length; i++) {
        var b = arr[i];
        var name = (b.lineName || "").replace(/^\s+|\s+$/g, "");
        if (!name || seen[name]) continue;
        seen[name] = 1;
        var bean = b.routeBean || {};
        if (String(bean.hasReal) !== "1") { skipped++; continue; }
        lines.push({
          line: name, from: shortName(b.from), to: shortName(b.to), hasReal: true
        });
      }
      lines.sort(function (a, b2) {
        var ra = rank(a.line, kw), rb = rank(b2.line, kw);
        if (ra !== rb) return ra - rb;
        if (a.line.length !== b2.line.length) return a.line.length - b2.line.length;
        return a.line < b2.line ? -1 : (a.line > b2.line ? 1 : 0);
      });

      var stations = stationSort(localStations(db, kw, lat, lon), kw, hasPos);

      var tail = stations.length ? Promise.resolve(stations) :
        apiPost(mix(base(), { CMD: "110", KEYWORD: kw })).then(function (r2) {
          var out = [], seen2 = {};
          var sa = r2.busstations || [];
          for (var j = 0; j < sa.length; j++) {
            var nm = (sa[j].stationName || "").replace(/^\s+|\s+$/g, "");
            if (!nm || seen2[nm]) continue;
            seen2[nm] = 1;
            var d = null;
            if (hasPos && db[nm] && db[nm].length) {
              var best = Infinity;
              for (var k = 0; k < db[nm].length; k++) {
                var v = distM(lat, lon, db[nm][k][0], db[nm][k][1]);
                if (v < best) best = v;
              }
              d = Math.round(best);
            }
            out.push({ name: nm, short: shortName(nm), dist: d });
          }
          out.sort(function (a, b3) {
            var ra = rankStation(a.name, kw), rb = rankStation(b3.name, kw);
            if (ra !== rb) return ra - rb;
            return a.name.length - b3.name.length;
          });
          return out;
        }).catch(function () { return []; });

      return tail.then(function (stList) {
        // 线路号精确命中时把两个方向直接摊开，省一次点击
        var exact = [];
        for (var q = 0; q < lines.length; q++) {
          if (rank(lines[q].line, kw) === 0 && exact.length < 3) exact.push(lines[q]);
        }
        var dirP = exact.map(function (v) {
          return Promise.all(["1", "2"].map(function (d) {
            return fetchStops(v.line, d).catch(function () { return null; });
          })).then(function (sts) {
            var dirs = [];
            for (var m = 0; m < sts.length; m++) {
              if (!sts[m] || !sts[m].stops.length) continue;
              dirs.push({
                dir: sts[m].dir,
                toShort: shortName(sts[m].to),
                stopCount: sts[m].stops.length
              });
            }
            v.dirs = dirs;
          });
        });

        return Promise.all(dirP).then(function () {
          return {
            ok: true, kw: kw,
            lines: lines.slice(0, 10),
            stations: stList.slice(0, 8),
            linesTotal: lines.length, stationsTotal: stList.length,
            skipped: skipped
          };
        });
      });
    });
  }

  /* ---------------------------------------------------------- 路由 */

  function parseQ(url) {
    var q = {}, i = url.indexOf("?");
    if (i < 0) return q;
    var s = url.slice(i + 1).split("&");
    for (var j = 0; j < s.length; j++) {
      if (!s[j]) continue;
      var a = s[j].split("=");
      q[decodeURIComponent(a[0])] = decodeURIComponent(a.slice(1).join("=") || "");
    }
    return q;
  }

  function numOrNull(v) {
    if (v === undefined || v === null || v === "") return null;
    var n = parseFloat(v);
    return isNaN(n) ? null : n;
  }

  window.localApi = function (url) {
    var path = url.split("?")[0];
    var q = parseQ(url);
    var p;

    try {
      if (path === "/api/home") {
        p = buildHome(q.station);
      } else if (path === "/api/station") {
        p = q.name ? buildStation(q.name)
                   : Promise.resolve({ ok: false, error: "缺少站名" });
      } else if (path === "/api/board") {
        p = buildBoard(q.line, q.dir || "1", q.station);
      } else if (path === "/api/line") {
        p = buildLine(q.name, q.dir || "1", q.focus || "");
      } else if (path === "/api/dirs") {
        p = buildDirs(q.line, q.from || "");
      } else if (path === "/api/eta") {
        p = buildEta(q.line, q.dir || "1", q.station);
      } else if (path === "/api/search") {
        p = q.kw ? buildSearch(q.kw, numOrNull(q.lat), numOrNull(q.lon))
                 : Promise.resolve({ ok: false, error: "缺少关键词" });
      } else if (path === "/api/nearby") {
        var lat = numOrNull(q.lat), lon = numOrNull(q.lon);
        if (lat === null || lon === null) {
          p = Promise.resolve({ ok: false, error: "没有位置" });
        } else {
          var rad = parseInt(q.r || "800", 10);
          if (isNaN(rad)) rad = 800;
          rad = Math.max(100, Math.min(3000, rad));
          var faves = [];
          var fs = (q.faves || "").split(",");
          for (var i = 0; i < fs.length; i++) {
            var n = fs[i].replace(/^\s+|\s+$/g, "");
            if (n && faves.indexOf(n) < 0) faves.push(n);
          }
          var lim = rad >= 2000 ? 60 : 40;
          p = stationDb().then(function (db) {
            return buildNearby(db, lat, lon, rad, lim, faves);
          });
        }
      } else if (path === "/api/stloc") {
        p = q.name ? fetchPlatforms(q.name).then(function (pts) {
          return { ok: pts.length > 0, name: q.name, points: pts.length };
        }).catch(function (e) {
          return { ok: false, error: String(e && e.message || e) };
        }) : Promise.resolve({ ok: false, error: "没给站名" });
      } else if (path === "/api/platforms") {
        p = fetchPlatforms(q.station).then(function (pts) {
          return { ok: true, station: q.station, platforms: pts };
        });
      } else {
        p = Promise.resolve({ ok: false, error: "没有这个接口" });
      }
    } catch (e) {
      p = Promise.resolve({ ok: false, error: String(e && e.message || e) });
    }

    return p.catch(function (e) {
      return { ok: false, error: String(e && e.message || e || "查不到") };
    });
  };
})();
