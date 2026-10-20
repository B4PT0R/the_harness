package app.theharness.mobile;

import android.app.ActivityManager;
import android.app.Application;
import android.app.NotificationManager;
import android.content.Context;
import android.os.Build;
import android.util.AtomicFile;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Collections;
import java.util.IdentityHashMap;

/** Local, opt-in export. Never collect exception messages, URLs, tokens or chat content. */
public final class Diagnostics extends Application {
    private static File crashFile(Context context) { return new File(context.getFilesDir(), "last-crash.txt"); }
    @Override public void onCreate() {
        super.onCreate();
        var previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler(handler(this, previous));
    }
    static Thread.UncaughtExceptionHandler handler(Context context, Thread.UncaughtExceptionHandler previous) {
        return (thread, error) -> {
            try { saveCrash(context, error); } catch (Throwable ignored) { /* Preserve Android's crash handling. */ }
            if (previous != null) previous.uncaughtException(thread, error);
            else { android.os.Process.killProcess(android.os.Process.myPid()); System.exit(10); }
        };
    }
    static String stack(Throwable error) {
        StringBuilder text = new StringBuilder();
        var seen = Collections.newSetFromMap(new IdentityHashMap<Throwable, Boolean>());
        for (int depth = 0; error != null && depth < 6 && seen.add(error); depth++, error = error.getCause()) {
            text.append(depth == 0 ? "Exception: " : "Cause: ").append(error.getClass().getName()).append('\n');
            var frames = error.getStackTrace();
            for (int i = 0; i < Math.min(frames.length, 40); i++) {
                var frame = frames[i];
                // Omit Throwable messages and source filenames; retain symbols and line numbers.
                text.append("  at ").append(frame.getClassName()).append('.').append(frame.getMethodName())
                    .append(':').append(frame.getLineNumber()).append('\n');
            }
        }
        return text.toString();
    }
    static void saveCrash(Context context, Throwable error) throws Exception {
        AtomicFile file = new AtomicFile(crashFile(context));
        var output = file.startWrite();
        try {
            String text = "UTC: " + Instant.now() + "\nVersion: " + BuildConfig.VERSION_NAME + "\n" + stack(error);
            output.write(text.getBytes(StandardCharsets.UTF_8));
            file.finishWrite(output);
        } catch (Exception failure) { file.failWrite(output); throw failure; }
    }
    static void clear(Context context) { new AtomicFile(crashFile(context)).delete(); }
    static String report(Context context) {
        StringBuilder text = new StringBuilder("The Harness — diagnostic local\n");
        text.append("UTC: ").append(Instant.now()).append("\nVersion: ").append(BuildConfig.VERSION_NAME)
            .append(" (SDK ").append(Build.VERSION.SDK_INT).append(")\n");
        text.append("Messages, identifiants, adresses et contenu des notifications exclus.\n\n");
        NativeAlerts alerts = NativeAlerts.get(context);
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        text.append("Alertes activées: ").append(alerts.enabled())
            .append("\nNotifications autorisées: ").append(manager.areNotificationsEnabled())
            .append("\nAlarmes exactes autorisées: ").append(alerts.exactAllowed())
            .append("\nRéception privée activée: ").append(PrivateReceiver.enabled(context)).append('\n');
        var channel = manager.getNotificationChannel(NativeAlerts.ALARMS);
        text.append("Canal alarme: ").append(channel == null ? "absent" : "importance=" + channel.getImportance()).append('\n');
        if (Build.VERSION.SDK_INT >= 30) {
            text.append("\nDernières fins de processus Android (métadonnées, pas leurs traces):\n");
            try {
                for (var exit : context.getSystemService(ActivityManager.class)
                        .getHistoricalProcessExitReasons(context.getPackageName(), 0, 5))
                    text.append(Instant.ofEpochMilli(exit.getTimestamp())).append(" reason=").append(exit.getReason())
                        .append(" status=").append(exit.getStatus()).append('\n');
            } catch (RuntimeException unavailable) { text.append("Historique indisponible.\n"); }
        }
        text.append("\nDernière exception Java capturée:\n");
        try (var input = new AtomicFile(crashFile(context)).openRead()) {
            byte[] buffer = new byte[65536];
            int size = 0, count;
            while (size < buffer.length && (count = input.read(buffer, size, buffer.length - size)) != -1) size += count;
            text.append(new String(buffer, 0, size, StandardCharsets.UTF_8));
        } catch (java.io.FileNotFoundException absent) { text.append("Aucune depuis l’installation du diagnostic.\n"); }
        catch (Exception unavailable) { text.append("Lecture indisponible.\n"); }
        return text.toString();
    }
}
