package app.theharness.mobile;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Native alarms survive WebView/process closure; system broadcasts only re-arm cached events. */
public final class AlertReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        NativeAlerts alerts = NativeAlerts.get(context);
        String action = intent.getAction();
        if (NativeAlerts.FIRE.equals(action) || NativeAlerts.ACK.equals(action)) alerts.receive(intent.getStringExtra("id"), action);
        else {
            alerts.rearm();
            if (Intent.ACTION_BOOT_COMPLETED.equals(action) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(action))
                PrivateReceiver.resume(context);
        }
    }
}
