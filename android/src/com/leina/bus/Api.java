package com.leina.bus;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 只问一件事：这条线在这个站还有几站到。
 *
 * 两个来源：
 *   board()      连电脑上的 server.py（要填地址，电脑得开着）
 *   boardLocal() 自己问上游 —— App 装在手机里就能用，不依赖任何服务器
 *
 * 只在 App 里用 get() 发请求是有原因的：上游有防盗链，只认
 * Origin: https://h5.mygolbs.com，这个头在浏览器/WebView 的 JS 里改不了。
 */
public class Api {

    private static final String UPSTREAM = "https://h5.mygolbs.com/ApiData.do";
    private static final String CITY = "温州市";

    public static class Board {
        public boolean ok;
        public String error;
        public String status;    // coming / here / waiting / closed / passed / unknown
        public Integer stations; // 还有几站；null 表示不知道
        public Integer minutes;
        public String toShort;   // 往哪儿开
        public String updated;
    }

    /** 连电脑上的 server.py。 */
    public static Board board(String server, String line, String dir, String station)
            throws Exception {
        String q = server + "/api/board?line=" + URLEncoder.encode(line, "UTF-8")
                 + "&dir=" + URLEncoder.encode(dir == null ? "1" : dir, "UTF-8")
                 + "&station=" + URLEncoder.encode(station == null ? "" : station, "UTF-8");

        HttpURLConnection c = (HttpURLConnection) new URL(q).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(10000);
        c.setRequestProperty("Cache-Control", "no-store");
        c.setRequestProperty("User-Agent", "BusApp/1.0");

        Board b = new Board();
        try {
            int code = c.getResponseCode();
            if (code != 200) throw new Exception("服务返回 " + code);
            String body = readAll(c.getInputStream());

            JSONObject j = new JSONObject(body);
            b.ok = j.optBoolean("ok", false);
            if (!b.ok) {
                b.error = j.optString("error", "查不到");
                return b;
            }
            JSONObject main = j.optJSONObject("main");
            if (main == null) {
                b.error = "没有这趟车";
                return b;
            }
            b.status = main.optString("status", "unknown");
            b.toShort = main.optString("toShort", "");
            if (!main.isNull("minutes")) b.minutes = main.optInt("minutes");
            if (!main.isNull("stations")) b.stations = main.optInt("stations");
            b.updated = j.optString("updated", "");
            return b;
        } finally {
            c.disconnect();
        }
    }

    /**
     * 自己问上游：CMD 115 = 这一站所有经过线路的实时到站。
     * 响铃只需要「还有几站」和「往哪开」，不用算窗口、不用算逐站 ETA ——
     * 所以这里比页面上那套轻得多。
     */
    public static Board boardLocal(String line, String dir, String station) throws Exception {
        String q = "CITYNAME=" + URLEncoder.encode(CITY, "UTF-8")
                 + "&CITYKEY=&CMD=115"
                 + "&STATIONNAME=" + URLEncoder.encode(station == null ? "" : station, "UTF-8")
                 + "&MYLAT=&MYLNG=&ALL=1";

        Board b = new Board();
        try {
            JSONObject j = new JSONObject(get(UPSTREAM + "?" + q));
            JSONArray arr = j.optJSONArray("data");
            if (arr == null) {
                b.error = "没有这趟车";
                return b;
            }
            String want = dir == null ? "1" : dir;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject x = arr.optJSONObject(i);
                if (x == null) continue;
                if (!line.equals(x.optString("lineName"))) continue;
                if (!want.equals(x.optString("upperOrDown"))) continue;

                String node = x.optString("neartext");
                String dist = x.optString("neardis");
                b.ok = true;
                b.status = statusOf(node, dist);
                b.toShort = shortName(x.optString("to"));
                b.stations = numOf(node);
                b.minutes = minutesOf(dist);
                return b;
            }
            b.error = "这站没有这趟车";
            return b;
        } catch (Exception e) {
            b.error = "查不到";
            return b;
        }
    }

    /* ---------------------------------------------------------- 小工具 */

    private static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod("GET");
        c.setConnectTimeout(8000);
        c.setReadTimeout(12000);
        // 不带这个头，上游回的是密文，解不出 JSON —— 实测过
        c.setRequestProperty("Origin", "https://h5.mygolbs.com");
        c.setRequestProperty("User-Agent",
                "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
                + "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36");
        try {
            if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
            return readAll(c.getInputStream());
        } finally {
            c.disconnect();
        }
    }

    /** 「9.3公里/28分钟」里的分钟数。 */
    private static Integer minutesOf(String d) {
        if (d == null || d.isEmpty()) return null;
        if (d.contains("小于") && d.contains("分钟")) return 0;
        Matcher m = Pattern.compile("(\\d+)\\s*分钟").matcher(d);
        return m.find() ? Integer.valueOf(m.group(1)) : null;
    }

    /** 「17站」里的站数。 */
    private static Integer numOf(String s) {
        if (s == null) return null;
        Matcher m = Pattern.compile("(\\d+)").matcher(s);
        return m.find() ? Integer.valueOf(m.group(1)) : null;
    }

    private static String statusOf(String node, String dist) {
        String t = (node == null ? "" : node) + (dist == null ? "" : dist);
        if (t.contains("非运营") || t.contains("收班")) return "closed";
        if (t.contains("等待发车") || t.contains("待发")) return "waiting";
        if (t.contains("已到站")) return "here";
        if (t.contains("已过")) return "passed";
        if (minutesOf(dist) != null) return "coming";
        return "unknown";
    }

    /** 「浙南科技城首末站」→「浙南科技城」。响铃那句话说完整了反而念得慢。 */
    private static String shortName(String s) {
        if (s == null) return "";
        String v = s.replaceAll("[（(][^)）]{0,16}[)）]", "")
                   .replaceAll("(首末站|公交枢纽|公交站)$", "");
        return v.trim();
    }

    private static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        in.close();
        return new String(out.toByteArray(), "UTF-8");
    }
}
