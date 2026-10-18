package app.theharness.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import androidx.webkit.WebMessageCompat;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Thin native host: origin-scoped screen control, no credential bridge or embedded VPN. */
public final class MainActivity extends Activity {
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private CredentialStore credentials;
    private WebView web;
    private String endpoint;
    private PermissionRequest audioRequest;
    private ValueCallback<Uri[]> fileCallback;
    private static final int AUDIO_PERMISSION = 10, FILE_PICKER = 11;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        credentials = new CredentialStore(this);
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().removeSessionCookies(removed -> {
            if (isFinishing() || isDestroyed()) return;
            if (getIntent().getData() != null) offerPairing(getIntent().getData().toString());
            else restore();
        });
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        if (intent.getData() != null) offerPairing(intent.getData().toString());
    }
    private void restore() {
        try {
            JSONObject saved = credentials.load();
            if (saved == null) onboarding("");
            else connect(PairingLink.endpoint(saved.getString("endpoint")), saved.getString("access_token"));
        } catch (Exception error) { onboarding("L’association enregistrée est illisible. Associez à nouveau cet appareil."); }
    }
    private LinearLayout layout() {
        LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        box.setPadding(pad, pad, pad, pad); box.setBackgroundColor(Color.rgb(25, 27, 30));
        android.widget.ScrollView scroll = new android.widget.ScrollView(this);
        scroll.setFillViewport(true); scroll.addView(box); setContentView(scroll); return box;
    }
    private void text(LinearLayout box, String value, int size) {
        TextView label = new TextView(this); label.setText(value); label.setTextSize(size);
        label.setTextColor(Color.rgb(230, 234, 240)); label.setPadding(0, 12, 0, 12); box.addView(label);
    }
    private Button button(LinearLayout box, String label, View.OnClickListener action) {
        Button button = new Button(this); button.setText(label); button.setOnClickListener(action); box.addView(button); return button;
    }
    private void onboarding(String error) {
        destroyWeb(); endpoint = null;
        LinearLayout box = layout();
        text(box, "The Harness", 28);
        text(box, "Votre conversation, sur votre serveur privé.", 18);
        text(box, "1. Installez Tailscale sur ce téléphone et connectez-le au même réseau que l’ordinateur.\n\n2. Sur l’ordinateur : Réglages → Appareils et accès distant → Activer → Créer un code d’association.", 16);
        if (!error.isEmpty()) text(box, error, 16);
        button(box, "Ouvrir Tailscale", view -> {
            Intent launch = getPackageManager().getLaunchIntentForPackage("com.tailscale.ipn");
            startActivity(launch != null ? launch : new Intent(Intent.ACTION_VIEW, Uri.parse("https://tailscale.com/download/android")));
        });
        button(box, "Scanner le QR code", view -> new IntentIntegrator(this)
            .setDesiredBarcodeFormats(IntentIntegrator.QR_CODE).setPrompt("Scannez le code d’association The Harness")
            .setBeepEnabled(false).setOrientationLocked(false).initiateScan());
        EditText link = new EditText(this); link.setHint("Ou collez le lien theharness://pair…");
        link.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        box.addView(link);
        button(box, "Associer cet appareil", view -> offerPairing(link.getText().toString()));
        invalidateOptionsMenu();
    }
    private void offerPairing(String raw) {
        final PairingLink pairing;
        try { pairing = PairingLink.parse(raw); }
        catch (RuntimeException error) { onboarding(error.getMessage()); return; }
        if (web == null) onboarding("");
        new AlertDialog.Builder(this).setTitle("Associer cet appareil ?")
            .setMessage("Ce serveur pourra lire vos messages et recevoir vos fichiers et votre voix :\n\n" + pairing.endpoint + "\n\nVérifiez qu’il s’agit bien de votre ordinateur.")
            .setNegativeButton("Annuler", (dialog, which) -> { if (endpoint == null) restore(); })
            .setPositiveButton("Associer", (dialog, which) -> claim(pairing)).show();
    }
    private static String readUtf8(java.io.InputStream input) throws java.io.IOException {
        var output = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        for (int count; (count = input.read(buffer)) != -1;) {
            if (output.size() + count > 65536) throw new java.io.IOException("Réponse du serveur trop longue");
            output.write(buffer, 0, count);
        }
        return output.toString("UTF-8");
    }
    private void claim(PairingLink pairing) {
        destroyWeb();
        LinearLayout box = layout(); text(box, "Association en cours…", 22);
        network.execute(() -> {
            HttpURLConnection connection = null;
            try {
                JSONObject request = new JSONObject().put("version", 1).put("pairing_id", pairing.pairingId)
                    .put("secret", pairing.secret).put("platform", "android")
                    .put("device_name", android.os.Build.MANUFACTURER + " " + android.os.Build.MODEL);
                connection = (HttpURLConnection) new URL(pairing.endpoint + "/remote/v1/pairings/claim").openConnection();
                connection.setInstanceFollowRedirects(false); connection.setConnectTimeout(15000); connection.setReadTimeout(15000);
                connection.setRequestMethod("POST"); connection.setDoOutput(true); connection.setRequestProperty("Content-Type", "application/json");
                try (var output = connection.getOutputStream()) { output.write(request.toString().getBytes(StandardCharsets.UTF_8)); }
                if (connection.getResponseCode() != 200) throw new IllegalStateException("Association refusée ou expirée. Créez un nouveau code sur l’ordinateur.");
                JSONObject response;
                try (var input = connection.getInputStream()) { response = new JSONObject(readUtf8(input)); }
                if (!pairing.endpoint.equals(PairingLink.endpoint(response.getString("endpoint")))) throw new IllegalStateException("Le serveur a changé d’adresse.");
                JSONObject saved = new JSONObject().put("endpoint", pairing.endpoint).put("access_token", response.getString("access_token"));
                credentials.save(saved);
                runOnUiThread(() -> { if (!isDestroyed()) connect(pairing.endpoint, saved.optString("access_token")); });
            } catch (Exception error) {
                runOnUiThread(() -> { if (!isDestroyed()) onboarding("Impossible de s’associer. Vérifiez Tailscale et la validité du code.\n" + error.getMessage()); });
            } finally { if (connection != null) connection.disconnect(); }
        });
    }
    private boolean sameOrigin(Uri uri) {
        return endpoint != null && "https".equals(uri.getScheme()) && uri.getUserInfo() == null
            && uri.getPort() == -1 && endpoint.equals("https://" + uri.getHost());
    }
    private void connect(String origin, String token) {
        if (!token.matches("[A-Za-z0-9_-]+")) { onboarding("Identifiant d’association invalide."); return; }
        endpoint = origin;
        // Session-only, HttpOnly: shared React code never receives the durable bearer.
        CookieManager.getInstance().setCookie(endpoint, "harness_mobile=" + token + "; Path=/; Secure; HttpOnly; SameSite=Strict", accepted -> {
            if (!accepted) { onboarding("Le stockage sécurisé de la session est indisponible."); return; }
            openConversation();
        });
    }
    @SuppressWarnings("SetJavaScriptEnabled")
    private void openConversation() {
        destroyWeb();
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        Button menu = new Button(this); menu.setText("The Harness  ·  Connexion privée  ·  ⋮");
        menu.setOnClickListener(view -> new AlertDialog.Builder(this).setItems(new String[]{"Actualiser", "Se déconnecter de ce téléphone"}, (dialog, item) -> {
            if (item == 0) web.reload(); else confirmDisconnect();
        }).show()); root.addView(menu);
        web = new WebView(this); root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1)); setContentView(root);
        WebSettings settings = web.getSettings(); settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false); settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW); settings.setMediaPlaybackRequiresUserGesture(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "harnessScreen", Collections.singleton(endpoint),
                (view, message, origin, mainFrame, reply) -> {
                    if (view != web || !mainFrame || !sameOrigin(origin)
                        || message.getType() != WebMessageCompat.TYPE_STRING) return;
                    String state = message.getData();
                    if ("keep-awake".equals(state)) view.setKeepScreenOn(true);
                    else if ("allow-sleep".equals(state)) view.setKeepScreenOn(false);
                });
        }
        web.setWebViewClient(new WebViewClient() {
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                view.setKeepScreenOn(false);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (sameOrigin(request.getUrl())) return false;
                if (request.isForMainFrame() && request.hasGesture() && "https".equals(request.getUrl().getScheme()))
                    startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl()));
                return true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) connectionError("Serveur inaccessible. Vérifiez Tailscale et que l’ordinateur est allumé.");
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame() && (response.getStatusCode() == 401 || response.getStatusCode() == 403))
                    connectionError("Accès désactivé ou appareil révoqué. Vérifiez les réglages sur l’ordinateur.");
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    if (!sameOrigin(request.getOrigin()) || !java.util.Arrays.asList(request.getResources()).contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) { request.deny(); return; }
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
                        request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
                    else { if (audioRequest != null) audioRequest.deny(); audioRequest = request; requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_PERMISSION); }
                });
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request) { if (audioRequest == request) audioRequest = null; }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
                picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                startActivityForResult(picker, FILE_PICKER); return true;
            }
        });
        web.setDownloadListener((url, agent, disposition, type, length) -> {
            Uri uri = Uri.parse(url); if (!sameOrigin(uri)) return;
            String name = android.webkit.URLUtil.guessFileName(url, disposition, type);
            new AlertDialog.Builder(this).setTitle("Télécharger ce fichier ?").setMessage(name)
                .setNegativeButton("Annuler", null).setPositiveButton("Télécharger", (dialog, which) -> {
                    DownloadManager.Request request = new DownloadManager.Request(uri);
                    request.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));
                    request.setTitle(name).setMimeType(type).setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                        .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                    try { ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(request); }
                    catch (RuntimeException error) { Toast.makeText(MainActivity.this, "Téléchargement indisponible : " + error.getMessage(), Toast.LENGTH_LONG).show(); }
                }).show();
        });
        web.loadUrl(endpoint + "/ui/"); invalidateOptionsMenu();
    }
    private void connectionError(String message) {
        if (isFinishing() || isDestroyed()) return;
        destroyWeb(); LinearLayout box = layout(); text(box, "Connexion interrompue", 24); text(box, message, 16);
        button(box, "Réessayer", view -> restore()); button(box, "Associer à nouveau", view -> onboarding(""));
    }
    private void confirmDisconnect() {
        new AlertDialog.Builder(this).setTitle("Déconnecter ce téléphone ?")
            .setMessage("L’identifiant enregistré sera effacé. Révoquez aussi cet appareil dans les réglages de l’ordinateur.")
            .setNegativeButton("Annuler", null).setPositiveButton("Déconnecter", (dialog, which) -> {
                credentials.clear(); CookieManager.getInstance().removeAllCookies(removed -> onboarding(""));
                CookieManager.getInstance().flush();
            }).show();
    }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(code, permissions, grants);
        if (code == AUDIO_PERMISSION && audioRequest != null) {
            if (grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED && sameOrigin(audioRequest.getOrigin())) audioRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else audioRequest.deny(); audioRequest = null;
        }
    }
    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code == FILE_PICKER) {
            if (fileCallback != null) {
                Uri[] files = null;
                if (result == RESULT_OK && data != null) {
                    if (data.getClipData() != null) {
                        files = new Uri[data.getClipData().getItemCount()];
                        for (int i = 0; i < files.length; i++) files[i] = data.getClipData().getItemAt(i).getUri();
                    } else if (data.getData() != null) files = new Uri[]{data.getData()};
                }
                fileCallback.onReceiveValue(files); fileCallback = null;
            }
            return;
        }
        IntentResult scan = IntentIntegrator.parseActivityResult(code, result, data);
        if (scan != null && scan.getContents() != null) offerPairing(scan.getContents());
    }
    private void destroyWeb() {
        if (audioRequest != null) { audioRequest.deny(); audioRequest = null; }
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (web != null) { web.setKeepScreenOn(false); web.stopLoading(); web.destroy(); web = null; }
    }
    @Override public void onBackPressed() { if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onDestroy() { destroyWeb(); network.shutdownNow(); super.onDestroy(); }
}
