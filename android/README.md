# The Harness — Android companion

Thin Android host for the server's shared React UI. The server owns the conversation;
Tailscale is a separate app, not an embedded VPN. Android 8.0+ (API 26).

Version 0.1.5 fixes audible alarms with an explicit, bounded audio loop.
Version 0.1.4 added an **opt-in private notification receiver**, alongside the
native local alerts introduced in 0.1.3. Local alerts are configured in the menu:
**Alertes locales et alarmes**. Allow notifications, then grant Android's special
exact-alarm access for explicitly requested audible alarms. Ordinary reminders
and new-message notifications remain silent; no full-screen takeover or microphone.

Known occurrences are downloaded from the paired server (seven-day horizon, next
occurrence of recurring events), persisted, and scheduled with AlarmManager.
They can fire offline after loading, including after process closure/reboot.
Audible alarms use a short-lived `mediaPlayback` foreground service and loop the
system alarm ringtone until stopped/acknowledged, with a **three-minute maximum per
occurrence**, measured against elapsed time. Audio is independent of notification
sound repetition: the new alarm notification channel is silent, while playback uses
the alarm audio stream and audio focus. No volume override or full-screen activity.
The CPU is kept awake only during playback; audio/focus/resources are released on
stop, cancellation, disable, playback error or service destruction. The service does
not restart an interrupted alarm. Overlapping alarms share one audio player, retain
separate deadlines and expose the most recent ringing occurrence's stop action.
ACK alerts have **Arrêter et acquitter** / **Acquitter** actions in the notification
(expand it if needed); there is no separate alarm screen. An ACK is not task completion.
At the audio cap, `auto_stopped` is queued, not an ACK; a silent actionable notification
remains until the occurrence deadline. Offline receipts are queued and their server
arrival time is recorded. Disabling local alerts or disconnecting cancels local
schedules, notifications and playback. Blocking notifications/the alarm channel
prevents starting playback; device alarm-volume and audio policies still apply.

Synchronization occurs on opening/resuming the app and through best-effort Android
jobs (nominally 15 minutes; Android may defer them). Without the private receiver,
unexpected messages depend on this synchronization. Offline edits or cancellations
cannot alter an already loaded alarm until synchronization. Do not
rely on this development build as a sole critical alarm. Android notification/channel,
exact-alarm and device power settings still apply. The menu shows permissions,
last synchronization, cached occurrences and pending receipts.

## Private reception (0.1.4)

After pairing, choose **Réception privée → Activer** in the conversation menu.
Notification permission is required. This also enables local alert synchronization;
exact-alarm access remains a separate explicit permission. A native foreground
service keeps a direct authenticated WebSocket to the paired Harness over Tailscale.
There is no shared relay, Firebase project, embedded VPN or additional account.
The persistent silent notification shows connection state and an **Arrêter** action.
Stopping reception leaves local alerts enabled; disabling local alerts or
disconnecting also stops reception.

Reconnect uses bounded exponential backoff and network-change callbacks, keeping
the service visible while offline. A private, atomic server journal retains the last
256 metadata-only signals across server restarts. The saved native cursor avoids
duplicate display and replays missed signals on reconnect; an expired cursor causes
a generic catch-up notice, not a replay of old audible alarms. Notification signals
never contain conversation text, and the pairing bearer stays native-only.
Remote revocation/denial stops reception rather than retrying indefinitely.

**This is best-effort reception, not an Android wakeup guarantee.** Android, Samsung
battery restrictions, force-stop, Tailscale availability and server outages can delay
or interrupt delivery. The battery-settings button only opens Android settings;
it does not silently grant an exemption. Restart after reboot/update is attempted
only when opted in and may require reopening the app. Preloaded local alarms remain
the separate offline path for known times. No indefinite wake lock is held.

Validation: debug APK build, unit tests and lint; nine silent API-35 instrumentation
tests including opt-in, ongoing status, offline persistence, stop action and cursor
replay/deduplication. Server-side tests cover authentication, private/mobile scope,
replay, revocation and durable restart. **No live Tailscale connection, Samsung
standby, battery endurance or real-phone installation was tested for this version.**
The new server route requires activation of the updated backend separately.

See [the implementation and original silent lab study](../docs/mobile-alerts.md).

## Alarm-loop validation (0.1.5)

Debug build, unit tests and lint pass. Fourteen API-35 alert instrumentation tests
pass on a `-no-audio` emulator, including five playback tests and a real elapsed
three-minute cutoff. The expanded notification action was visually inspected.
The APK signer matches 0.1.4, so an in-place update can retain pairing.
**Looping and sound stopping after ACK have not yet been tested on the real phone.**
No backend restart or pairing change is needed for this Android-only update.

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

For native alert tests, use **only an emulator started with `-no-audio`**, never
a physical handset. Select both alert classes using
`-Pandroid.testInstrumentationRunnerArguments.class=app.theharness.mobile.NativeAlertsTest,app.theharness.mobile.AlarmPlaybackTest`
with `:app:connectedDebugAndroidTest`. These tests post notifications, exercise the
receiver offline, queue an offline ACK, and fire real local alarms on the muted
emulator. Playback checks cover end-of-track looping, stop/ACK, disable, overlapping
occurrences, cancellation and the full three-minute cap (allow about four minutes).
The receiver fixture temporarily disables emulator Wi-Fi/data and restores them
afterward. Grant exact-alarm access on the disposable emulator to include scheduling.

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
