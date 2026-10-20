# The Harness — Android companion

Thin Android host for the server's shared React UI. The server owns the conversation;
Tailscale is a separate app, not an embedded VPN. Android 8.0+ (API 26).

Version 0.1.3 adds **opt-in native local alerts** in the conversation menu:
**Alertes locales et alarmes**. Allow notifications, then grant Android's special
exact-alarm access for explicitly requested audible alarms. Ordinary reminders
and new-message notifications remain silent; no full-screen takeover or microphone.

Known occurrences are downloaded from the paired server (seven-day horizon, next
occurrence of recurring events), persisted, and scheduled with AlarmManager.
They can fire offline after loading, including after process closure/reboot.
An alarm notification repeats for at most 60 seconds and has a stop action;
ACK alerts have **Arrêter et acquitter** / **Acquitter** actions. An ACK is not task
completion. Offline receipts are queued and their server arrival time is recorded.
Disabling local alerts or disconnecting cancels the local schedule and notifications.

Synchronization occurs on opening/resuming the app and through best-effort Android
jobs (nominally 15 minutes; Android may defer them). **There is no push transport**:
unexpected messages are not guaranteed to arrive promptly, and offline edits or
cancellations cannot alter an already loaded alarm until synchronization. Do not
rely on this development build as a sole critical alarm. Android notification/channel,
exact-alarm and device power settings still apply. The menu shows permissions,
last synchronization, cached occurrences and pending receipts.

See [the implementation and original silent lab study](../docs/mobile-alerts.md).

## Build

Install Java 17 or 21 and Android SDK 34, then:

```sh
cd android
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME="$HOME/Android/Sdk" \
  ./gradlew :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

APK: `app/build/outputs/apk/debug/app-debug.apk`. This is a development build,
not a Play Store release. Install it manually or with `adb install -r ...`.
Install updates over the existing app (same signing key); do not uninstall if you
want to retain its pairing.

For silent native tests, use **only an emulator started with `-no-audio`**, never
a physical handset. Select `app.theharness.mobile.NativeAlertsTest` using
`-Pandroid.testInstrumentationRunnerArguments.class=app.theharness.mobile.NativeAlertsTest`
with `:app:connectedDebugAndroidTest`. These tests post only a silent notification,
queue an offline ACK, and arm/cancel a next-day alarm without firing it. Grant
exact-alarm access on the disposable emulator to include that scheduling test.

The separate `WebViewAudioTest` **uses the microphone**; do not run it as part of a
silent alert validation. With a consented emulator/device, the full instrumentation suite
checks actual WebView microphone capture and track release using the production
permission handler and an isolated test page, without a server or Tailscale.
Both `RECORD_AUDIO` (runtime permission) and `MODIFY_AUDIO_SETTINGS` (install-time
permission for Chromium audio routing) are needed. This test does not validate
the complete Realtime call or physical microphone/speaker quality.

## Pair

1. Install Tailscale on the phone; connect it and the server to the same tailnet.
2. In the desktop UI: **Réglages → Appareils et accès distant**.
3. Explicitly enable private access. This may configure `tailscale serve --bg`
   for this server's loopback port. Tailscale HTTPS and Serve permissions must
   already be available. Other proxies are never replaced; Funnel is refused.
4. Create a short-lived QR code, then scan it in the Android app (or paste/open
   the `theharness://pair` link). Confirm the displayed server address.
5. Chat, attach files and use voice through the shared UI. Voice still requires
   microphone permission and server-side Realtime configuration.

The one-time pairing secret is exchanged natively over HTTPS. The durable bearer
is AES-GCM encrypted using Android Keystore and never passed to JavaScript.
A Secure, HttpOnly, SameSite=Strict session cookie authenticates the WebView.
Only the exact paired `.ts.net` origin is allowed. Mobile credentials cannot
administer server settings, pair devices, restart or reset the server, or use
host-local file routes. The authorized conversation and shared bucket remain
accessible, including conversation content produced by host tools.

Revoke a device from desktop Settings. The phone's disconnect action only erases
its saved credential; it does not revoke the server-side registration. Disabling
private access rejects remote requests and closes current remote sockets, but
leaves Tailscale Serve configuration in place to avoid altering unrelated system
settings. It does not erase paired devices. Re-enabling restores their access.

The server retains its listener port after an opted-in restart. No Serve command
runs during startup, builds or tests. Test first-time pairing, reconnect, files
and microphone on a real phone before relying on it away from the server.

During a Realtime connection or call, the foreground app keeps its screen awake.
Stopping the call restores normal screen timeout. This does not provide background
calling. A main-frame-only message channel, restricted to the paired origin,
controls this screen flag; it never exposes credentials. Instrumentation also
checks screen-flag release, navigation and iframe isolation.
