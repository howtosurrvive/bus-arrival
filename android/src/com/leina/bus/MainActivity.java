package com.leina.bus;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
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
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

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

    private Prefs prefs;
    private FrameLayout root;
    private WebView web;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        prefs = new Prefs(this);

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor(BG));
        setContentView(root);

        if (prefs.server().isEmpty()) showSetup();
        else openWeb();

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
            web.setBackgroundColor(Color.parseColor(BG));
            web.setOverScrollMode(View.OVER_SCROLL_NEVER);
            web.addJavascriptInterface(new Bridge(), "AndroidBridge");
            web.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView v, String url) {
                    return false;   // 就一个站内页面，全部自己加载
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
                    if (req != null && req.isForMainFrame()) showOffline();
                }
            });
        }
        root.removeAllViews();
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        web.loadUrl(prefs.server() + "/");

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                   != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 7);
        }
    }

    /** 连不上电脑上的服务时，给一个能看懂、能自己救回来的页面。 */
    private void showOffline() {
        root.removeAllViews();
        LinearLayout box = page();
        box.addView(title("连不上"));
        box.addView(para("手机和电脑要在同一个 WiFi 下，电脑上要先双击运行「启动.bat」，黑窗口不要关。"));
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
        box.addView(title("公交到站"));
        box.addView(para("在电脑上运行「启动.bat」，把黑窗口里显示的地址填到下面。像这样："));
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

        box.addView(paraSmall("地址只要填一次，以后开机就直接进查询页。"));
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
