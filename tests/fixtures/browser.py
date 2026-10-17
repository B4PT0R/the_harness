"""Isolated browser fixtures shared by durable UI contracts and performance feedback."""
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
def page(bundle, request):
    errors = []
    image_delay = request.getfixturevalue("image_delay") if "image_delay" in request.fixturenames else 0
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
                if image_delay:
                    page.wait_for_timeout(image_delay)
                route.fulfill(path=str(bundle / name), content_type="image/png")
            elif name == "assistant.svg":
                route.fulfill(path=str(ROOT / "desktop/public/assistant.svg"), content_type="image/svg+xml")
            else:
                route.fulfill(body='<div id="root"></div><link rel="stylesheet" href="/app.css"><script src="/app.js"></script>', content_type="text/html")

        page.route("**/*", respond)
        page.goto("https://harness.test/")
        page.wait_for_function("document.querySelectorAll('.message').length === 80 && !document.querySelector('textarea').disabled")
        # Font layout must settle before a test establishes its scroll position.
        page.evaluate("document.fonts.ready")
        try:
            yield page
        finally:
            browser.close()
    assert not errors
