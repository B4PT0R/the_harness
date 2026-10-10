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
window.requests = [];
class Socket {
  static OPEN = 1;
  readyState = 1;
  constructor() { window.socket = this; queueMicrotask(() => this.onopen?.()); }
  close() { this.readyState = 3; }
}
window.WebSocket = Socket;
window.emit = (event) => window.socket.onmessage({ data: JSON.stringify(event) });
const text = '# Message\\n\\nSome **rich text**, a [link](https://example.org), and $x^2$.\\n\\n- First\\n- Second\\n\\n```python\\nprint(42)\\n```';
const items = Array.from({ length: 80 }, (_, id) => ({
  type: 'message', id: String(id), role: id % 2 ? 'assistant' : 'user', content: [{ text }],
}));
async function request(path, options = {}) {
  window.requests.push({ path, body: options.body });
  if (path === 'plugins') return { plugins: [{ name: 'chat', running: true }] };
  if (path === 'status') return { foreground_active: false, foreground_pending: 0 };
  if (path.startsWith('session')) return { turns: [{ items }], has_more: true, next_before: 'older' };
  if (path === 'agent/prompt' && window.failSend) throw new Error('Send failed');
  return {};
}
createRoot(document.getElementById('root')).render(<AssistantApp request={request} />);
"""
    build = """
import { build } from 'esbuild';
import { readFile } from 'node:fs/promises';
await build({
  stdin: { contents: ENTRY, resolveDir: process.cwd(), loader: 'jsx' },
  bundle: true, outfile: OUTPUT, loader: { '.woff': 'dataurl', '.woff2': 'dataurl', '.ttf': 'dataurl' },
  plugins: [{ name: 'count-markdown', setup(build) {
    build.onLoad({ filter: /Markdown\\.jsx$/ }, async ({ path }) => ({
      contents: (await readFile(path, 'utf8')).replace(
        'export function Markdown({ children }) {',
        'export function Markdown({ children }) { window.markdownRenders++;'),
      loader: 'jsx',
    }));
  }}],
});
""".replace("ENTRY", json.dumps(entry)).replace("OUTPUT", json.dumps(str(output / "app.js")))
    subprocess.run(["node", "--input-type=module", "-e", build], cwd=ROOT, check=True, capture_output=True)
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
        page = browser.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def respond(route):
            name = route.request.url.rsplit("/", 1)[-1]
            if name in {"app.js", "app.css"}:
                route.fulfill(path=str(bundle / name), content_type="text/javascript" if name.endswith("js") else "text/css")
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
