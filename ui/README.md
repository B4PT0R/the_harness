# Shared Harness interface

`@the-harness/ui` owns browser-rendered components shared by desktop and future
mobile/Quest hosts. It has no dependency on the desktop entry point.

- `AssistantApp` assembles `AppShell`, `Conversation`, `Composer` and `Settings`.
- `useAssistant` owns the browser-side conversation, history and voice lifecycle;
  Python remains the owner of the canonical conversation.
- `Composer` owns its draft and attachments: typing never updates application
  state. Its `onSubmit({ text, files })` action resolves to `true` on acceptance;
  otherwise the draft is preserved. Sending status remains application-owned.
- `Conversation` and its messages are memoized; keep its callback props stable so
  composer edits never reparse the transcript's Markdown. Unchanged messages also
  stay cached while another message streams. Browser behavior contracts live in
  `tests/general/test_chat_ui.py`; current render-count feedback lives in
  `tests/agentic/test_composer_rendering.py`. Both run with pytest when Node
  dependencies and Playwright Chromium are installed.
- Visual components receive data and actions through props. `Settings` receives
  its request function; it does not choose a desktop backend.
- Hosts can configure `request`, `eventsUrl`, `eventProtocol` and `brandIcon` on
  `AssistantApp`. Requests return parsed API payloads and reject on failure.
- `LocaleProvider` owns UI language independently of the assistant's language.
  `locales.js` is the copy bank: labels, tooltips, accessible names and local error
  fallbacks. Add matching keys in every language. Backend/model/user content is
  preserved verbatim. Language preference is stored locally when possible.
- `theme.css` is the single source for application colors, typography, spacing,
  radii, control sizes and layout dimensions. `style.css` consumes those tokens;
  only structural CSS values and responsive breakpoints are literal.

The desktop entry point renders `<AssistantApp />`. Another host can assemble
individual exported components under `LocaleProvider`; import
`@the-harness/ui/theme.css` and `@the-harness/ui/style.css` when doing so.
Native packaging, remote authentication and device-specific integration belong
to the host, not to these visual components. Mobile/Quest clients are not yet
bundled, but the responsive UI and its components are shared from the outset.
