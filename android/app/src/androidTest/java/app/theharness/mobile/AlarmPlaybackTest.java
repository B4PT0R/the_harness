package app.theharness.mobile;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.SystemClock;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.time.Instant;
import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static org.junit.Assume.assumeTrue;

/** Run ONLY on an emulator launched with -no-audio. No microphone/network/phone test. */
@RunWith(AndroidJUnit4.class)
public class AlarmPlaybackTest {
    private Context context;
    private NativeAlerts alerts;
    private SharedPreferences prefs;
    private NotificationManager notifications;

    @Before public void setup() throws Exception {
        assumeTrue("Muted emulator lab only", Build.FINGERPRINT.contains("generic")
            || Build.MODEL.contains("sdk_gphone"));
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        context = instrumentation.getTargetContext();
        if (Build.VERSION.SDK_INT >= 33) instrumentation.getUiAutomation()
            .grantRuntimePermission(context.getPackageName(), Manifest.permission.POST_NOTIFICATIONS);
        try (var descriptor = instrumentation.getUiAutomation().executeShellCommand(
                "appops set " + context.getPackageName() + " SCHEDULE_EXACT_ALARM allow");
             var input = new java.io.FileInputStream(descriptor.getFileDescriptor())) { input.readAllBytes(); }
        alerts = NativeAlerts.get(context);
        alerts.disable();
        instrumentation.waitForIdleSync();
        notifications = context.getSystemService(NotificationManager.class);
        notifications.cancelAll();
        prefs = context.getSharedPreferences("native-alerts", Context.MODE_PRIVATE);
        alerts.enable();
    }
    @After public void cleanup() {
        if (alerts != null) {
            alerts.disable();
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            notifications.cancelAll();
        }
    }
    private Object field(Object object, String name) throws Exception {
        var field = (object == null ? AlarmPlayback.class : object.getClass()).getDeclaredField(name);
        field.setAccessible(true);
        return field.get(object);
    }
    private AlarmPlayback service() throws Exception { return (AlarmPlayback) field(null, "running"); }
    private void awaitPlayback(boolean present) throws Exception {
        for (int i = 0; i < 150; i++) {
            final boolean[] playing = {false};
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                try {
                    var service = service();
                    MediaPlayer player = service == null ? null : (MediaPlayer) field(service, "player");
                    playing[0] = player != null && player.isPlaying();
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
            if (playing[0] == present) return;
            Thread.sleep(100);
        }
        fail("Playback did not become " + present + "; receipts=" + prefs.getString("receipts", "{}"));
    }
    private void awaitServiceStopped() throws Exception {
        for (int i = 0; i < 50; i++) {
            final boolean[] stopped = {false};
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                try { stopped[0] = service() == null; }
                catch (Exception failure) { throw new AssertionError(failure); }
            });
            if (stopped[0]) return;
            Thread.sleep(100);
        }
        fail("Playback service did not stop");
    }
    private void arm(String id) throws Exception { arm(id, null); }
    private void arm(String id, String audioSrc) throws Exception {
        JSONObject item = new JSONObject().put("id", id).put("kind", "alarm").put("title", "Muted alarm lab")
            .put("body", "Emulator -no-audio only").put("ack_required", true)
            .put("at", Instant.now().plusMillis(800).toString())
            .put("deadline_at", Instant.now().plusSeconds(600).toString());
        if (audioSrc != null) item.put("audio_src", audioSrc);
        JSONObject cached = new JSONObject(prefs.getString("alerts", "{}"));
        cached.put(id, item);
        prefs.edit().putString("alerts", cached.toString()).commit();
        // Actual background AlarmManager -> BroadcastReceiver -> foreground-service path.
        alerts.rearm();
        for (int i = 0; i < 150 && !receipt(id, "fired"); i++) Thread.sleep(100);
        assertTrue("AlarmManager fired " + id, receipt(id, "fired"));
        awaitPlayback(true);
    }
    private boolean receipt(String id, String event) throws Exception {
        return new JSONObject(prefs.getString("receipts", "{}")).has(id + ":" + event);
    }
    private Notification ongoing() {
        for (var entry : notifications.getActiveNotifications())
            if (entry.getId() == AlarmPlayback.NOTIFICATION && entry.getTag() == null) return entry.getNotification();
        throw new AssertionError("Alarm foreground notification missing");
    }
    @Test public void loopsAcrossTrackEndAndAckReleasesAudioOffline() throws Exception {
        arm("loop-ack");
        var notification = ongoing();
        assertEquals("alarms-playback-v2", notification.getChannelId());
        assertNull(notifications.getNotificationChannel(notification.getChannelId()).getSound());
        assertTrue((notification.flags & Notification.FLAG_FOREGROUND_SERVICE) != 0);
        assertEquals("Arrêter et acquitter", notification.actions[0].title.toString());
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try {
                MediaPlayer player = (MediaPlayer) field(service(), "player");
                assertTrue(player.isLooping());
                assertTrue(player.getDuration() > 0);
                player.seekTo(Math.max(0, player.getDuration() - 200));
            } catch (Exception failure) { throw new AssertionError(failure); }
        });
        Thread.sleep(1800); // Past a real end-of-track: looping must still be playing.
        awaitPlayback(true);
        notification.actions[0].actionIntent.send();
        awaitPlayback(false);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        assertTrue(receipt("loop-ack", "acknowledged"));
        assertFalse(receipt("loop-ack", "auto_stopped"));
        awaitServiceStopped();
        alerts.rearm(); Thread.sleep(300);
        assertNull(service()); // Offline cached occurrence cannot restart after ACK.
    }
    @Test public void realThreeMinuteLimitStopsButDoesNotAcknowledge() throws Exception {
        assertEquals(180_000, AlarmPlayback.MAX_RING_MS);
        long before = SystemClock.elapsedRealtime();
        arm("three-minute-cap");
        Thread.sleep(61_000); // Explicit regression: former 60-second notification timeout.
        awaitPlayback(true);
        while (!receipt("three-minute-cap", "auto_stopped")
                && SystemClock.elapsedRealtime() - before < 190_000) Thread.sleep(200);
        long elapsed = SystemClock.elapsedRealtime() - before;
        assertTrue("Three-minute lower bound: " + elapsed, elapsed >= 180_000);
        assertTrue("Three-minute upper bound: " + elapsed, elapsed < 187_000);
        awaitPlayback(false);
        assertTrue(receipt("three-minute-cap", "auto_stopped"));
        assertFalse(receipt("three-minute-cap", "acknowledged"));
        // Keep a silent actionable notification after audio stops; timeout is NOT an ACK.
        Notification stopped = null;
        for (var entry : notifications.getActiveNotifications())
            if ("three-minute-cap".equals(entry.getTag())) stopped = entry.getNotification();
        assertNotNull(stopped);
        stopped.actions[0].actionIntent.send();
        Thread.sleep(300);
        assertTrue(receipt("three-minute-cap", "acknowledged"));
    }
    @Test public void disableStopsPlaybackAndReleasesService() throws Exception {
        arm("disable");
        alerts.disable();
        awaitPlayback(false);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        awaitServiceStopped();
        assertEquals(0, notifications.getActiveNotifications().length);
    }
    @Test public void overlappingAlarmsDoNotStopEachOtherOrExtendTheirDeadline() throws Exception {
        arm("first");
        final Object[] original = {null};
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try { original[0] = ((java.util.Map<?, ?>) field(service(), "ringing")).get("first"); }
            catch (Exception failure) { throw new AssertionError(failure); }
        });
        arm("second");
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try {
                var rings = (java.util.Map<?, ?>) field(service(), "ringing");
                assertEquals(2, rings.size());
                assertSame("Starting another alarm preserves the original deadline", original[0], rings.get("first"));
            } catch (Exception failure) { throw new AssertionError(failure); }
        });
        assertTrue(receipt("first", "fired")); assertTrue(receipt("second", "fired"));
        alerts.receive("second", NativeAlerts.ACK);
        Thread.sleep(300); awaitPlayback(true);
        assertEquals("Muted alarm lab", ongoing().extras.getString(Notification.EXTRA_TITLE));
        assertTrue(receipt("second", "acknowledged"));
        assertFalse(receipt("first", "acknowledged"));
        alerts.receive("first", NativeAlerts.ACK);
        awaitPlayback(false);
        assertTrue(receipt("first", "acknowledged"));
    }
    @Test public void cancelBeforeServiceStartsCannotPlayStaleAlarm() throws Exception {
        JSONObject item = new JSONObject().put("id", "cancelled").put("kind", "alarm")
            .put("at", Instant.now().minusSeconds(1).toString())
            .put("deadline_at", Instant.now().plusSeconds(600).toString()).put("cancelled", true);
        prefs.edit().putString("alerts", new JSONObject().put("cancelled", item).toString()).commit();
        assertNull(alerts.beginAlarm("cancelled"));
        alerts.receive("cancelled", NativeAlerts.FIRE);
        Thread.sleep(300); assertNull(service());
    }
    static void silentWav(java.io.File file, int milliseconds) throws Exception {
        int size = 8000 * milliseconds / 1000 * 2;
        var bytes = java.nio.ByteBuffer.allocate(44 + size).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        bytes.put("RIFF".getBytes(java.nio.charset.StandardCharsets.US_ASCII)).putInt(36 + size)
            .put("WAVEfmt ".getBytes(java.nio.charset.StandardCharsets.US_ASCII)).putInt(16)
            .putShort((short) 1).putShort((short) 1).putInt(8000).putInt(16000)
            .putShort((short) 2).putShort((short) 16)
            .put("data".getBytes(java.nio.charset.StandardCharsets.US_ASCII)).putInt(size);
        try (var out = new java.io.FileOutputStream(file)) { out.write(bytes.array()); }
    }
    private void assertTrackDuration(int expected) {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            try {
                var player = (MediaPlayer) field(service(), "player");
                assertEquals(expected, player.getDuration());
                assertTrue(player.isLooping());
            } catch (Exception failure) { throw new AssertionError(failure); }
        });
    }
    @Test public void cachedSpeechPlaysOfflineAndOverlappingVoicesResume() throws Exception {
        AlarmAudio cache = new AlarmAudio(context);
        String first = "/api/v1/bucket/first.wav", second = "/api/v1/bucket/second.wav";
        silentWav(cache.file(first), 1000); silentWav(cache.file(second), 1600);
        AlarmAudio.validate(cache.file(first));
        assertTrue(cache.prepare(new JSONObject(), first, 0)); // No credential/network needed for preloaded bytes.
        arm("voice-first", first);
        assertTrackDuration(1000);
        Thread.sleep(1300); // Real loop over end-of-file.
        awaitPlayback(true);
        arm("voice-second", second);
        assertTrackDuration(1600);
        alerts.receive("voice-second", NativeAlerts.ACK);
        Thread.sleep(300); awaitPlayback(true); assertTrackDuration(1000);
        alerts.receive("voice-first", NativeAlerts.ACK);
        awaitPlayback(false); awaitServiceStopped();
    }
    @Test public void missingSpeechFallsBackToRingtoneAndReportsUnavailability() throws Exception {
        arm("missing-voice", "/api/v1/bucket/missing.wav");
        assertTrue(receipt("missing-voice", "audio_unavailable"));
        awaitPlayback(true);
        alerts.receive("missing-voice", NativeAlerts.ACK);
        awaitPlayback(false);
    }
    @Test public void invalidSpeechFallsBackRatherThanSilencingAlarm() throws Exception {
        String src = "/api/v1/bucket/corrupt.wav";
        try (var out = new java.io.FileOutputStream(new AlarmAudio(context).file(src))) { out.write(new byte[]{1, 2, 3}); }
        arm("corrupt-voice", src);
        assertTrue(receipt("corrupt-voice", "audio_unavailable"));
        assertNull(new AlarmAudio(context).cached(src));
        awaitPlayback(true);
        alerts.receive("corrupt-voice", NativeAlerts.ACK);
        awaitPlayback(false);
    }
    @Test public void cacheRejectsUnsafePathsAndPrunesOnDisable() throws Exception {
        for (String src : new String[]{"https://host/a.wav", "//host/a.wav", "/api/v1/bucket/../a",
                "/api/v1/bucket/a?secret=x", "/api/v1/bucket/%2e.wav", "/api/v1/bucket/"})
            assertFalse(src, AlarmAudio.allowed(src));
        AlarmAudio cache = new AlarmAudio(context);
        String kept = "/api/v1/bucket/kept.wav", discarded = "/api/v1/bucket/discarded.wav";
        silentWav(cache.file(kept), 1000); silentWav(cache.file(discarded), 1000);
        cache.prune(new org.json.JSONArray().put(new JSONObject().put("audio_src", kept)));
        assertNotNull(cache.cached(kept)); assertNull(cache.cached(discarded));
        assertTrue(cache.prepare(new JSONObject(), kept, 0)); // Cached voice needs no network.
        assertFalse(cache.prepare(new JSONObject(), discarded, 0)); // Expired budget never fetches.
        assertFalse(cache.prepare(new JSONObject(), "https://host/leak", SystemClock.elapsedRealtime() + 1000));
        alerts.disable();
        assertNull(cache.cached(kept));
    }

}
