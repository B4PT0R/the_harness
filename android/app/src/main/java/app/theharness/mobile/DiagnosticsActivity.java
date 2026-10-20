package app.theharness.mobile;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.nio.charset.StandardCharsets;

/** Offline entry point: never starts WebView, the receiver, pairing or audio. */
public final class DiagnosticsActivity extends Activity {
    static final int EXPORT = 13;
    private String pendingExport;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        pendingExport = state == null ? null : state.getString("diagnostic_export");
        render();
    }
    private void render() {
        String report = Diagnostics.report(this);
        LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        box.setPadding(pad, pad, pad, pad);
        TextView text = new TextView(this); text.setText(report); text.setTextIsSelectable(true);
        ScrollView scroll = new ScrollView(this); scroll.addView(text);
        box.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        Button export = new Button(this); export.setText("Exporter le diagnostic…");
        export.setOnClickListener(view -> {
            pendingExport = report;
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                .setType("text/plain").putExtra(Intent.EXTRA_TITLE, "Harness-diagnostic.txt");
            try { startActivityForResult(intent, EXPORT); }
            catch (RuntimeException unavailable) {
                pendingExport = null; feedback("Export indisponible ; vous pouvez sélectionner et copier le texte.");
            }
        }); box.addView(export);
        Button clear = new Button(this); clear.setText("Effacer la trace locale");
        clear.setOnClickListener(view -> { Diagnostics.clear(this); render(); }); box.addView(clear);
        Button close = new Button(this); close.setText("Fermer");
        close.setOnClickListener(view -> finish()); box.addView(close);
        setTitle("Diagnostic local"); setContentView(box);
    }
    private void feedback(String text) { Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("diagnostic_export", pendingExport); super.onSaveInstanceState(state);
    }
    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code != EXPORT) return;
        String report = pendingExport; pendingExport = null;
        if (result != RESULT_OK || data == null || data.getData() == null || report == null) return;
        // A small bounded local report; no network and no automatic upload.
        try (var output = getContentResolver().openOutputStream(data.getData(), "wt")) {
            if (output == null) throw new java.io.IOException();
            output.write(report.getBytes(StandardCharsets.UTF_8));
            feedback("Diagnostic exporté. Aucun envoi automatique.");
        } catch (Exception failure) { feedback("Impossible d’exporter le diagnostic."); }
    }
}
