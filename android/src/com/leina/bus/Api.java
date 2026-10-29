package com.leina.bus;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

/**
 * 只问一件事：这条线在这个站还有几站到。
 * 数据来自本地 Python 服务（server.py）的 /api/board。
 */
public class Api {

    public static class Board {
        public boolean ok;
        public String error;
        public String status;    // coming / here / waiting / closed / passed / unknown
        public Integer stations; // 还有几站；null 表示不知道
        public Integer minutes;
        public String toShort;   // 往哪儿开
        public String updated;
    }

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

    private static String readAll(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        in.close();
        return new String(out.toByteArray(), "UTF-8");
    }
}
