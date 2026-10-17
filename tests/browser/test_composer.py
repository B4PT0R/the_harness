"""Real-browser regressions for the composer, with no backend or user data."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    if not shutil.which("node") or not (ROOT / "node_modules/esbuild").exists():
        pytest.skip("Install frontend dependencies to run browser tests")
    output = tmp_path_factory.mktemp("composer")
    entry = """
import React from 'react';
import { createRoot } from 'react-dom/client';
import { AssistantApp } from './ui/src/AssistantApp.jsx';
window.markdownRenders = 0;
window.assistantRenders = 0;
window.requests = [];
class Socket {
  static OPEN = 1;
  readyState = 1;
  constructor() { window.socket = this; queueMicrotask(() => this.onopen?.()); }
  close() { this.readyState = 3; }
}
window.WebSocket = Socket;
window.emit = (event) => window.socket.onmessage({ data: JSON.stringify(event) });
window.publishArtifact = (item) => {
  const saved = JSON.parse(localStorage.getItem('test-artifacts') || '[]');
  localStorage.setItem('test-artifacts', JSON.stringify([...saved.filter(value => value.id !== item.id), item]));
  window.emit({type: 'command_event', event: {type: 'agent.response_item.added', item}});
};
const text = '# Message\\n\\nSome **rich text**, a [link](https://example.org), and $x^2$.\\n\\n- First\\n- Second\\n\\n```python\\nprint(42)\\n```';
const items = Array.from({ length: 80 }, (_, id) => ({
  type: 'message', id: String(id), role: id % 2 ? 'assistant' : 'user', content: [{ text }],
}));
async function request(path, options = {}) {
  const body = options.body instanceof FormData
    ? Object.fromEntries(['id', 'prompt'].map(key => [key, options.body.get(key)]).concat([
      ['files', options.body.getAll('files').map(file => file.name)],
    ])) : options.body;
  window.requests.push({ path, body });
  if (path.startsWith('agent/') && window.holdSend)
    await new Promise(resolve => { window.releaseSend = resolve; });
  if (path === 'config' && options.method === 'PATCH' && window.failConfigSave) throw new Error('Config save failed');
  if (path === 'local-files/settings') {
    if (options.method === 'PUT' && window.failEditorSave) throw new Error('Editor save failed');
    if (options.method === 'PUT') window.fileEditor = body.editor;
    return { editor: window.fileEditor || 'system' };
  }
  if (path === 'local-files/open' && window.failFileOpen) throw new Error('File no longer exists');
  if (path === 'browser/open-external' && window.failBrowserOpen) throw new Error('Integrated browser unavailable');
  if (path === 'config') return { config: { model: 'test-model' } };
  if (path === 'surfaces') return { surfaces: [{ name: 'main', active: 'active', candidate: 'candidate', previous: 'previous', preview_route: '/preview/main', building: !!window.building }] };
  if (path === 'surfaces/main/cancel') { window.building = false; return { cancelled: true }; }
  if (path === 'plugins') return { plugins: [{ name: 'chat', running: true }] };
  if (path === 'status') return { foreground_active: false, foreground_pending: 0 };
  if (path.startsWith('session')) return { turns: [{ items: [...items, ...JSON.parse(localStorage.getItem('test-artifacts') || '[]')] }], has_more: true, next_before: 'older' };
  if (path.startsWith('agent/') && window.failSend) throw new Error('Send failed');
  return {};
}
const renderers = { weather: ({payload}) => <p>{payload.city} · {payload.temperature} °C</p>,
  broken: () => { throw new Error('Widget failed'); } };
createRoot(document.getElementById('root'), {onCaughtError: () => {}}).render(<AssistantApp request={request} artifactRenderers={renderers} />);
"""
    build = """
