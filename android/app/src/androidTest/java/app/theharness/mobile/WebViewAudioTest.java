package app.theharness.mobile;

import android.Manifest;
import android.webkit.WebView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

/** Real WebView capture with the production origin/permission handler, no server or VPN. */
@RunWith(AndroidJUnit4.class)
public class WebViewAudioTest {
    @Test public void grantedMicrophoneCanStartAndStopAudioCapture() throws Exception {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        instrumentation.getUiAutomation().grantRuntimePermission(
            instrumentation.getTargetContext().getPackageName(), Manifest.permission.RECORD_AUDIO);
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            // Wait for the asynchronous cookie cleanup/onboarding before replacing its page.
            for (int attempt = 0; attempt < 50; attempt++) {
                AtomicReference<Boolean> ready = new AtomicReference<>(false);
                scenario.onActivity(activity -> ready.set(
                    ((android.view.ViewGroup) activity.findViewById(android.R.id.content)).getChildCount() > 0));
                if (ready.get()) break;
                Thread.sleep(100);
            }
            AtomicReference<WebView> browser = new AtomicReference<>();
            scenario.onActivity(activity -> {
                try {
                    Field endpoint = MainActivity.class.getDeclaredField("endpoint");
                    endpoint.setAccessible(true);
                    endpoint.set(activity, "https://audio-test.example.ts.net");
                    Method open = MainActivity.class.getDeclaredMethod("openConversation");
                    open.setAccessible(true);
                    open.invoke(activity);
                    Field field = MainActivity.class.getDeclaredField("web");
                    field.setAccessible(true);
                    WebView web = (WebView) field.get(activity);
                    browser.set(web);
                    web.stopLoading();
                    web.loadDataWithBaseURL("https://audio-test.example.ts.net/", "<script>"
                        + "navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}})"
                        + ".then(s=>{window.audioResult=s.getAudioTracks()[0].readyState;"
                        + "s.getTracks().forEach(t=>t.stop());window.audioStopped=s.getTracks().every(t=>t.readyState==='ended')})"
                        + ".catch(e=>window.audioResult=e.name+': '+e.message)"
                        + "</script>", "text/html", "UTF-8", null);
                } catch (Exception error) { throw new AssertionError(error); }
            });
            String result = "null";
            for (int attempt = 0; attempt < 150; attempt++) {
                CountDownLatch read = new CountDownLatch(1);
                AtomicReference<String> value = new AtomicReference<>();
                scenario.onActivity(activity -> browser.get().evaluateJavascript(
                    "window.audioResult ? JSON.stringify({capture:window.audioResult,stopped:window.audioStopped}) : null",
                    response -> { value.set(response); read.countDown(); }));
                assertTrue("WebView callback timed out", read.await(5, TimeUnit.SECONDS));
                result = value.get();
                if (!"null".equals(result)) break;
                Thread.sleep(100);
            }
            assertTrue("Microphone capture failed: " + result, result.contains("live"));
            assertTrue("Audio track not released: " + result, result.contains("true"));
            evaluate(scenario, browser.get(), "harnessScreen.postMessage('keep-awake')");
            assertScreen(scenario, browser.get(), true);
            // Same-origin subframes must not control the host screen.
            evaluate(scenario, browser.get(), "window.frameDone=false;"
                + "addEventListener('message',()=>window.frameDone=true,{once:true});"
                + "let f=document.createElement('iframe');f.srcdoc=\"<script>harnessScreen.postMessage('allow-sleep');parent.postMessage('done','*')</script>\";document.body.append(f)");
            for (int attempt = 0; attempt < 50; attempt++) {
                if ("true".equals(evaluate(scenario, browser.get(), "window.frameDone"))) break;
                Thread.sleep(100);
            }
            assertEquals("Subframe did not finish", "true", evaluate(scenario, browser.get(), "window.frameDone"));
            assertScreen(scenario, browser.get(), true);
            evaluate(scenario, browser.get(), "harnessScreen.postMessage('allow-sleep')");
            assertScreen(scenario, browser.get(), false);
            evaluate(scenario, browser.get(), "harnessScreen.postMessage('keep-awake')");
            assertScreen(scenario, browser.get(), true);
            // Navigation releases the flag; another origin gets no bridge at all.
            scenario.onActivity(activity -> browser.get().loadDataWithBaseURL(
                "https://other.example.ts.net/", "<script>window.bridgeAvailable=typeof harnessScreen!=='undefined'</script>",
                "text/html", "UTF-8", null));
            for (int attempt = 0; attempt < 50; attempt++) {
                if ("false".equals(evaluate(scenario, browser.get(), "window.bridgeAvailable"))) break;
                Thread.sleep(100);
            }
            assertEquals("Bridge exposed to another origin", "false", evaluate(scenario, browser.get(), "window.bridgeAvailable"));
            assertScreen(scenario, browser.get(), false);
        }
    }

    private static String evaluate(ActivityScenario<MainActivity> scenario, WebView web, String script) throws Exception {
        CountDownLatch read = new CountDownLatch(1);
        AtomicReference<String> value = new AtomicReference<>();
        scenario.onActivity(activity -> web.evaluateJavascript(script, result -> { value.set(result); read.countDown(); }));
        assertTrue("WebView callback timed out", read.await(5, TimeUnit.SECONDS));
        return value.get();
    }

    private static void assertScreen(ActivityScenario<MainActivity> scenario, WebView web, boolean expected) throws Exception {
        AtomicReference<Boolean> actual = new AtomicReference<>();
        for (int attempt = 0; attempt < 50; attempt++) {
            scenario.onActivity(activity -> actual.set(web.getKeepScreenOn()));
            if (actual.get() == expected) return;
            Thread.sleep(100);
        }
        assertEquals("Unexpected screen-awake state", expected, actual.get());
    }
}
