package app.theharness.mobile;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.net.ConnectivityManager;
import android.net.Network;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ThreadLocalRandom;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import org.json.JSONObject;

/** User-enabled private subscription. No embedded VPN, public push provider or permanent wake lock. */
public final class PrivateReceiver extends Service {
    private static final String CHANNEL = "private-receiver-v1", STOP = "private-receiver-stop";
    private static final int NOTIFICATION = 3201;
    private static volatile String state;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private OkHttpClient client;
    private WebSocket socket;
    private int generation, failures;
    private boolean destroyed;
    private ConnectivityManager.NetworkCallback networkCallback;
    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("private-receiver", MODE_PRIVATE);
    }
    static boolean enabled(Context context) { return prefs(context).getBoolean("enabled", false); }
    static String status(Context context) {
        return state != null ? state : prefs(context).getString("status", "Arrêtée");
    }
    static void enable(Context context) {
        NativeAlerts.get(context).enable();
        prefs(context).edit().putBoolean("enabled", true).putString("status", "Démarrage demandé…").commit();
        resume(context);
    }
    static void resume(Context context) {
        if (!enabled(context)) return;
        try { context.startForegroundService(new Intent(context, PrivateReceiver.class)); }
        catch (RuntimeException denied) {
            prefs(context).edit().putString("status", "Démarrage refusé par Android ; rouvrir l’application.").commit();
        }
    }
    static void disable(Context context) {
        prefs(context).edit().putBoolean("enabled", false).putString("status", "Arrêtée").commit();
        context.stopService(new Intent(context, PrivateReceiver.class));
    }
    @Override public void onCreate() {
        super.onCreate();
        NotificationChannel channel = new NotificationChannel(CHANNEL, "Réception privée", NotificationManager.IMPORTANCE_LOW);
        channel.setSound(null, null); channel.enableVibration(false);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        state = "Connexion au serveur privé…";
        if (Build.VERSION.SDK_INT >= 34)
            startForeground(NOTIFICATION, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(NOTIFICATION, notification());
        client = new OkHttpClient.Builder().connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS).pingInterval(60, TimeUnit.SECONDS)
            .followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false).build();
        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network network) { handler.post(() -> reconnectSoon()); }
            @Override public void onLost(Network network) { handler.post(() -> reconnectSoon()); }
        };
        getSystemService(ConnectivityManager.class).registerDefaultNetworkCallback(networkCallback);
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            disable(this); return START_NOT_STICKY;
        }
        if (!enabled(this) || !NativeAlerts.get(this).enabled()) { stopSelf(); return START_NOT_STICKY; }
        if (!getSystemService(NotificationManager.class).areNotificationsEnabled()) {
            failPermanently("Notifications bloquées ; autoriser puis réactiver la réception.");
            return START_NOT_STICKY;
        }
        if (socket == null) { handler.removeCallbacks(reconnect); handler.post(reconnect); }
        return START_STICKY;
    }
    private Notification notification() {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 0, new Intent(this, PrivateReceiver.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, CHANNEL).setSmallIcon(R.drawable.ic_harness)
            .setContentTitle("Réception privée Harness").setContentText(state).setContentIntent(open)
            .setOngoing(true).setOnlyAlertOnce(true).setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(null, "Arrêter", stop).build()).build();
    }
    private void update(String value) {
        state = value;
        getSystemService(NotificationManager.class).notify(NOTIFICATION, notification());
    }
    private final Runnable reconnect = this::connect;
    private void reconnectSoon() {
        if (destroyed || !enabled(this)) return;
        generation++;
        if (socket != null) { socket.cancel(); socket = null; }
        handler.removeCallbacks(reconnect);
        handler.postDelayed(reconnect, 1000);
    }
    private void connect() {
        if (destroyed || !enabled(this)) return;
        final int attempt = ++generation;
        try {
            JSONObject credential = new CredentialStore(this).load();
            if (credential == null) { failPermanently("Association absente ; associer à nouveau."); return; }
            String endpoint = PairingLink.endpoint(credential.getString("endpoint"));
            String url = endpoint.replaceFirst("^https:", "wss:") + "/remote/v1/notifications" + NativeAlerts.get(this).messageQuery();
            update("Connexion au serveur privé…");
            socket = client.newWebSocket(new Request.Builder().url(url)
                .header("Sec-WebSocket-Protocol", "harness-notifications-v1, " + credential.getString("access_token")).build(), new WebSocketListener() {
                @Override public void onOpen(WebSocket webSocket, Response response) {
                    handler.post(() -> {
                        if (attempt != generation || destroyed) return;
                        if (!"harness-notifications-v1".equals(response.header("Sec-WebSocket-Protocol"))) {
                            failPermanently("Protocole de réception incompatible."); return;
                        }
                        update("Connectée au serveur privé");
                        NativeAlerts.get(PrivateReceiver.this).requestSync();
                    });
                }
                @Override public void onMessage(WebSocket webSocket, String text) {
                    handler.post(() -> {
                        if (attempt != generation || destroyed) return;
                        try {
                            if (text.length() > 262144) throw new IllegalArgumentException();
                            NativeAlerts.get(PrivateReceiver.this).consumeMessages(new JSONObject(text));
                            failures = 0;
                            update("Connectée au serveur privé");
                        } catch (Exception invalid) {
                            failPermanently("Flux incompatible ; mise à jour nécessaire.");
                        }
                    });
                }
                @Override public void onClosing(WebSocket webSocket, int code, String reason) {
                    webSocket.close(code, null);
                }
                @Override public void onClosed(WebSocket webSocket, int code, String reason) {
                    handler.post(() -> lost(attempt, code == 1008));
                }
                @Override public void onFailure(WebSocket webSocket, Throwable error, Response response) {
                    boolean denied = response != null && (response.code() == 401 || response.code() == 403);
                    handler.post(() -> lost(attempt, denied));
                }
            });
        } catch (Exception invalid) { failPermanently("Association illisible ; associer à nouveau."); }
    }
    private void lost(int attempt, boolean denied) {
        if (attempt != generation || destroyed) return;
        socket = null;
        if (denied) { failPermanently("Accès refusé ; vérifier l’association et l’accès privé du serveur."); return; }
        update("Hors connexion · reprise automatique (réseau, Tailscale ou serveur)");
        long delay = Math.min(120000L, 3000L << Math.min(failures++, 6));
        handler.removeCallbacks(reconnect);
        handler.postDelayed(reconnect, delay + ThreadLocalRandom.current().nextLong(1000));
    }
    private void failPermanently(String reason) {
        prefs(this).edit().putBoolean("enabled", false).putString("status", reason).commit();
        stopSelf();
    }
    @Override public void onDestroy() {
        destroyed = true; generation++;
        handler.removeCallbacksAndMessages(null);
        if (networkCallback != null) getSystemService(ConnectivityManager.class).unregisterNetworkCallback(networkCallback);
        if (socket != null) socket.cancel();
        if (client != null) { client.dispatcher().executorService().shutdown(); client.connectionPool().evictAll(); }
        state = null;
        if (enabled(this)) prefs(this).edit().putString("status", "Interrompue ; rouvrir l’application si Android ne la relance pas.").commit();
        stopForeground(STOP_FOREGROUND_REMOVE);
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
