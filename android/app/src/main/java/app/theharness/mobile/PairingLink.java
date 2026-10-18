package app.theharness.mobile;

import java.net.URI;
import java.net.URLDecoder;
import java.util.HashMap;
import java.util.Map;

/** Parse untrusted QR/deep links without network activity or Android dependencies. */
final class PairingLink {
    final String endpoint, pairingId, secret;
    private PairingLink(String endpoint, String pairingId, String secret) {
        this.endpoint = endpoint; this.pairingId = pairingId; this.secret = secret;
    }
    static String endpoint(String value) {
        URI uri = URI.create(value);
        String host = uri.getHost();
        if (!"https".equals(uri.getScheme()) || host == null || !host.matches("[a-z0-9-]+(?:\\.[a-z0-9-]+)+\\.ts\\.net")
                || uri.getUserInfo() != null || uri.getPort() != -1 || uri.getQuery() != null || uri.getFragment() != null
                || !(uri.getPath().isEmpty() || uri.getPath().equals("/"))) {
            throw new IllegalArgumentException("Une adresse HTTPS Tailscale (*.ts.net) est nécessaire.");
        }
        return "https://" + host;
    }
    private static String decode(String value) {
        try { return URLDecoder.decode(value, "UTF-8"); }
        catch (java.io.UnsupportedEncodingException error) { throw new AssertionError(error); }
    }
    static PairingLink parse(String value) {
        if (value == null || value.length() > 4096) throw new IllegalArgumentException("Lien d’association invalide.");
        URI uri = URI.create(value.trim());
        if (!"theharness".equals(uri.getScheme()) || !"pair".equals(uri.getHost()) || uri.getPort() != -1
                || uri.getUserInfo() != null || uri.getFragment() != null || !uri.getPath().isEmpty() || uri.getRawQuery() == null) {
            throw new IllegalArgumentException("Lien d’association invalide.");
        }
        Map<String, String> fields = new HashMap<>();
        for (String part : uri.getRawQuery().split("&")) {
            String[] pair = part.split("=", 2);
            if (pair.length != 2) throw new IllegalArgumentException("Lien d’association incomplet.");
            String key = decode(pair[0]);
            if (fields.put(key, decode(pair[1])) != null)
                throw new IllegalArgumentException("Lien d’association ambigu.");
        }
        if (fields.size() != 4 || !"1".equals(fields.get("v"))
                || !fields.getOrDefault("pairing_id", "").matches("[A-Za-z0-9_-]{1,128}")
                || !fields.getOrDefault("secret", "").matches("[A-Za-z0-9_-]{1,256}")) {
            throw new IllegalArgumentException("Lien d’association invalide ou version incompatible.");
        }
        return new PairingLink(endpoint(fields.getOrDefault("endpoint", "")), fields.get("pairing_id"), fields.get("secret"));
    }
}
