package com.leina.bus;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;

/**
 * 后台盯站的服务。
 *
 * 网页一被切到后台就被系统冻住，JavaScript 不再跑，所以响铃只能交给这里。
 * 它是个前台服务：状态栏有一行「正在看着 36 路」，系统不会随手把它清掉；
 * 每 30 秒问一次本地服务，到条件就响铃、震动、弹通知。
 */
public class BusService extends Service {

    public static final String CH_RUN = "run";
    public static final String CH_ALERT = "alert";

    private static final int NOTI_RUN = 1001;
    private static final int NOTI_ALERT = 1002;
    private static final long PERIOD = 30_000L;

    private Handler handler;
    private Runnable tick;
    private Prefs prefs;

    /** 同一趟车只提醒一次；车又变远了才重新武装。 */
    private boolean firedComing = false;
    private boolean firedHere = false;
    private String lastLine = "";
    private String lastText = "";

    public static void start(Context c) {
        Intent i = new Intent(c, BusService.class);
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i);
        else c.startService(i);
    }

    public static void stop(Context c) {
        c.stopService(new Intent(c, BusService.class));
    }

    @Override
    public void onCreate() {
        super.onCreate();
        prefs = new Prefs(this);
        handler = new Handler(Looper.getMainLooper());
        channels();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification n = runningNote("正在看着 " + label() + " 的到站", "车快到了会响一声");
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTI_RUN, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTI_RUN, n);
        }

        if (!prefs.watchOn()) {
            stopSelf();
            return START_NOT_STICKY;
        }

        if (tick != null) handler.removeCallbacks(tick);
        tick = new Runnable() {
            @Override public void run() {
                poll();
                handler.postDelayed(this, PERIOD);
            }
        };
        handler.post(tick);
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (handler != null && tick != null) handler.removeCallbacks(tick);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    /* ------------------------------------------------------------ 轮询 */

    private void poll() {
        final String server = prefs.server();
        final String line = prefs.line();
        final String dir = prefs.dir();
        final String station = prefs.station();
        final int at = prefs.at();

        // 没填服务器 = 用装在手机里的那一套，自己上网查，不需要电脑
        if (line.isEmpty() || at <= 0) return;

        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    Api.Board b = server.isEmpty()
                            ? Api.boardLocal(line, dir, station)
                            : Api.board(server, line, dir, station);
                    if (!b.ok) {
                        note("查不到：" + (b.error == null ? "无数据" : b.error));
                        return;
                    }
                    judge(b, at);
                } catch (Exception e) {
                    note("连不上服务，重试中");
                }
            }
        }).start();
    }

    private void judge(Api.Board b, int at) {
        lineChanged();   // 换线路了，内部会把「已提醒」清掉

        Integer st = b.stations;
        String where = b.toShort == null || b.toShort.isEmpty() ? "" : "，往 " + b.toShort;

        // 车又走远了（比如刚发车），重新武装
        if (st != null && st > at) {
            firedComing = false;
            firedHere = false;
        }

        String line1 = b.minutes != null ? (b.minutes == 0 ? "马上到" : b.minutes + " 分钟")
                                         : (st != null ? "还有 " + st + " 站" : "在途");
        note("正在看着 " + label() + " · " + line1);

        if (st != null && st <= at && !firedComing) {
            firedComing = true;
            ring(3);
            alert("车还有 " + st + " 站", "该出门了" + where);
            return;
        }

        boolean here = "here".equals(b.status) || (b.minutes != null && b.minutes == 0);
        if (here && !firedHere) {
            firedHere = true;
            firedComing = true;
            ring(4);
            alert("车到站了", "快上车" + where);
        }
    }

    private boolean lineChanged() {
        String now = prefs.line() + "/" + prefs.dir();
        if (!now.equals(lastLine)) {
            lastLine = now;
            firedComing = false;
            firedHere = false;
            return true;
        }
        return false;
    }

    private String label() {
        String l = prefs.line();
        String s = prefs.station();
        if (l.isEmpty()) return "公交";
        return s.isEmpty() ? l : l + " · " + s + "站";
    }

    /* ------------------------------------------------------------ 响铃 */

    /** 响 ring 次。走闹钟音量，老人听不清也听得见。 */
    private void ring(final int times) {
        try {
            final ToneGenerator tg = new ToneGenerator(AudioManager.STREAM_ALARM, 100);
            for (int i = 0; i < times; i++) {
                final int k = i;
                handler.postDelayed(new Runnable() {
                    @Override public void run() {
                        try {
                            tg.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD, 700);
                        } catch (Exception ignored) { }
                        if (k == times - 1) {
                            handler.postDelayed(new Runnable() {
                                @Override public void run() { tg.release(); }
                            }, 1200);
                        }
                    }
                }, i * 900L);
            }
        } catch (Exception e) {
            // 没有可用的音频通道就只靠震动和通知
        }
        buzz(times >= 4 ? 3 : 2);
    }

    private void buzz(int n) {
        try {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (v == null || !v.hasVibrator()) return;
            long[] p = new long[n * 2];
            for (int i = 0; i < n; i++) { p[i * 2] = 280; p[i * 2 + 1] = 160; }
            if (Build.VERSION.SDK_INT >= 26) {
                v.vibrate(VibrationEffect.createWaveform(p, -1));
            } else {
                v.vibrate(p, -1);
            }
        } catch (Exception ignored) { }
    }

    /* ------------------------------------------------------------ 通知 */

    private void channels() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager m = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);

        NotificationChannel run = new NotificationChannel(
                CH_RUN, "后台盯站", NotificationManager.IMPORTANCE_LOW);
        run.setShowBadge(false);
        run.enableVibration(false);
        m.createNotificationChannel(run);

        NotificationChannel alert = new NotificationChannel(
                CH_ALERT, "到站提醒", NotificationManager.IMPORTANCE_HIGH);
        alert.setShowBadge(true);
        alert.enableVibration(true);
        // 铃声由本服务自己放（音量更大），渠道静音避免响两遍
        alert.setSound(null, null);
        m.createNotificationChannel(alert);
    }

    private PendingIntent open() {
        Intent i = new Intent(this, MainActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int f = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        return PendingIntent.getActivity(this, 0, i, f);
    }

    private Notification runningNote(String title, String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CH_RUN)
                : new Notification.Builder(this);
        b.setContentTitle(title)
         .setContentText(text)
         .setSmallIcon(android.R.drawable.ic_menu_mylocation)
         .setOngoing(true)
         .setOnlyAlertOnce(true)
         .setContentIntent(open());
        if (Build.VERSION.SDK_INT >= 21) b.setPriority(Notification.PRIORITY_LOW);
        return b.build();
    }

    /** 只刷新状态栏那行字，不弹新通知。 */
    private void note(String text) {
        if (text == null || text.equals(lastText)) return;
        lastText = text;
        NotificationManager m = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        m.notify(NOTI_RUN, runningNote(text, "车快到了会响一声"));
    }

    /** 真正弹出来的提醒：响铃 + 震动 + 通知。 */
    private void alert(String title, String text) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CH_ALERT)
                : new Notification.Builder(this);
        b.setContentTitle(title)
         .setContentText(text)
         .setSmallIcon(android.R.drawable.ic_dialog_info)
         .setAutoCancel(true)
         .setContentIntent(open());
        if (Build.VERSION.SDK_INT >= 21) b.setPriority(Notification.PRIORITY_HIGH);
        NotificationManager m = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        m.notify(NOTI_ALERT, b.build());
    }
}
