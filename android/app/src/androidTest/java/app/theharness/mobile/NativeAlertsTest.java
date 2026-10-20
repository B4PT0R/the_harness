package app.theharness.mobile;

import android.Manifest;
import android.app.AlarmManager;
import android.app.NotificationManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
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

/** Emulator only. Never posts to the alarm channel or exercises audio capture. */
@RunWith(AndroidJUnit4.class)
public class NativeAlertsTest {
    private Context context;
    private NativeAlerts alerts;
    private SharedPreferences prefs;
    private NotificationManager notifications;

    @Before public void setup() {
        assumeTrue("Silent emulator lab only", Build.FINGERPRINT.contains("generic")
            || Build.MODEL.contains("sdk_gphone"));
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        context = instrumentation.getTargetContext();
        if (Build.VERSION.SDK_INT >= 33) instrumentation.getUiAutomation()
            .grantRuntimePermission(context.getPackageName(), Manifest.permission.POST_NOTIFICATIONS);
        alerts = NativeAlerts.get(context);
        alerts.disable();
        prefs = context.getSharedPreferences("native-alerts", Context.MODE_PRIVATE);
        notifications = context.getSystemService(NotificationManager.class);
        alerts.enable();
    }
    @After public void cleanup() { if (alerts != null) alerts.disable(); }

    private JSONObject item(String kind, long seconds) throws Exception {
        return new JSONObject().put("id", "silent-lab").put("kind", kind).put("title", "Essai silencieux")
            .put("body", "Aucune sonnerie").put("ack_required", true)
            .put("at", Instant.now().plusSeconds(seconds).toString())
            .put("deadline_at", Instant.now().plusSeconds(seconds + 120).toString());
    }
    private void cache(JSONObject item) throws Exception {
        prefs.edit().putString("alerts", new JSONObject().put(item.getString("id"), item).toString()).commit();
    }
    private void awaitNotification(boolean present) throws Exception {
        for (int i = 0; i < 50; i++) {
            if ((notifications.getActiveNotifications().length > 0) == present) return;
            Thread.sleep(100);
        }
        assertEquals(present, notifications.getActiveNotifications().length > 0);
    }
    @Test public void silentNotificationDeduplicatesAndAcknowledgesOffline() throws Exception {
        assertNull(notifications.getNotificationChannel("reminders-silent-v1").getSound());
        cache(item("message", -1));
        alerts.receive("silent-lab", NativeAlerts.FIRE);
        awaitNotification(true);
        var shown = notifications.getActiveNotifications()[0].getNotification();
        assertEquals("reminders-silent-v1", shown.getChannelId());
        assertEquals(1, shown.actions.length);
        String first = prefs.getString("fired", "{}");
        alerts.receive("silent-lab", NativeAlerts.FIRE);
        assertEquals(first, prefs.getString("fired", "{}"));
        alerts.receive("silent-lab", NativeAlerts.ACK);
        awaitNotification(false);
        JSONObject receipts = new JSONObject(prefs.getString("receipts", "{}"));
        assertEquals("acknowledged", receipts.getJSONObject("silent-lab:acknowledged").getString("event"));
        assertTrue(receipts.has("silent-lab:fired"));
        // Cached occurrence cannot reappear before the offline receipt is delivered.
        alerts.rearm();
        assertEquals(first, prefs.getString("fired", "{}"));
    }
    @Test public void realAlarmClockCanArmAndCancelWithoutFiring() throws Exception {
        if (Build.VERSION.SDK_INT >= 31) {
            try (var descriptor = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("appops set " + context.getPackageName() + " SCHEDULE_EXACT_ALARM allow");
                 var input = new java.io.FileInputStream(descriptor.getFileDescriptor())) {
                input.readAllBytes();
            }
        }
        assertTrue("Emulator exact-alarm access", alerts.exactAllowed());
        cache(item("alarm", 86400)); // Tomorrow: never trigger or post an audible notification.
        alerts.rearm();
        assertNotNull(context.getSystemService(AlarmManager.class).getNextAlarmClock());
        JSONObject receipts = new JSONObject(prefs.getString("receipts", "{}"));
        assertTrue(receipts.has("silent-lab:armed"));
        alerts.disable();
        assertNull(context.getSystemService(AlarmManager.class).getNextAlarmClock());
        assertEquals(0, notifications.getActiveNotifications().length);
    }
    @Test public void deliveredReceiptsAreNotRequeuedOnEachSync() throws Exception {
        JSONObject item = item("message", 60);
        String key = "silent-lab:armed";
        prefs.edit().putString("reported", new JSONObject().put(key, System.currentTimeMillis()).toString()).commit();
        alerts.receipt(item, "armed");
        assertFalse(new JSONObject(prefs.getString("receipts", "{}")).has(key));
        alerts.receipt(item, "acknowledged");
        assertTrue(new JSONObject(prefs.getString("receipts", "{}")).has("silent-lab:acknowledged"));
    }
    @Test public void settingsDialogShowsPermissionsAndNoPushLimitation() throws Exception {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        try (var scenario = androidx.test.core.app.ActivityScenario.launch(MainActivity.class)) {
            instrumentation.waitForIdleSync();
            scenario.onActivity(activity -> {
                try {
                    var method = MainActivity.class.getDeclaredMethod("alertSettings");
                    method.setAccessible(true); method.invoke(activity);
                } catch (Exception failure) { throw new AssertionError(failure); }
            });
            instrumentation.waitForIdleSync();
            Thread.sleep(300);
            var root = instrumentation.getUiAutomation().getRootInActiveWindow();
            assertNotNull(root);
            assertFalse(root.findAccessibilityNodeInfosByText("Alertes locales et alarmes").isEmpty());
            assertFalse(root.findAccessibilityNodeInfosByText("pas de push instantané").isEmpty());
            try (var descriptor = instrumentation.getUiAutomation()
                .executeShellCommand("screencap -p /data/local/tmp/harness-alerts-lab.png");
                 var input = new java.io.FileInputStream(descriptor.getFileDescriptor())) { input.readAllBytes(); }
        }
    }
    @Test public void disabledCacheCannotDisplayOrAcknowledge() throws Exception {
        cache(item("message", -1));
        alerts.disable();
        alerts.receive("silent-lab", NativeAlerts.FIRE);
        alerts.receive("silent-lab", NativeAlerts.ACK);
        assertFalse(alerts.enabled());
        assertEquals("{}", prefs.getString("receipts", "{}"));
        assertEquals(0, notifications.getActiveNotifications().length);
    }
}
