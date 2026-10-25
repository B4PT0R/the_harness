package app.theharness.mobile;

import android.content.Context;
import android.media.MediaMetadataRetriever;
import android.os.SystemClock;
import java.io.File;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import org.json.JSONArray;
import org.json.JSONObject;

/** Bounded private cache. Fetch only authenticated same-server bucket assets, never at alarm time. */
final class AlarmAudio {
    static final long MAX_FILE = 8 * 1024 * 1024, MAX_CACHE = 64 * 1024 * 1024;
    private final File root;
    AlarmAudio(Context context) {
        root = new File(context.getFilesDir(), "alarm-audio");
        if (!root.isDirectory() && !root.mkdirs()) throw new IllegalStateException("Audio cache unavailable");
    }
    static boolean allowed(String src) {
        return src != null && src.length() <= 2048
            && src.matches("/api/v1/bucket/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*");
    }
    File file(String src) {
        if (!allowed(src)) return null;
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(src.getBytes(StandardCharsets.UTF_8));
            StringBuilder name = new StringBuilder();
            for (byte part : hash) name.append(String.format("%02x", part & 255));
            return new File(root, name + ".audio");
        } catch (Exception failure) { throw new IllegalStateException(failure); }
    }
    File cached(String src) {
        File file = file(src);
        return file != null && file.isFile() && file.length() > 0 ? file : null;
    }
    private long size() {
        long total = 0;
        File[] files = root.listFiles();
        if (files != null) for (File file : files) total += file.length();
        return total;
    }
    static void validate(File file) throws Exception {
        try (MediaMetadataRetriever media = new MediaMetadataRetriever()) {
            media.setDataSource(file.getAbsolutePath());
            long duration = Long.parseLong(media.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            if (duration <= 0 || duration > AlarmPlayback.MAX_RING_MS)
                throw new IllegalArgumentException("Alarm audio must fit within three minutes");
        }
    }
    synchronized boolean prepare(JSONObject credential, String src, long deadline) {
        File destination = file(src);
        if (destination == null) return false;
        if (cached(src) != null) return true;
        if (SystemClock.elapsedRealtime() >= deadline || Thread.currentThread().isInterrupted()) return false;
        File temporary = new File(root, destination.getName() + ".part");
        HttpURLConnection connection = null;
        try {
            long used = size();
            if (used >= MAX_CACHE) return false;
            String endpoint = PairingLink.endpoint(credential.getString("endpoint"));
            connection = (HttpURLConnection) new URL(endpoint + src).openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(6000); connection.setReadTimeout(6000);
            connection.setRequestProperty("Authorization", "Bearer " + credential.getString("access_token"));
            if (connection.getResponseCode() != 200 || connection.getContentLengthLong() > MAX_FILE) return false;
            long total = 0;
            try (var input = connection.getInputStream(); var output = new java.io.FileOutputStream(temporary)) {
                byte[] bytes = new byte[8192]; int count;
                while ((count = input.read(bytes)) != -1) {
                    total += count;
                    if (Thread.currentThread().isInterrupted() || SystemClock.elapsedRealtime() >= deadline
                        || total > MAX_FILE || total + used > MAX_CACHE)
                        throw new IllegalStateException("Audio download interrupted or too large");
                    output.write(bytes, 0, count);
                }
                output.getFD().sync();
            }
            validate(temporary);
            return temporary.renameTo(destination);
        } catch (Exception failure) { return false; }
        finally {
            if (connection != null) connection.disconnect();
            if (temporary.exists()) temporary.delete();
        }
    }
    synchronized void prune(JSONArray alerts) {
        HashSet<String> kept = new HashSet<>();
        for (int i = 0; i < alerts.length(); i++) {
            JSONObject item = alerts.optJSONObject(i);
            if (item == null || item.optBoolean("cancelled")) continue;
            File file = file(item.optString("audio_src", null));
            if (file != null) kept.add(file.getName());
        }
        File[] files = root.listFiles();
        if (files != null) for (File file : files) if (!kept.contains(file.getName())) file.delete();
    }
}
