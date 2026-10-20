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
    private void arm(String id) throws Exception {
        JSONObject item = new JSONObject().put("id", id).put("kind", "alarm").put("title", "Muted alarm lab")
            .put("body", "Emulator -no-audio only").put("ack_required", true)
            .put("at", Instant.now().plusMillis(800).toString())
            .put("deadline_at", Instant.now().plusSeconds(600).toString());
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
}
