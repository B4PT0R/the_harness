package app.theharness.mobile;

import android.content.Context;
import android.os.Build;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import static org.junit.Assume.assumeTrue;

/** Synthetic exceptions only: no production crash, microphone, network or alarm. */
@RunWith(AndroidJUnit4.class)
public class DiagnosticsTest {
    private Context context;
    @Before public void setup() {
        assumeTrue(Build.FINGERPRINT.contains("generic") || Build.MODEL.contains("sdk_gphone"));
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        Diagnostics.clear(context);
    }
    @After public void cleanup() { if (context != null) Diagnostics.clear(context); }
    @Test public void handlerPersistsSymbolsButNeverExceptionMessagesAndDelegates() throws Exception {
        var cause = new IllegalArgumentException("PRIVATE_TOKEN https://private.example chat secret");
        var error = new IllegalStateException("PRIVATE_TOKEN", cause);
        final boolean[] delegated = {false};
        Diagnostics.handler(context, (thread, failure) -> {
            assertSame(error, failure); delegated[0] = true;
        }).uncaughtException(Thread.currentThread(), error);
        assertTrue(delegated[0]);
        String report = Diagnostics.report(context);
        assertTrue(report.contains("java.lang.IllegalStateException"));
        assertTrue(report.contains("java.lang.IllegalArgumentException"));
        assertTrue(report.contains("handlerPersistsSymbolsButNeverExceptionMessagesAndDelegates"));
        assertFalse(report.contains("PRIVATE_TOKEN"));
        assertFalse(report.contains("private.example"));
        assertFalse(report.contains("chat secret"));
        assertTrue(report.contains("Version: " + BuildConfig.VERSION_NAME));
    }
    @Test public void reportSurvivesNewContextAndClearRemovesTrace() throws Exception {
        Diagnostics.saveCrash(context, new UnsupportedOperationException("not retained"));
        var fresh = context.createPackageContext(context.getPackageName(), 0);
        assertTrue(Diagnostics.report(fresh).contains("java.lang.UnsupportedOperationException"));
        Diagnostics.clear(context);
        assertFalse(Diagnostics.report(fresh).contains("java.lang.UnsupportedOperationException"));
        assertTrue(Diagnostics.report(fresh).contains("Aucune depuis"));
    }
    @Test public void cyclicCausesAndDeepStackAreBounded() {
        var first = new RuntimeException("hidden");
        var second = new RuntimeException("hidden");
        first.initCause(second); second.initCause(first);
        var frames = new StackTraceElement[500];
        java.util.Arrays.fill(frames, new StackTraceElement("SafeClass", "safeMethod", "PRIVATE_FILENAME", 12));
        first.setStackTrace(frames); second.setStackTrace(frames);
        String stack = Diagnostics.stack(first);
        assertEquals(80, stack.lines().filter(line -> line.startsWith("  at ")).count());
        assertFalse(stack.contains("PRIVATE_FILENAME")); assertFalse(stack.contains("hidden"));
    }
    @Test public void installedApplicationUsesCrashCollector() {
        assertTrue(context.getApplicationContext() instanceof Diagnostics);
    }
    @Test public void offlineActivityExportsWithUserPickerAndDoesNotEnableReceiver() throws Exception {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        NativeAlerts.get(context).disable(); 
        var activity = (DiagnosticsActivity) instrumentation.startActivitySync(
            new android.content.Intent(context, DiagnosticsActivity.class).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK));
        var file = new java.io.File(context.getCacheDir(), "diagnostic-test.txt");
        var filter = new android.content.IntentFilter(android.content.Intent.ACTION_CREATE_DOCUMENT);
        filter.addCategory(android.content.Intent.CATEGORY_OPENABLE); filter.addDataType("text/plain");
        var monitor = instrumentation.addMonitor(filter,
            new android.app.Instrumentation.ActivityResult(android.app.Activity.RESULT_OK,
                new android.content.Intent().setData(android.net.Uri.fromFile(file))), true);
        try {
            instrumentation.runOnMainSync(() -> {
                var box = (android.widget.LinearLayout) ((android.view.ViewGroup) activity.findViewById(android.R.id.content)).getChildAt(0);
                assertTrue(((android.widget.TextView) ((android.widget.ScrollView) box.getChildAt(0)).getChildAt(0))
                    .getText().toString().contains("The Harness — diagnostic local"));
                ((android.widget.Button) box.getChildAt(1)).performClick();
            });
            instrumentation.waitForIdleSync();
            assertEquals(1, monitor.getHits());
            String exported = new String(java.nio.file.Files.readAllBytes(file.toPath()), java.nio.charset.StandardCharsets.UTF_8);
            assertTrue(exported.contains("Version: " + BuildConfig.VERSION_NAME));
            assertFalse(NativeAlerts.get(context).enabled());
            assertFalse(PrivateReceiver.enabled(context));
        } finally {
            instrumentation.removeMonitor(monitor); file.delete();
            instrumentation.runOnMainSync(activity::finish);
        }
    }

}
