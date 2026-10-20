package app.theharness.mobile;

import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import java.util.LinkedHashMap;
import org.json.JSONObject;

/** Explicit, bounded local audio; notification sound/FLAG_INSISTENT is not a loop contract. */
public final class AlarmPlayback extends Service {
    static final long MAX_RING_MS = 180_000;
    static final int NOTIFICATION = 3301;
    private static AlarmPlayback running; // Main-thread owned, including all playback controls.
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final LinkedHashMap<String, Ring> ringing = new LinkedHashMap<>();
    private record Ring(JSONObject item, long until) {}
    private MediaPlayer player;
    private AudioManager audio;
    private AudioFocusRequest focus;
    private final Runnable timeout = () -> expire(SystemClock.elapsedRealtime());

    static void start(Context context, String id) {
        context.startForegroundService(new Intent(context, AlarmPlayback.class).putExtra("id", id));
    }
    static void stop(String id) {
        new Handler(Looper.getMainLooper()).post(() -> {
            if (running != null) running.remove(id);
        });
    }
    @Override public void onCreate() { super.onCreate(); running = this; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        NativeAlerts alerts = NativeAlerts.get(this);
        String id = intent == null ? null : intent.getStringExtra("id");
        JSONObject item = alerts.beginAlarm(id);
        if (item == null) {
            if (ringing.isEmpty()) stopSelf();
            return START_NOT_STICKY;
        }
        ringing.put(id, new Ring(item, SystemClock.elapsedRealtime() + MAX_RING_MS));
        try {
            refresh(); // Foreground BEFORE audio/focus, including while app is in background.
            if (player == null) startAudio();
            alerts.receipt(item, "fired");
        } catch (Exception failure) {
            alerts.receipt(item, "error");
            remove(id);
        }
        alerts.requestSync();
        return START_NOT_STICKY; // Never restart/replay an alarm after process death.
    }
    private void startAudio() throws Exception {
        AudioAttributes attributes = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
        audio = getSystemService(AudioManager.class);
        focus = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
            .setAudioAttributes(attributes).setOnAudioFocusChangeListener(change -> {
                if (player == null) return;
                if (change == AudioManager.AUDIOFOCUS_GAIN) {
                    expire(SystemClock.elapsedRealtime());
                    if (player != null) player.start();
                } else if (change == AudioManager.AUDIOFOCUS_LOSS) {
                    finishAll("error");
                } else player.pause();
            }, handler).build();
        if (audio.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED)
            throw new IllegalStateException("Alarm audio focus denied");
        player = new MediaPlayer();
        player.setAudioAttributes(attributes);
        player.setWakeMode(this, PowerManager.PARTIAL_WAKE_LOCK);
        var uri = RingtoneManager.getActualDefaultRingtoneUri(this, RingtoneManager.TYPE_ALARM);
        if (uri == null) uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
        player.setDataSource(this, uri);
        player.setLooping(true);
        player.setOnErrorListener((failed, what, extra) -> { finishAll("error"); return true; });
        player.prepare();
        player.start();
    }
    private void refresh() {
        handler.removeCallbacks(timeout);
        if (ringing.isEmpty()) {
            releaseAudio();
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
            return;
        }
        Ring latest = null;
        long next = Long.MAX_VALUE;
        for (Ring ring : ringing.values()) { latest = ring; next = Math.min(next, ring.until()); }
        var notification = NativeAlerts.get(this).notification(latest.item(), true);
        if (Build.VERSION.SDK_INT >= 29)
            startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        else startForeground(NOTIFICATION, notification);
        handler.postDelayed(timeout, Math.max(0, next - SystemClock.elapsedRealtime()));
    }
    private void remove(String id) {
        if (ringing.remove(id) != null) refresh();
    }
    // Elapsed time, independent of wall-clock changes. Each occurrence has its own three-minute cap.
    void expire(long now) {
        NativeAlerts alerts = NativeAlerts.get(this);
        for (var entries = ringing.entrySet().iterator(); entries.hasNext();) {
            var entry = entries.next();
            if (entry.getValue().until() <= now) {
                JSONObject item = entry.getValue().item();
                alerts.receipt(item, "auto_stopped");
                getSystemService(NotificationManager.class).notify(entry.getKey(), 0, alerts.notification(item, false));
                entries.remove();
            }
        }
        refresh();
        alerts.requestSync();
    }
    private void finishAll(String event) {
        NativeAlerts alerts = NativeAlerts.get(this);
        for (Ring ring : ringing.values()) alerts.receipt(ring.item(), event);
        ringing.clear(); refresh(); alerts.requestSync();
    }
    private void releaseAudio() {
        if (player != null) { player.release(); player = null; }
        if (audio != null && focus != null) audio.abandonAudioFocusRequest(focus);
        focus = null;
    }
    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        releaseAudio(); ringing.clear();
        stopForeground(STOP_FOREGROUND_REMOVE);
        if (running == this) running = null;
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