import { build } from 'esbuild';
import { readFile } from 'node:fs/promises';
await build({
  stdin: { contents: ENTRY, resolveDir: process.cwd(), loader: 'jsx' },
  bundle: true, outfile: OUTPUT, loader: { '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl' },
  plugins: [{ name: 'count-markdown', setup(build) {
    build.onLoad({ filter: /(Markdown|AssistantApp)\\.jsx$/ }, async ({ path }) => ({
      contents: (await readFile(path, 'utf8'))
        .replace('export function Markdown({ children }) {',
          'export function Markdown({ children }) { window.markdownRenders++;')
        .replace('  const [settingsOpen, setSettingsOpen] = useState(false);',
          '  window.assistantRenders++; const [settingsOpen, setSettingsOpen] = useState(false);'),
      loader: 'jsx',
    }));
  }}],
});
""".replace("ENTRY", json.dumps(entry)).replace("OUTPUT", json.dumps(str(output / "app.js")))
    subprocess.run(["node", "--input-type=module", "-e", build], cwd=ROOT, check=True, capture_output=True)
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (640, 200), "#153b39")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((30, 30, 610, 170), radius=16, fill="#23544f")
    draw.line([(55, 145), (150, 115), (250, 130), (365, 65), (480, 85), (585, 45)], fill="#a7e4d2", width=4)
    image.save(output / "artifact-fixture.png")
    return output


@pytest.fixture
def page(bundle):
    errors = []
    with sync_playwright() as playwright:
        executables = list((ROOT / ".playwright-browsers").glob("chromium-*/chrome-linux*/chrome"))
        options = {"executable_path": str(executables[-1])} if executables else {}
        try:
            browser = playwright.chromium.launch(**options)
        except Exception as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip("Install Playwright Chromium to run browser tests")
            raise
        page = browser.new_page(locale="fr-FR")
        page.on("pageerror", lambda error: errors.append(str(error)))

        def respond(route):
            name = route.request.url.rsplit("/", 1)[-1]
            if name in {"app.js", "app.css"}:
                route.fulfill(path=str(bundle / name), content_type="text/javascript" if name.endswith("js") else "text/css")
            elif name == "artifact-fixture.png":
                route.fulfill(path=str(bundle / name), content_type="image/png")
            else:
                route.fulfill(body='<div id="root"></div><link rel="stylesheet" href="/app.css"><script src="/app.js"></script>', content_type="text/html")

        page.route("**/*", respond)
        page.goto("https://harness.test/")
        page.wait_for_function("document.querySelectorAll('.message').length === 80 && !document.querySelector('textarea').disabled")
        try:
            yield page
        finally:
            browser.close()
    assert not errors


def test_repeated_backspace_does_not_render_history(page):
    field = page.locator("textarea")
    field.fill("a" * 2000)
    field.press("End")
    before = page.evaluate("window.markdownRenders")
    parent_before = page.evaluate("window.assistantRenders")
    page.evaluate("window.repeatKeys = []; document.querySelector('textarea').addEventListener('keydown', event => window.repeatKeys.push(event.repeat))")
    durations = []
    try:
        for _ in range(40):
            start = page.evaluate("performance.now()")
            page.keyboard.down("Backspace")
            durations.append(page.evaluate("performance.now()") - start)
    finally:
        page.keyboard.up("Backspace")
    assert page.evaluate("window.repeatKeys.filter(Boolean).length") == 39
    assert len(field.input_value()) == 1960
    renders = page.evaluate("window.markdownRenders") - before
    print(f"Backspace: mean {sum(durations) / len(durations):.1f} ms, max {max(durations):.1f} ms, history renders {renders}")
    assert renders == 0
    assert page.evaluate("window.assistantRenders") == parent_before
    page.evaluate("window.emit({ type: 'command_event', event: { type: 'response.output_text.delta', item_id: 'stream', sequence_number: 1, delta: 'Streaming response' } })")
    page.wait_for_function("document.querySelectorAll('.message').length === 81")
    assert page.locator(".message").last.inner_text() == "Streaming response"
    assert page.evaluate("window.markdownRenders") == before + 1
    page.evaluate("window.emit({ type: 'command_event', event: { type: 'response.output_text.delta', item_id: 'stream', sequence_number: 2, delta: ' updated' } })")
    page.wait_for_function("document.querySelector('.message:last-child').textContent.includes('updated')")
    assert page.evaluate("window.markdownRenders") == before + 2
    assert field.input_value() == "a" * 1960


@pytest.mark.parametrize("width", [1280, 390])
def test_composer_resize_submission_and_failure(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    field = page.locator("textarea")
    field.fill("long line " * 600)
    page.wait_for_function("document.querySelector('textarea').style.overflowY === 'auto'")
    assert field.evaluate("el => el.getBoundingClientRect().height") <= 231
    field.fill("short draft")
    page.wait_for_function("document.querySelector('textarea').getBoundingClientRect().height < 100")
    page.evaluate("window.failSend = true")
    field.press("Enter")
    page.wait_for_function("document.querySelector('[role=alert]')?.textContent.includes('Send failed')")
    assert field.input_value() == "short draft"
    page.evaluate("window.failSend = false")
    field.press("Shift+Enter")
    assert "\n" in field.input_value()
    field.press("Enter")
    page.wait_for_function("document.querySelector('textarea').value === ''")
    assert page.evaluate("window.requests.filter(r => r.path === 'agent/prompt').length") == 2
    assert field.evaluate("el => el.getBoundingClientRect().height") < 100
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_attachments_and_draft_survive_updates_and_failed_send(page):
    field = page.locator("textarea")
    field.fill("With attachment")
    page.locator("input[type=file]").set_input_files({
        "name": "note.txt", "mimeType": "text/plain", "buffer": b"test attachment",
    })
    page.evaluate("window.emit({ type: 'worker_status', foreground_active: false, local_input_tokens: 40, context_token_limit: 200 })")
    page.wait_for_function("document.querySelector('.context-gauge text').textContent === '20'")
    assert field.input_value() == "With attachment"
    assert page.locator(".attachments button").inner_text() == "note.txt ×"
    page.evaluate("window.holdSend = true; window.failSend = true")
    field.press("Enter")
    page.wait_for_function("typeof window.releaseSend === 'function'")
    assert field.is_disabled()
    # Even a second synchronous/programmatic submit cannot duplicate the request.
    page.evaluate("document.querySelector('.composer').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))")
    assert page.evaluate("window.requests.filter(r => r.path === 'agent/attachments').length") == 1
    page.evaluate("window.releaseSend()")
    page.wait_for_function("document.querySelector('[role=alert]')?.textContent.includes('Send failed')")
    assert field.input_value() == "With attachment"
    assert page.locator(".attachments button").count() == 1
    page.evaluate("window.holdSend = false; window.failSend = false")
    field.press("Enter")
    page.wait_for_function("document.querySelector('textarea').value === ''")
    assert page.locator(".attachments button").count() == 0
    body = page.evaluate("window.requests.filter(r => r.path === 'agent/attachments').at(-1).body")
    assert body["prompt"] == "With attachment"
    assert body["files"] == ["note.txt"]
    assert body["id"]


def test_voice_completion_clears_caption_without_replacing_canonical_history(page):
    before = page.locator(".message").count()
    page.evaluate("window.emit({ type: 'realtime_event', call_id: 'call', event: { type: 'input_transcript.added', item: { text: 'Partial voice' } } })")
    page.wait_for_function("document.querySelectorAll('.message').length === 81")
    assert "Partial voice" in page.locator(".message").last.inner_text()
    page.evaluate("window.emit({ type: 'realtime_event', call_id: 'call', event: { type: 'turn.done', turn: { role: 'user', transcript: '' } } })")
    page.wait_for_function("document.querySelectorAll('.message').length === 80")
    assert page.locator(".message").count() == before


def test_worker_recovery_clears_only_the_disconnect_error(page):
    page.evaluate("window.emit({ type: 'worker_exited', returncode: 1, stderr: [] })")
    page.get_by_role("alert").filter(has_text="Le worker s’est déconnecté.").wait_for()
    page.evaluate("window.emit({ type: 'worker_status', foreground_active: false, foreground_pending: 0 })")
    page.get_by_role("alert").wait_for(state="detached")
    page.evaluate("window.failSend = true")
    page.locator("textarea").fill("Keep this unsent draft")
    page.locator("textarea").press("Enter")
    page.get_by_role("alert").filter(has_text="Send failed").wait_for()
    page.evaluate("window.emit({ type: 'worker_status', foreground_active: false, foreground_pending: 0 })")
    assert page.get_by_role("alert").inner_text().startswith("Send failed")
    assert page.locator("textarea").input_value() == "Keep this unsent draft"


@pytest.mark.parametrize("width", [1280, 390])
def test_interface_release_confirmations_and_external_build(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.locator("button[aria-label='Réglages']").click()
    page.locator(".settings-nav").get_by_role("button", name="Interface", exact=True).click()
    panel = page.locator(".surface-settings")
    panel.get_by_role("button", name="Publier", exact=True).click()
    assert panel.locator(".surface-confirmation").is_visible()
    assert not page.evaluate("window.requests.some(r => r.path === 'surfaces/main/publish')")
    panel.get_by_role("button", name="Annuler", exact=True).click()
    assert panel.locator(".surface-confirmation").count() == 0
    panel.get_by_role("button", name="Publier", exact=True).click()
    panel.get_by_role("button", name="Confirmer", exact=True).click()
    page.wait_for_function("window.requests.some(r => r.path === 'surfaces/main/publish')")
    assert page.evaluate("window.requests.find(r => r.path === 'surfaces/main/publish').body") == {"release": "candidate"}
    page.evaluate("window.building = true")
    panel.get_by_role("button", name="Actualiser", exact=True).click()
    panel.get_by_role("button", name="Annuler la compilation", exact=True).wait_for()
    assert panel.get_by_role("button", name="Construire un aperçu", exact=True).is_disabled()
    panel.get_by_role("button", name="Annuler la compilation", exact=True).click()
    page.wait_for_function("window.requests.some(r => r.path === 'surfaces/main/cancel')")
    page.wait_for_function("!window.building")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1280, 390])
def test_fullscreen_settings_preserve_drafts_and_keyboard_navigation(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    draft = page.locator(".composer textarea")
    draft.fill("Un brouillon à conserver")
    trigger = page.get_by_role("button", name="Réglages", exact=True)
    trigger.click()
    settings = page.locator(".settings")
    assert page.locator(".workspace > main").is_hidden()
    assert settings.evaluate("el => el.getBoundingClientRect().width") == width
    nav = settings.get_by_role("navigation", name="Sections des réglages")
    nav.get_by_role("button", name="Conversation", exact=True).click()
    instructions = settings.get_by_role("textbox", name="Instructions personnelles")
    instructions.fill("Une instruction conservée entre les sections")
    nav.get_by_role("button", name="Avancé", exact=True).click()
    config = settings.locator("#config")
    assert "Une instruction conservée" in config.input_value()
    nav.get_by_role("button", name="Conversation", exact=True).click()
    assert instructions.input_value() == "Une instruction conservée entre les sections"
    nav.get_by_role("button", name="Données", exact=True).click()
    settings.get_by_role("button", name="Réinitialiser la session", exact=True).click()
    page.locator("dialog").wait_for(state="visible")
    page.keyboard.press("Escape")
    assert page.locator("dialog").is_hidden()
    assert settings.is_visible()
    nav.get_by_role("button", name="Général", exact=True).click()
    assert nav.get_by_role("button", name="Général", exact=True).get_attribute("aria-current") == "page"
    page.keyboard.press("Tab")
    assert settings.evaluate("el => el.contains(document.activeElement)")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.keyboard.press("Escape")
    assert settings.count() == 0
    assert draft.input_value() == "Un brouillon à conserver"
    assert trigger.evaluate("el => el === document.activeElement")


def test_settings_save_validation_and_visible_errors(page):
    page.get_by_role("button", name="Réglages", exact=True).click()
    settings = page.locator(".settings")
    settings.locator(".settings-nav").get_by_role("button", name="Avancé", exact=True).click()
    config = settings.locator("#config")
    save = settings.get_by_role("button", name="Enregistrer", exact=True)
    config.fill("[]")
    assert save.is_disabled()
    assert settings.get_by_role("alert").is_visible()
    config.fill('{"model": "changed-model"}')
    page.evaluate("window.failConfigSave = true")
    save.click()
    settings.get_by_role("alert").filter(has_text="Config save failed").wait_for()
    assert settings.is_visible()
    page.evaluate("window.failConfigSave = false")
    save.click()
    page.wait_for_function("document.querySelector('.settings-footer').textContent.includes('Réglages enregistrés.')")
    assert settings.is_visible()
    assert save.is_disabled()


def test_chat_paths_open_locally_and_errors_are_visible(page):
    text = "Fichier `/home/baptiste/Documents/a b.md`, dossier /home/baptiste/Documents et [image](file:///tmp/image.png).\n\n```sh\ncat /tmp/a.md\n```\n\n[site](https://example.org)"
    page.evaluate("text => window.emit({ type: 'command_event', event: { type: 'response.output_text.delta', item_id: 'paths', sequence_number: 1, delta: text } })", text)
    message = page.locator(".message").last
    message.locator(".resource-link").first.wait_for()
    assert message.locator(".resource-link").count() == 4
    assert message.locator("pre a").count() == 0
    message.get_by_role("link", name="/home/baptiste/Documents/a b.md").click()
    request = page.evaluate("window.requests.filter(r => r.path === 'local-files/open').at(-1)")
    assert request["body"] == {"path": "/home/baptiste/Documents/a b.md"}
    assert page.url == "https://harness.test/"
    page.evaluate("window.failFileOpen = true")
    message.get_by_role("link", name="image", exact=True).click()
    message.get_by_role("alert").filter(has_text="File no longer exists").wait_for()
    site = message.get_by_role("link", name="site", exact=True)
    site.click()
    request = page.evaluate("window.requests.filter(r => r.path === 'browser/open-external').at(-1)")
    assert request["body"] == {"url": "https://example.org"}
    assert page.url == "https://harness.test/"
    site.click(button="middle")
    assert page.evaluate("window.requests.filter(r => r.path === 'browser/open-external').length") == 2
    page.evaluate("window.failBrowserOpen = true")
    site.click()
    message.get_by_role("alert").filter(has_text="Integrated browser unavailable").wait_for()


def test_file_editor_preference_is_immediate_and_failed_save_keeps_previous_value(page):
    page.get_by_role("button", name="Réglages", exact=True).click()
    editor = page.get_by_label("Éditeur des fichiers texte", exact=True)
    editor.wait_for()
    page.wait_for_function("!document.querySelector('#file-editor').disabled")
    assert editor.input_value() == "system"
    page.evaluate("window.failEditorSave = true")
    editor.select_option("vscode")
    page.get_by_role("alert").filter(has_text="Editor save failed").wait_for()
    assert editor.input_value() == "system"
    page.evaluate("window.failEditorSave = false")
    editor.select_option("vscode")
    page.wait_for_function("document.querySelector('#file-editor').value === 'vscode'")
    assert page.evaluate("window.fileEditor") == "vscode"
    assert page.locator(".settings-footer").get_by_role("button", name="Enregistrer", exact=True).is_disabled()


def test_artifact_rendering_replay_and_widget_fallback(page):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.evaluate("const el = document.querySelector('.conversation'); el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(100)
    page.screenshot(path="/tmp/harness-artifacts-before.png")
    artifact = {"type": "artifact", "id": "plot", "kind": "image", "payload": {
        "src": "/artifact-fixture.png", "title": "Résultat de l’analyse", "description": "Un aperçu conservé dans la conversation.",
    }}
    page.evaluate("item => window.publishArtifact(item)", artifact)
    page.locator(".artifact img").wait_for()
    page.wait_for_function("document.querySelector('.artifact img').naturalWidth === 640")
    page.wait_for_function("(() => {const el = document.querySelector('.conversation'); return el.scrollHeight - el.scrollTop - el.clientHeight < 5;})()")
    page.screenshot(path="/tmp/harness-artifacts-after.png")
    page.evaluate("item => window.publishArtifact(item)", artifact)
    assert page.locator(".artifact").count() == 1
    page.reload()
    page.wait_for_function("document.querySelector('.artifact img')?.naturalWidth === 640")
    assert page.locator(".artifact").count() == 1
    page.evaluate("item => window.publishArtifact(item)", {
        "type": "artifact", "id": "weather", "kind": "weather",
        "payload": {"city": "Paris", "temperature": 18, "title": "Météo"},
    })
    page.get_by_text("Paris · 18 °C", exact=True).wait_for()
    for kind in ["unknown", "broken"]:
        page.evaluate("item => window.publishArtifact(item)", {
            "type": "artifact", "id": kind, "kind": kind, "payload": {"value": 42},
        })
        page.locator(f".artifact-{kind} summary").click()
        assert '"value": 42' in page.locator(f".artifact-{kind} pre").inner_text()
    page.evaluate("item => window.publishArtifact(item)", {
        "type": "artifact", "id": "file", "kind": "file",
        "payload": {"src": "/api/v1/artifacts/report.txt", "name": "rapport.txt"},
    })
    assert page.get_by_role("link", name="Télécharger rapport.txt").get_attribute("href") == "/api/v1/artifacts/report.txt"
    page.get_by_role("textbox", name="Message", exact=True).fill("Le chat fonctionne toujours")


def test_provider_artifacts_replace_then_disappear_without_replay(page):
    for index in [1, 2]:
        page.evaluate("index => window.emit({type: 'command_event', event: {type: 'agent.provider_artifacts.updated', items: ["
                      "{type: 'artifact', id: 'screen-' + index, kind: 'image', payload: {src: '/artifact-fixture.png', title: 'Vue ' + index}}]}})", index)
        page.get_by_role("heading", name=f"Vue {index}", exact=True).wait_for()
        assert page.locator(".artifact").count() == 1
    page.evaluate("window.emit({type: 'command_event', event: {type: 'agent.turn.end'}})")
    page.wait_for_function("document.querySelectorAll('.artifact').length === 0")
    page.reload()
    page.wait_for_function("document.querySelectorAll('.message').length === 80")
    assert page.locator(".artifact").count() == 0
