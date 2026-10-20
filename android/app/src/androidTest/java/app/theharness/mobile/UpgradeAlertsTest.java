package app.theharness.mobile;

import android.app.NotificationManager;
import android.content.Context;
import android.os.Build;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static org.junit.Assume.assumeTrue;

/** Run immediately after installing 0.1.6 over 0.1.4 with alerts enabled. No alarm fires. */
@RunWith(AndroidJUnit4.class)
public class UpgradeAlertsTest {
    @Test public void upgradeCreatesSilentAlarmChannelWithoutChangingSavedConsent() throws Exception {
        assumeTrue(Build.FINGERPRINT.contains("generic") || Build.MODEL.contains("sdk_gphone"));
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        var prefs = context.getSharedPreferences("native-alerts", Context.MODE_PRIVATE);
        assertTrue("Prepare an enabled pre-upgrade fixture", prefs.getBoolean("enabled", false));
        assertEquals("preserved", prefs.getString("upgrade_marker", ""));
        var alerts = NativeAlerts.get(context);
        alerts.rearm();
        var channel = context.getSystemService(NotificationManager.class).getNotificationChannel(NativeAlerts.ALARMS);
        assertNotNull(channel); assertNull(channel.getSound()); assertFalse(channel.shouldVibrate());
        assertTrue(alerts.enabled());
        assertEquals("preserved", prefs.getString("upgrade_marker", ""));
        assertFalse("Upgrade must not opt in to the private receiver", PrivateReceiver.enabled(context));
        alerts.disable();
        alerts.rearm();
        assertFalse("Repair must never enable a disabled feature", alerts.enabled());
    }
}
