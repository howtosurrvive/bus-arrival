package com.leina.bus;

import android.content.Context;
import android.content.SharedPreferences;

/** 全部配置就四个字段：服务地址、线路、方向、上车站、还剩几站时提醒。 */
public class Prefs {

    private static final String FILE = "bus";

    public static final String KEY_SERVER = "server";
    public static final String KEY_LINE = "line";
    public static final String KEY_DIR = "dir";
    public static final String KEY_STATION = "station";
    public static final String KEY_AT = "at";

    /** 构建时写入的默认地址。默认空 —— 空的意思是「用装在手机里的那一套」，
     *  不连电脑。想连电脑的人在设置里填地址即可。 */
    public static final String DEFAULT_SERVER = "@DEFAULT_SERVER@";

    /** 空 = 自带数据（自己上网查）；非空 = 连电脑上的 server.py */
    public boolean local() { return server().isEmpty(); }

    private final SharedPreferences sp;

    public Prefs(Context c) {
        sp = c.getApplicationContext().getSharedPreferences(FILE, Context.MODE_PRIVATE);
    }

    public String server() {
        String v = sp.getString(KEY_SERVER, "");
        if (v == null || v.trim().isEmpty()) v = DEFAULT_SERVER;
        return v == null ? "" : v.trim().replaceAll("/+$", "");
    }

    public void server(String v) {
        sp.edit().putString(KEY_SERVER, v == null ? "" : v.trim()).apply();
    }

    public String line()    { return sp.getString(KEY_LINE, ""); }
    public String dir()     { return sp.getString(KEY_DIR, "1"); }
    public String station() { return sp.getString(KEY_STATION, ""); }
    public int    at()      { return sp.getInt(KEY_AT, 0); }

    public void watch(String line, String dir, String station, int at) {
        sp.edit()
          .putString(KEY_LINE, line == null ? "" : line)
          .putString(KEY_DIR, dir == null ? "1" : dir)
          .putString(KEY_STATION, station == null ? "" : station)
          .putInt(KEY_AT, at)
          .apply();
    }

    public void clearWatch() {
        sp.edit().putString(KEY_LINE, "").putInt(KEY_AT, 0).apply();
    }

    /** 提醒开着、并且知道看哪条线，才值得把服务挂着。 */
    public boolean watchOn() {
        return at() > 0 && !line().isEmpty();
    }
}
