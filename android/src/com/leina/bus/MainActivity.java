package com.leina.bus;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;

/**
 * 一个很薄的壳：里面就是那套网页，外面只多了两件事 ——
 * 记住服务器地址，和把「看着哪条线、响几站」交给后台服务。
 */
public class MainActivity extends Activity {

    private static final String BG = "#FAFAF7";
    private static final String INK = "#1A1C1E";
    private static final String SUB = "#5C6166";
    private static final String BLUE = "#0E3A63";
    private static final String ORANGE = "#DA6B1C";

    /* 页面整个住在 APK 里。bus.local 是假的域名 —— 不会真的解析，
       所有请求都在 shouldInterceptRequest 里被接住。用 https 是为了让
       WebView 当成安全上下文。 */
    private static final String LOCAL_HOST = "bus.local";
    private static final String LOCAL_HOME = "https://" + LOCAL_HOST + "/index.html";
    private static final String UPSTREAM = "https://h5.mygolbs.com/ApiData.do";

    private Prefs prefs;
    private FrameLayout root;
    private WebView web;
    private boolean triedAssetFallback = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = new Prefs(this);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor(BG));
        setContentView(root);

        // 默认就用装在手机里的那一套，不需要先填服务器地址。
        // 想连电脑的人可以在设置里填（填了就会走电脑，老用户升级后也认）。
        openWeb();

        // 手机重启过、或者 App 被系统清掉过：打开时把盯站服务接回来
        if (prefs.watchOn()) BusService.start(this);
    }

    /* ------------------------------------------------------------ 网页 */

    private void openWeb() {
        if (web == null) {
            web = new WebView(this);
            WebSettings s = web.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setDatabaseEnabled(true);
            s.setCacheMode(WebSettings.LOAD_NO_CACHE);
            s.setUseWideViewPort(true);
            s.setLoadWithOverviewMode(false);
            s.setSupportZoom(false);
            s.setTextZoom(100);
            if (Build.VERSION.SDK_INT >= 21) {
                s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
            }
            // 兜底路径会用 file:// 直接打开 assets 里的页面，那时要读同目录的
            // stations.json / app.js —— WebView 默认禁止 file:// 之间互相取文件
            s.setAllowFileAccessFromFileURLs(true);
            s.setAllowUniversalAccessFromFileURLs(true);
            web.setBackgroundColor(Color.parseColor(BG));
            web.setOverScrollMode(View.OVER_SCROLL_NEVER);
            web.addJavascriptInterface(new Bridge(), "AndroidBridge");
            web.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView v, String url) {
                    return false;   // 就一个站内页面，全部自己加载
                }

                /* bus.local 上的东西一律由这里供货：
                   ① /api/data —— 替网页去问上游。上游有防盗链，只认
                      Origin: https://h5.mygolbs.com，浏览器里 JS 改不了这个头
                      （禁止修改的请求头），所以只能原生发；
                   ② 其他 —— 从 assets/web 里读静态文件。
                   这样就不需要电脑、也不需要任何服务器。 */
                @Override
                public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                    Uri u = req.getUrl();
                    if (u == null || !LOCAL_HOST.equals(u.getHost())) return null;

                    String path = u.getPath();
                    if (path != null && path.startsWith("/api/data")) {
                        Map<String, String> h = new HashMap<String, String>();
                        h.put("Access-Control-Allow-Origin", "*");
                        h.put("Cache-Control", "no-store");
                        WebResourceResponse r = new WebResourceResponse(
                                "application/json", "utf-8",
                                new ByteArrayInputStream(fetchUpstream(u.getEncodedQuery())));
                        r.setResponseHeaders(h);
                        return r;
                    }
                    return serveAsset(path);
                }

                @Override
                public void onReceivedError(WebView v, int code, String desc, String url) {
                    // 只关心主文档失败；子资源失败不打断
                    if (url != null && url.contains("/api/")) return;
                    showOffline();
                }

                // Android 6 以后只会回调这个带请求信息的新版本，旧的 4 参版本不再触发
                @Override
                public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                    if (req == null || !req.isForMainFrame()) return;
                    // bus.local 是个假域名，正常都被 shouldInterceptRequest 接住。
                    // 万一某台老机器的 WebView 没接住，直接去 assets 里打开 ——
                    // 页面会以 file:// 跑，接口仍走绝对地址让原生代发。
                    if (!triedAssetFallback && req.getUrl() != null
                            && LOCAL_HOST.equals(req.getUrl().getHost())) {
                        triedAssetFallback = true;
                        v.loadUrl("file:///android_asset/web/index.html");
                        return;
                    }
                    showOffline();
                }
            });
        }
        root.removeAllViews();
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        web.loadUrl(prefs.local() ? LOCAL_HOME : prefs.server() + "/");

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                   != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 7);
        }
        // 附近站点要用位置。首次启动会弹一次系统权限框，拒绝也不影响手动选站。
        askLocPerm();
    }

    /* ------------------------------------------------------- 内置那份数据 */

    /** 替网页去问上游。必须在这里发 —— 上游只认 Origin: h5.mygolbs.com，
     *  而这个头在浏览器里是禁止修改的，只有原生能设。 */
    private byte[] fetchUpstream(String query) {
        HttpURLConnection c = null;
        try {
            String url = UPSTREAM + "?" + (query == null ? "" : query);
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("GET");
            c.setConnectTimeout(8000);
            c.setReadTimeout(12000);
            c.setRequestProperty("Origin", "https://h5.mygolbs.com");
            c.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36");
            if (c.getResponseCode() != 200) {
                return ("{\"status\":\"-1\",\"msg\":\"http" + c.getResponseCode() + "\"}")
                        .getBytes("UTF-8");
            }
            InputStream in = c.getInputStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            in.close();
            return out.toByteArray();
        } catch (Exception e) {
            return "{\"status\":\"-1\",\"msg\":\"net\"}".getBytes();
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** 从 assets/web 里读页面文件。 */
    private WebResourceResponse serveAsset(String path) {
        String rel = (path == null || path.length() <= 1) ? "index.html" : path.substring(1);
        String mime = "application/octet-stream";
        if (rel.endsWith(".html")) mime = "text/html";
        else if (rel.endsWith(".js")) mime = "application/javascript";
        else if (rel.endsWith(".css")) mime = "text/css";
        else if (rel.endsWith(".json")) mime = "application/json";
        else if (rel.endsWith(".png")) mime = "image/png";
        else if (rel.endsWith(".svg")) mime = "image/svg+xml";
        try {
            InputStream in = getAssets().open("web/" + rel);
            WebResourceResponse r = new WebResourceResponse(mime, "utf-8", in);
            Map<String, String> h = new HashMap<String, String>();
            h.put("Cache-Control", "no-cache");
            r.setResponseHeaders(h);
            return r;
        } catch (Exception e) {
            return new WebResourceResponse("text/plain", "utf-8",
                    new ByteArrayInputStream("not found".getBytes()));
        }
    }

    /** 连不上电脑上的服务时，给一个能看懂、能自己救回来的页面。 */
    private void showOffline() {
        root.removeAllViews();
        LinearLayout box = page();
        box.addView(title("连不上"));
        box.addView(para("手机和电脑要在同一个 WiFi 下，电脑上要先双击运行「启动.bat」，黑窗口不要关。"
                       + "不想连电脑，点最下面那个按钮就行。"));
        box.addView(para("当前地址：" + prefs.server()));
        box.addView(bigButton("重试", new View.OnClickListener() {
            @Override public void onClick(View v) { openWeb(); }
        }), gap(20));
        box.addView(bigButton("改地址", new View.OnClickListener() {
            @Override public void onClick(View v) { showSetup(); }
        }), gap(10));
        root.addView(scroll(box));
    }

    /* ------------------------------------------------------------ 设置 */

    private void showSetup() {
        root.removeAllViews();
        LinearLayout box = page();
        box.addView(title("连电脑（可选）"));
        box.addView(para("不用填也能用 —— App 自己带数据，出门在外照样查。"
                       + "填了就走家里电脑上的服务，局域网里反应更快、也更省流量。"));
        box.addView(para("要用的话，先在电脑上运行「启动.bat」，把黑窗口里的地址填到下面："));
        box.addView(paraStrong("http://192.168.1.5:8765"));

        final EditText et = new EditText(this);
        et.setText(prefs.server().isEmpty() ? Prefs.DEFAULT_SERVER : prefs.server());
        et.setHint("http://192.168.1.5:8765");
        et.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        et.setSingleLine(true);
        et.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        et.setTextColor(Color.parseColor(INK));
        et.setBackgroundColor(Color.WHITE);
        et.setPadding(dp(16), dp(14), dp(16), dp(14));
        box.addView(et, gap(18));

        box.addView(bigButton("开始使用", new View.OnClickListener() {
            @Override public void onClick(View v) {
                String u = normalize(et.getText().toString());
                if (u.isEmpty()) { toast("地址不能空"); return; }
                prefs.server(u);
                openWeb();
            }
        }), gap(18));

        box.addView(bigButton("还是用手机自己的数据", new View.OnClickListener() {
            @Override public void onClick(View v) {
                prefs.server("");
                openWeb();
            }
        }), gap(10));

        box.addView(paraSmall("地址只要填一次。想改回来，点上面这个按钮。"));
        root.addView(scroll(box));
    }

    private String normalize(String raw) {
        String u = raw == null ? "" : raw.trim();
        if (u.isEmpty()) return "";
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "http://" + u;
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        return u;
    }

    /* ------------------------------------------------------------ 小工具 */

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private LinearLayout page() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        l.setBackgroundColor(Color.parseColor(BG));
        l.setPadding(dp(22), dp(52), dp(22), dp(28));
        return l;
    }

    private ScrollView scroll(View child) {
        ScrollView s = new ScrollView(this);
        s.setBackgroundColor(Color.parseColor(BG));
        s.setFillViewport(true);
        s.addView(child, new ViewGroup.LayoutParams(-1, -2));
        return s;
    }

    private TextView title(String t) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 30);
        v.setTextColor(Color.parseColor(BLUE));
        v.setGravity(Gravity.START);
        v.setPadding(0, 0, 0, dp(14));
        v.setTypeface(v.getTypeface(), 1);
        return v;
    }

    private TextView para(String t) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        v.setTextColor(Color.parseColor(SUB));
        v.setLineSpacing(dp(6), 1f);
        v.setPadding(0, 0, 0, dp(10));
        return v;
    }

    private TextView paraStrong(String t) {
        TextView v = para(t);
        v.setTextColor(Color.parseColor(BLUE));
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        v.setTypeface(v.getTypeface(), 1);
        return v;
    }

    private TextView paraSmall(String t) {
        TextView v = para(t);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        v.setTextColor(Color.parseColor("#8A8F94"));
        return v;
    }

    private Button bigButton(String t, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(t);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 19);
        b.setTextColor(Color.WHITE);
        b.setTypeface(b.getTypeface(), 1);
        b.setBackgroundColor(Color.parseColor(BLUE));
        b.setPadding(0, dp(16), 0, dp(16));
        b.setOnClickListener(l);
        return b;
    }

    private LinearLayout.LayoutParams gap(int h) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, -2);
        p.topMargin = dp(h);
        return p;
    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    /* ------------------------------------------------------------ 定位
       网页加载的是 http://192.168.x.x:8765，浏览器认为这不是安全来源，
       navigator.geolocation 直接拒绝。所以位置只能由 App 自己拿，
       再通过桥给页面。页面那边拿不到就说拿不到，不编坐标。 */
    private static volatile Location lastFix;

    private boolean hasLocPerm() {
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                   == PackageManager.PERMISSION_GRANTED
            || checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)
                   == PackageManager.PERMISSION_GRANTED;
    }

    private void askLocPerm() {
        if (Build.VERSION.SDK_INT >= 23 && !hasLocPerm()) {
            requestPermissions(new String[]{
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION}, 8);
        }
    }

    /** 要一次当前位置。异步回，结果写 lastFix，网页下次问就有值。 */
    private void requestOneFix() {
        if (!hasLocPerm()) return;
        runOnUiThread(new Runnable() {
            @Override public void run() {
                try {
                    LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
                    if (lm == null) return;
                    String prov = null;
                    if (lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                        prov = LocationManager.GPS_PROVIDER;
                    } else if (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                        prov = LocationManager.NETWORK_PROVIDER;
                    }
                    if (prov == null) return;
                    lm.requestSingleUpdate(prov, new LocationListener() {
                        @Override public void onLocationChanged(Location l) { lastFix = l; }
                        @Override public void onStatusChanged(String p, int st, Bundle b) {}
                        @Override public void onProviderEnabled(String p) {}
                        @Override public void onProviderDisabled(String p) {}
                    }, null);
                } catch (Exception ignored) {}
            }
        });
    }

    /* ------------------------------------------------------------ 给网页的桥 */

    public class Bridge {

        /** 网页上选定「还有几站响」时同步过来，后台服务才知道盯什么。 */
        @JavascriptInterface
        public void setWatch(String line, String dir, String station, double at) {
            final int n = (int) at;
            prefs.watch(line, dir, station, n);
            if (n > 0 && line != null && !line.isEmpty()) {
                if (!online()) { toast("手机没联网，提醒可能发不出"); }
                BusService.start(MainActivity.this);
            } else {
                BusService.stop(MainActivity.this);
            }
        }

        @JavascriptInterface
        public String getWatch() {
            return "{\"line\":\"" + safe(prefs.line()) + "\",\"dir\":\"" + safe(prefs.dir())
                 + "\",\"station\":\"" + safe(prefs.station()) + "\",\"at\":" + prefs.at() + "}";
        }

        @JavascriptInterface
        public boolean nativeOn() {
            return true;
        }

        /** 给网页的坐标，形如 "27.964,120.747"；拿不到回空串。 */
        @JavascriptInterface
        public String getLocation() {
            if (!hasLocPerm()) {
                runOnUiThread(new Runnable() {
                    @Override public void run() { askLocPerm(); }
                });
                return "";
            }
            long now = System.currentTimeMillis();
            Location l = lastFix;
            if (l == null) {
                // 退一步用系统缓存的最近位置，但太旧的不要 —— 人可能已经走远了
                try {
                    LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
                    if (lm != null) {
                        for (String p : lm.getProviders(true)) {
                            Location c = lm.getLastKnownLocation(p);
                            if (c != null && now - c.getTime() < 5 * 60 * 1000L) {
                                if (l == null || c.getTime() > l.getTime()) l = c;
                            }
                        }
                    }
                } catch (Exception ignored) {}
            }
            requestOneFix();          // 顺手更新，网页下一次问就是新的
            if (l == null || now - l.getTime() > 10 * 60 * 1000L) return "";
            return l.getLatitude() + "," + l.getLongitude();
        }

        @JavascriptInterface
        public String server() {
            return prefs.server();
        }

        @JavascriptInterface
        public void setServer(String s) {
            prefs.server(normalize(s));
            runOnUiThread(new Runnable() {
                @Override public void run() { openWeb(); }
            });
        }

        @JavascriptInterface
        public void settings() {
            runOnUiThread(new Runnable() {
                @Override public void run() { showSetup(); }
            });
        }

        @JavascriptInterface
        public void toast(final String s) {
            runOnUiThread(new Runnable() {
                @Override public void run() { MainActivity.this.toast(s); }
            });
        }

        private String safe(String s) {
            return s == null ? "" : s.replace("\\", "").replace("\"", "");
        }
    }

    private boolean online() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo n = cm.getActiveNetworkInfo();
            return n != null && n.isConnected();
        } catch (Exception e) {
            return true;
        }
    }

    /* ------------------------------------------------------------ 系统事件 */

    @Override
    public boolean onKeyDown(int code, KeyEvent e) {
        if (code == KeyEvent.KEYCODE_BACK && web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return super.onKeyDown(code, e);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onPause() {
        if (web != null) web.onPause();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            root.removeView(web);
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
