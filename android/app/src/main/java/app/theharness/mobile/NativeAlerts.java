package app.theharness.mobile;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.Instant;

/** Local schedule, receipts and shared notification cursor; never infer task completion. */
final class NativeAlerts {
    static final String FIRE = "app.theharness.mobile.ALERT", ACK = "app.theharness.mobile.ACK";
    private static final int JOB = 3101, URGENT_JOB = 3102;
    private static final String MESSAGES = "reminders-silent-v1", ALARMS = "alarms-v1";
    private final Context context;
    private final SharedPreferences prefs;
    private static NativeAlerts instance;
    static synchronized NativeAlerts get(Context context) {
        if (instance == null) instance = new NativeAlerts(context);
        return instance;
    }
    private NativeAlerts(Context context) {
        this.context = context.getApplicationContext();
        prefs = this.context.getSharedPreferences("native-alerts", Context.MODE_PRIVATE);
    }
    volatile boolean foreground;
    boolean enabled() { return prefs.getBoolean("enabled", false); }
    private JSONObject read(String key) {
        try { return new JSONObject(prefs.getString(key, "{}")); }
        catch (Exception ignored) { return new JSONObject(); }
    }
    private void write(String key, JSONObject value) { prefs.edit().putString(key, value.toString()).commit(); }
    private AlarmManager alarms() { return context.getSystemService(AlarmManager.class); }
    private NotificationManager notifications() { return context.getSystemService(NotificationManager.class); }
    boolean exactAllowed() { return Build.VERSION.SDK_INT < 31 || alarms().canScheduleExactAlarms(); }
    private PendingIntent action(String id, String action) {
        Intent intent = new Intent(context, AlertReceiver.class).setAction(action)
            .setData(Uri.parse("harness-alert://local/" + Uri.encode(id))).putExtra("id", id);
        return PendingIntent.getBroadcast(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private PendingIntent open(String id) {
        // No URI: pairing links and local notification opens must never be confused.
        return PendingIntent.getActivity(context, id.hashCode(), new Intent(context, MainActivity.class),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private boolean paired() { return context.getSharedPreferences("pairing", Context.MODE_PRIVATE).contains("credential"); }
    synchronized void enable() {
        prefs.edit().putBoolean("enabled", true).commit();
        NotificationChannel messages = new NotificationChannel(MESSAGES, "Rappels silencieux", NotificationManager.IMPORTANCE_DEFAULT);
        messages.setSound(null, null); messages.enableVibration(false);
        NotificationChannel alarm = new NotificationChannel(ALARMS, "Alarmes demandées", NotificationManager.IMPORTANCE_HIGH);
        alarm.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
            new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).build());
        notifications().createNotificationChannel(messages); notifications().createNotificationChannel(alarm);
        if (paired()) context.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(JOB,
            new ComponentName(context, AlertSyncJob.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
            .setPersisted(true).setPeriodic(15 * 60_000L).build());
        requestSync();
    }
    synchronized void disable() {
        PrivateReceiver.disable(context);
        JSONObject cached = read("alerts");
        for (var ids = cached.keys(); ids.hasNext();) cancel(ids.next());
        notifications().cancel("conversation", 0);
        prefs.edit().clear().commit();
        context.getSystemService(JobScheduler.class).cancel(JOB);
        context.getSystemService(JobScheduler.class).cancel(URGENT_JOB);
    }
    void requestSync() {
        if (enabled() && paired())
            context.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(URGENT_JOB,
            new ComponentName(context, AlertSyncJob.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
            .setMinimumLatency(0).build());
    }
    private void cancel(String id) {
        alarms().cancel(action(id, FIRE)); notifications().cancel(id, 0);
    }
    synchronized void receipt(JSONObject item, String event) {
        if (!item.optBoolean("ack_required")) return;
        try {
            JSONObject queue = read("receipts");
            String key = item.getString("id") + ":" + event;
            if (read("reported").has(key)) return;
            if (queue.length() >= 2048 && !queue.has(key)) {
                if (!"acknowledged".equals(event)) return;
                for (var keys = queue.keys(); keys.hasNext();) {
                    String candidate = keys.next();
                    if (!candidate.endsWith(":acknowledged")) { queue.remove(candidate); break; }
                }
            }
            queue.put(key, new JSONObject().put("wait_id", item.getString("id")).put("event", event));
            write("receipts", queue);
        } catch (Exception ignored) { error("Impossible d’enregistrer un reçu."); }
    }
    private void error(String message) { prefs.edit().putString("error", message).commit(); }
    static long time(JSONObject item, String field) { return Instant.parse(item.optString(field)).toEpochMilli(); }
    private void arm(JSONObject item) {
        try {
            String id = item.getString("id");
            long now = System.currentTimeMillis(), at = time(item, "at");
            if (item.optBoolean("cancelled") || time(item, "deadline_at") <= now) { cancel(id); return; }
            if (read("fired").has(id)) return;
            if (!notifications().areNotificationsEnabled()) { receipt(item, "permission_denied"); return; }
            boolean alarm = "alarm".equals(item.getString("kind"));
            if (alarm && !exactAllowed()) { receipt(item, "permission_denied"); return; }
            PendingIntent trigger = action(id, FIRE);
            if (alarm) alarms().setAlarmClock(new AlarmManager.AlarmClockInfo(Math.max(now + 100, at), open(id)), trigger);
            else alarms().setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, Math.max(now + 100, at), trigger);
            receipt(item, "armed");
        } catch (Exception failure) { error("Une alerte n’a pas pu être armée."); receipt(item, "error"); }
    }
    synchronized void rearm() {
        if (!enabled()) return;
        JSONObject cached = read("alerts");
        for (var ids = cached.keys(); ids.hasNext();) arm(cached.optJSONObject(ids.next()));
        requestSync();
    }
    synchronized void receive(String id, String event) {
        if (!enabled() || id == null) return;
        JSONObject item = read("alerts").optJSONObject(id);
        if (item == null) return;
        if (ACK.equals(event)) {
            cancel(id); receipt(item, "acknowledged"); requestSync(); return;
        }
        try {
            if (time(item, "at") > System.currentTimeMillis() + 1000 || time(item, "deadline_at") <= System.currentTimeMillis()
                || item.optBoolean("cancelled")) return;
            JSONObject fired = read("fired");
            if (fired.has(id)) return;
            if (!notifications().areNotificationsEnabled()) { receipt(item, "permission_denied"); requestSync(); return; }
            boolean alarm = "alarm".equals(item.getString("kind"));
            Notification.Builder builder = new Notification.Builder(context, alarm ? ALARMS : MESSAGES)
                .setSmallIcon(R.drawable.ic_harness).setContentTitle(item.getString("title"))
                .setContentText(item.optString("body")).setStyle(new Notification.BigTextStyle().bigText(item.optString("body")))
                .setVisibility(Notification.VISIBILITY_PRIVATE).setContentIntent(open(id)).setAutoCancel(!alarm)
                .setCategory(alarm ? Notification.CATEGORY_ALARM : Notification.CATEGORY_REMINDER)
                .setTimeoutAfter(alarm ? 60_000 : Math.min(3_600_000, time(item, "deadline_at") - System.currentTimeMillis()));
            if (item.optBoolean("ack_required")) builder.addAction(new Notification.Action.Builder(null,
                alarm ? "Arrêter et acquitter" : "Acquitter", action(id, ACK)).build());
            else if (alarm) builder.addAction(new Notification.Action.Builder(null, "Arrêter", action(id, ACK)).build());
            Notification notification = builder.build();
            if (alarm) notification.flags |= Notification.FLAG_INSISTENT;
            notifications().notify(id, 0, notification);
            fired.put(id, System.currentTimeMillis()); write("fired", fired);
            receipt(item, "fired"); requestSync();
        } catch (Exception failure) { error("Échec d’affichage d’une alerte."); receipt(item, "error"); requestSync(); }
    }
    private JSONObject request(JSONObject credential, String path, JSONObject body) throws Exception {
        if (Thread.currentThread().isInterrupted()) throw new InterruptedException();
        String endpoint = PairingLink.endpoint(credential.getString("endpoint"));
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint + path).openConnection();
        try {
            connection.setInstanceFollowRedirects(false); connection.setConnectTimeout(6000); connection.setReadTimeout(6000);
            connection.setRequestProperty("Authorization", "Bearer " + credential.getString("access_token"));
            if (body != null) {
                connection.setRequestMethod("POST"); connection.setDoOutput(true); connection.setRequestProperty("Content-Type", "application/json");
                try (var out = connection.getOutputStream()) { out.write(body.toString().getBytes(StandardCharsets.UTF_8)); }
            }
            int status = connection.getResponseCode();
            if (status == 401 || status == 403) { disable(); throw new IllegalStateException("Association révoquée ou accès refusé."); }
            if (body != null && status == 422) return new JSONObject(); // Expired/pruned waits cannot be retried forever.
            if (status != 200) throw new IllegalStateException("Serveur indisponible (HTTP " + status + ").");
            try (var in = connection.getInputStream()) {
                java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
                byte[] chunk = new byte[8192]; int count;
                while ((count = in.read(chunk)) != -1) {
                    if (buffer.size() + count > 1_048_576) throw new IllegalStateException("Réponse trop volumineuse.");
                    buffer.write(chunk, 0, count);
                }
                byte[] bytes = buffer.toByteArray();
                return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
            }
        } finally { connection.disconnect(); }
    }
    synchronized String messageQuery() {
        if (!prefs.contains("message_cursor")) return "";
        return "?after=" + prefs.getLong("message_cursor", 0)
            + "&server_instance_id=" + Uri.encode(prefs.getString("message_instance", ""));
    }
    synchronized void consumeMessages(JSONObject result) throws Exception {
        if (!enabled()) return;
        String instance = result.getString("server_instance_id"), status = result.getString("status");
        long cursor = result.getLong("cursor");
        if (cursor < 0 || !("events".equals(status) || "reset".equals(status) || "idle".equals(status)))
            throw new IllegalArgumentException("Invalid notification cursor");
        boolean same = instance.equals(prefs.getString("message_instance", ""));
        long previous = same ? prefs.getLong("message_cursor", -1) : -1;
        if (same && cursor <= previous) return;
        boolean hasMessage = "reset".equals(status) && prefs.contains("message_cursor");
        JSONArray events = result.getJSONArray("events");
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.getJSONObject(i);
            if (event.getLong("sequence") > previous && "message".equals(event.optString("kind"))) hasMessage = true;
        }
        if (hasMessage && !foreground && notifications().areNotificationsEnabled()) {
            notifications().notify("conversation", 0, new Notification.Builder(context, MESSAGES)
                .setSmallIcon(R.drawable.ic_harness).setContentTitle("The Harness")
                .setContentText("reset".equals(status) ? "Connexion reprise ; vérifier les messages récents." : "De nouveaux messages sont disponibles.")
                .setOnlyAlertOnce(true).setContentIntent(open("conversation")).setVisibility(Notification.VISIBILITY_PRIVATE).setAutoCancel(true).build());
        }
        // Commit only after notification posting. A crash may replay; the stable tag replaces it silently.
        if (!prefs.edit().putLong("message_cursor", cursor).putString("message_instance", instance).commit())
            throw new IllegalStateException("Notification cursor not saved");
        if (events.length() > 0 || "reset".equals(status)) requestSync();
    }
    private void syncMessages(JSONObject credential) throws Exception {
        if (PrivateReceiver.enabled(context)) return;
        String query = messageQuery();
        consumeMessages(request(credential, "/remote/v1/notifications/wait" + (query.isEmpty() ? "?" : query + "&") + "timeout=1", null));
    }
    void sync() {
        if (!enabled()) return;
        try {
            JSONObject credential = new CredentialStore(context).load();
            if (credential == null) { disable(); return; }
            JSONObject schedule = request(credential, "/remote/v1/alerts", null);
            if (schedule.optBoolean("truncated") || schedule.getJSONArray("alerts").length() > 512)
                throw new IllegalStateException("Calendrier trop volumineux ; cache conservé.");
            synchronized (this) {
                if (!enabled()) return;
                JSONArray incoming = schedule.getJSONArray("alerts");
                JSONObject next = new JSONObject(), old = read("alerts"), fired = read("fired"), keptFired = new JSONObject();
                for (int i = 0; i < incoming.length(); i++) {
                    JSONObject item = incoming.getJSONObject(i);
                    if (time(item, "deadline_at") > System.currentTimeMillis()) next.put(item.getString("id"), item);
                }
                for (var ids = old.keys(); ids.hasNext();) {
                    String id = ids.next();
                    if (!next.has(id)) cancel(id);
                }
                for (var ids = fired.keys(); ids.hasNext();) {
                    String id = ids.next();
                    if (next.has(id) || fired.optLong(id) > System.currentTimeMillis() - 86_400_000) keptFired.put(id, fired.get(id));
                }
                JSONObject reported = read("reported"), keptReported = new JSONObject();
                for (var keys = reported.keys(); keys.hasNext();) {
                    String key = keys.next();
                    if (reported.optLong(key) > System.currentTimeMillis() - 86_400_000
                        || next.has(key.substring(0, key.lastIndexOf(':')))) keptReported.put(key, reported.get(key));
                }
                write("reported", keptReported);
                write("fired", keptFired); write("alerts", next);
                for (var ids = next.keys(); ids.hasNext();) arm(next.getJSONObject(ids.next()));
                prefs.edit().putLong("last_sync", System.currentTimeMillis()).putString("error", "").commit();
            }
            // Bounded replay: ACK can be sent after an offline interval, never backdated as proof.
            for (int i = 0; i < 8 && enabled(); i++) {
                JSONObject queue;
                String key;
                synchronized (this) {
                    queue = read("receipts"); if (!queue.keys().hasNext()) break;
                    key = queue.keys().next();
                    for (var keys = queue.keys(); keys.hasNext();) {
                        String candidate = keys.next();
                        if (candidate.endsWith(":acknowledged")) { key = candidate; break; }
                    }
                }
                request(credential, "/remote/v1/alerts/receipt", queue.getJSONObject(key));
                synchronized (this) {
                    if (!enabled()) return;
                    queue = read("receipts"); queue.remove(key); write("receipts", queue);
                    JSONObject reported = read("reported"); reported.put(key, System.currentTimeMillis()); write("reported", reported);
                }
            }
            if (enabled()) syncMessages(credential);
        } catch (Exception failure) { error("Synchronisation interrompue ; les alertes déjà chargées restent locales."); }
    }
    String status() {
        return (enabled() ? "Activées" : "Désactivées") + " · notifications " + (notifications().areNotificationsEnabled() ? "autorisées" : "bloquées")
            + " · alarmes exactes " + (exactAllowed() ? "autorisées" : "à autoriser")
            + "\nDernière synchronisation : " + (prefs.getLong("last_sync", 0) == 0 ? "jamais" : new java.util.Date(prefs.getLong("last_sync", 0)))
            + "\n" + read("alerts").length() + " occurrences en cache · " + read("receipts").length() + " reçus en attente\n" + prefs.getString("error", "");
    }
}
