from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

import pytest


@pytest.mark.parametrize("width", [1280, 390])
def test_voice_and_delegated_answers_stay_distinct_live_and_after_reload(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    backend = {"id": "backend-answer", "type": "message", "role": "assistant",
               "kind": "realtime_delegation", "content": [{"text": "Résultat détaillé du backend."}]}
    spoken = {"id": "voice-answer", "type": "message", "role": "assistant",
              "kind": "realtime", "content": [{"text": "Voici la réponse prononcée."}]}
    page.evaluate("window.emit({type:'realtime_event',call_id:'voice-call',event:{type:'voice.transcript.updated',role:'assistant',text:'Voici la réponse prononcée.'}})")
    page.get_by_text("Voice agent", exact=False).wait_for()
    page.evaluate("window.emit({type:'command_event',event:{type:'agent.text.delta',channel:'output',kind:'realtime_delegation',item_id:'backend-answer',sequence:1,delta:'Résultat détaillé du backend.'}})")
    disclosure = page.locator(".text-agent-output")
    assert disclosure.count() == 1
    assert disclosure.locator("summary").inner_text() == "Text agent"
    assert page.get_by_text("Résultat détaillé du backend.", exact=True).is_hidden()
    assert page.get_by_text("Voici la réponse prononcée.", exact=True).is_visible()
    for item in (backend, spoken):
        page.evaluate("item => window.emit({type:'command_event',event:{type:'agent.response_item.added',item}})", item)
    page.evaluate("window.emit({type:'realtime_event',call_id:'voice-call',event:{type:'voice.turn.completed',role:'assistant'}})")
    disclosure.locator("summary").click()
    assert page.get_by_text("Résultat détaillé du backend.", exact=True).is_visible()
    assert page.locator(".message-source").get_by_text("Voice agent", exact=True).count() == 1
    page.evaluate("items => localStorage.setItem('test-artifacts',JSON.stringify(items))", [backend, spoken])
    page.reload()
    page.locator(".text-agent-output summary").wait_for()
    assert page.get_by_text("Résultat détaillé du backend.", exact=True).is_hidden()
    assert page.get_by_text("Voici la réponse prononcée.", exact=True).is_visible()
    assert page.locator(".message-source").get_by_text("Voice agent", exact=True).count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1280, 390])
def test_registry_reset_requires_confirmation_and_targets_only_registry(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Données", exact=True).click()
    page.get_by_role("button", name="Réinitialiser le registre", exact=True).click()
    dialog = page.get_by_role("dialog")
    assert "La conversation, la mémoire, les fichiers et les réglages sont conservés" in dialog.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    dialog.get_by_role("button", name="Annuler", exact=True).click()
    assert not page.evaluate("window.requests.some(r => r.path === 'registry')")
    page.get_by_role("button", name="Réinitialiser le registre", exact=True).click()
    dialog.get_by_role("button", name="Réinitialiser", exact=True).click()
    page.get_by_text("Réinitialisation effectuée.", exact=True).wait_for()
    assert page.evaluate("window.requests.filter(r => r.path === 'registry').length") == 1


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


@pytest.mark.parametrize("width", [1280, 390])
@pytest.mark.parametrize("via_button", [False, True])
@pytest.mark.parametrize("fails", [False, True])
def test_composer_recovers_focus_after_submission(page, width, via_button, fails):
    page.set_viewport_size({"width": width, "height": 800})
    field = page.locator(".composer textarea")
    # Initial mount and background updates must not grab the keyboard.
    assert not field.evaluate("el => el === document.activeElement")
    field.fill("First message")
    page.evaluate("fails => { window.holdSend = true; window.failSend = fails; }", fails)
    if via_button:
        page.get_by_role("button", name="Envoyer", exact=True).click()
    else:
        field.press("Enter")
    page.wait_for_function("typeof window.releaseSend === 'function'")
    assert field.is_disabled()
    page.evaluate("window.releaseSend()")
    page.wait_for_function("document.activeElement === document.querySelector('.composer textarea') && !document.activeElement.disabled")
    assert field.input_value() == ("First message" if fails else "")
    # Real keyboard input, not fill()/press() which would focus the field for us.
    page.keyboard.type(" next")
    assert field.input_value() == ("First message next" if fails else " next")


def test_composer_does_not_steal_focus_when_user_opens_settings_during_send(page):
    field = page.locator(".composer textarea")
    field.fill("Delayed message")
    page.evaluate("window.holdSend = true")
    field.press("Enter")
    page.wait_for_function("typeof window.releaseSend === 'function'")
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Conversation", exact=True).click()
    instructions = page.get_by_role("textbox", name="Instructions personnelles")
    instructions.fill("Keep my focus here")
    page.evaluate("window.releaseSend()")
    page.wait_for_function("!document.querySelector('.composer textarea').disabled")
    assert instructions.evaluate("el => el === document.activeElement")
    page.get_by_role("button", name="Retour à la conversation", exact=True).click()
    assert not field.evaluate("el => el === document.activeElement")


def test_attachments_and_draft_survive_updates_and_failed_send(page):
    field = page.locator("textarea")
    field.fill("With attachment")
    page.locator("input[type=file]").set_input_files({
        "name": "note.txt", "mimeType": "text/plain", "buffer": b"test attachment",
    })
    page.evaluate("window.emit({ type: 'worker_status', foreground_active: false, local_input_tokens: 40, context_token_limit: 200 })")
    page.wait_for_function("document.querySelector('.context-gauge text').textContent === '20%'")
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
    page.evaluate("window.emit({ type: 'realtime_event', call_id: 'call', event: { type: 'voice.transcript.updated', role: 'user', text: 'Partial voice' } })")
    page.wait_for_function("document.querySelectorAll('.message').length === 81")
    assert "Partial voice" in page.locator(".message").last.inner_text()
    page.evaluate("window.emit({ type: 'realtime_event', call_id: 'call', event: { type: 'voice.turn.completed', role: 'user', transcript: '' } })")
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
    assert nav.get_by_role("button", name="Interface", exact=True).count() == 0
    assert not page.evaluate("window.requests.some(r => r.path.startsWith('surfaces'))")
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
    page.locator('dialog[aria-labelledby="reset-title"]').wait_for(state="visible")
    page.keyboard.press("Escape")
    assert page.locator('dialog[aria-labelledby="reset-title"]').is_hidden()
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


@pytest.mark.parametrize("width", [1280, 390])
def test_voice_settings_save_only_on_request_and_preserve_advanced_fields(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Voix", exact=True).click()
    section = page.locator("#settings-voice")
    voice = section.get_by_role("combobox", name="Voix utilisée")
    assert voice.input_value() == "maple"
    voice.select_option("breeze")
    section.get_by_role("textbox", name="Modèle vocal", exact=True).fill("custom-realtime-model")
    section.get_by_role("checkbox").uncheck()
    assert "prochain appel" in section.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not page.evaluate("window.requests.some(r => r.path === 'config' && r.body)")
    page.get_by_role("button", name="Avancé", exact=True).click()
    config = json.loads(page.locator("#config").input_value())
    assert config["model"] == "test-model"
    assert config["realtime"] == {
        "model": "custom-realtime-model", "voice": "breeze",
        "delegation_ack_filler": False, "max_initial_items": 50,
    }
    # Custom configured voices are retained rather than silently replaced.
    config["realtime"]["voice"] = "account-specific-voice"
    page.locator("#config").fill(json.dumps(config))
    page.get_by_role("button", name="Voix", exact=True).click()
    assert voice.input_value() == "account-specific-voice"
    save = page.get_by_role("button", name="Enregistrer", exact=True)
    save.click()
    page.get_by_text("Réglages enregistrés.", exact=True).wait_for()
    assert save.is_disabled()
    assert page.evaluate("window.requests.filter(r => r.path === 'config' && r.body).map(r => r.body)") == [config]
    assert not page.evaluate("window.requests.some(r => r.path.startsWith('realtime/'))")


def test_voice_settings_disable_fields_when_configuration_is_missing(page):
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Avancé", exact=True).click()
    page.locator("#config").fill('{"model":"test-model"}')
    page.get_by_role("button", name="Voix", exact=True).click()
    section = page.locator("#settings-voice")
    assert "indisponible" in section.inner_text()
    assert section.get_by_role("combobox").is_disabled()
    assert section.get_by_role("textbox").is_disabled()
    assert section.get_by_role("checkbox").is_disabled()


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
    page.evaluate("text => window.emit({ type: 'command_event', event: { type: 'agent.text.delta', item_id: 'paths', channel: 'output', sequence: 1, delta: text } })", text)
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


@pytest.mark.parametrize("image_delay", [0, 250])
def test_artifact_rendering_replay_and_widget_fallback(page, image_delay):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.evaluate("const el = document.querySelector('.conversation'); el.scrollTop = el.scrollHeight")
    page.wait_for_function("(() => {const el = document.querySelector('.conversation'); return el.scrollHeight - el.scrollTop - el.clientHeight < 5;})()")
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
        "payload": {"src": "/api/v1/bucket/report.txt", "name": "rapport.txt"},
    })
    assert page.get_by_role("link", name="Télécharger rapport.txt").get_attribute("href") == "/api/v1/bucket/report.txt"
    page.get_by_role("textbox", name="Message", exact=True).fill("Le chat fonctionne toujours")


@pytest.mark.parametrize("width", [1280, 390])
@pytest.mark.parametrize("dimensions", [(1024, 1536), (1536, 1024), (32, 32)])
def test_image_artifact_hides_prompt_and_uses_four_fifths_width(page, width, dimensions):
    from io import BytesIO
    from PIL import Image

    page.set_viewport_size({"width": width, "height": 900})
    data = BytesIO()
    Image.new("RGB", dimensions, "ivory").save(data, format="PNG")
    page.route("**/sized-image.png", lambda route: route.fulfill(body=data.getvalue(), content_type="image/png"))
    page.evaluate("item => window.publishArtifact(item)", {
        "type": "artifact", "id": "sized-image", "kind": "image",
        "payload": {"src": "/sized-image.png", "title": "Encre de Chine", "description": "Long generation prompt"},
    })
    image = page.locator(".artifact-image img")
    image.scroll_into_view_if_needed()
    page.wait_for_function("document.querySelector('.artifact-image img')?.naturalWidth > 0")
    assert page.get_by_text("Long generation prompt", exact=True).count() == 0
    metrics = image.evaluate("""el => {
        const image = el.getBoundingClientRect(), parent = el.closest('.artifact');
        const style = getComputedStyle(parent), frame = parent.getBoundingClientRect();
        return {width: image.width, height: image.height,
            available: parent.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
            offset: image.left + image.width / 2 - frame.left - frame.width / 2};
    }""")
    assert metrics["width"] == pytest.approx(metrics["available"] * .8, abs=1)
    assert metrics["height"] == pytest.approx(metrics["width"] * dimensions[1] / dimensions[0], abs=1)
    assert abs(metrics["offset"]) < 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.fixture
def download_page(page, bundle):
    # Chromium downloads bypass route.fulfill: give them a real local endpoint.
    handler = partial(SimpleHTTPRequestHandler, directory=str(bundle))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        page.goto(f"http://127.0.0.1:{server.server_port}/")
        page.wait_for_function("document.querySelectorAll('.message').length === 80")
        yield page
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("width", [1280, 390])
def test_image_artifact_fullscreen_keyboard_and_download(download_page, tmp_path, width):
    page = download_page
    page.set_viewport_size({"width": width, "height": 900})
    page.evaluate("window.publishArtifact({type:'artifact', id:'viewer', kind:'image', payload:"
                  "{src:'/artifact-fixture.png', name:'graphique.png', title:'Mon graphique'}})")
    preview = page.locator(".artifact-image-preview")
    preview.scroll_into_view_if_needed()
    preview.focus()
    page.keyboard.press("Enter")
    viewer = page.get_by_role("dialog", name="Mon graphique")
    viewer.wait_for()
    page.wait_for_function("document.querySelector('dialog img')?.naturalWidth === 640")
    assert viewer.bounding_box() == {"x": 0, "y": 0, "width": width, "height": 900}
    image = viewer.locator("img").bounding_box()
    assert image["x"] >= 0 and image["y"] >= 0
    assert image["x"] + image["width"] <= width
    assert image["y"] + image["height"] <= 900
    assert viewer.locator("img").evaluate("el => getComputedStyle(el).objectFit") == "contain"
    assert viewer.get_by_role("button", name="Fermer").evaluate("el => el === document.activeElement")
    page.keyboard.press("Shift+Tab")
    assert viewer.get_by_role("link", name="Télécharger l’image").evaluate("el => el === document.activeElement")
    with page.expect_download() as event:
        viewer.get_by_role("link", name="Télécharger l’image").click()
    download = event.value
    assert download.suggested_filename == "graphique.png"
    download.save_as(tmp_path / "graphique.png")
    assert (tmp_path / "graphique.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    page.screenshot(path=f"/tmp/harness-image-fullscreen-{width}.png")
    page.keyboard.press("Escape")
    assert page.get_by_role("dialog").count() == 0
    assert preview.evaluate("el => el === document.activeElement")
    page.get_by_role("button", name="Afficher en plein écran", exact=True).last.click()
    page.get_by_role("dialog").get_by_role("button", name="Fermer").click()
    assert page.get_by_role("dialog").count() == 0
    preview.click()
    page.locator(".artifact-image-stage").click(position={"x": 1, "y": 1})
    assert page.get_by_role("dialog").count() == 0
    with page.expect_download() as event:
        page.get_by_role("link", name="Télécharger l’image").click()
    assert event.value.suggested_filename == "graphique.png"
    page.reload()
    page.locator(".artifact-image-preview").wait_for()
    assert page.get_by_role("dialog").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("source", ["javascript:alert(1)", "/missing-image.png"])
def test_unavailable_image_has_no_viewer_or_download(page, source):
    page.route("**/missing-image.png", lambda route: route.fulfill(status=404))
    page.evaluate("src => window.publishArtifact({type:'artifact',id:'missing',kind:'image',payload:{src}})", source)
    page.get_by_role("status").filter(has_text="Ce contenu est indisponible.").wait_for()
    assert page.locator(".artifact-image button, .artifact-image a, .artifact-image dialog").count() == 0


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


@pytest.mark.parametrize("image_delay", [0, 250])
def test_late_artifact_does_not_pull_a_reader_out_of_history(page, image_delay):
    page.evaluate("document.fonts.ready")
    page.evaluate("""() => {
      const el = document.querySelector('.conversation');
      el.scrollTop = el.scrollHeight - el.clientHeight - 500;
    }""")
    page.wait_for_timeout(100)
    before = page.locator('.conversation').evaluate('(el) => el.scrollTop')
    page.evaluate("window.publishArtifact({type:'artifact', id:'late-image', kind:'image', payload:{src:'/artifact-fixture.png'}})")
    page.wait_for_function("document.querySelector('.artifact img')?.naturalWidth === 640")
    after = page.locator('.conversation').evaluate('(el) => el.scrollTop')
    assert abs(after - before) < 2
    page.evaluate("const el=document.querySelector('.conversation'); el.scrollTop=el.scrollHeight")
    page.wait_for_timeout(100)
    page.evaluate("window.publishArtifact({type:'artifact', id:'next-view', kind:'weather', payload:{city:'Paris',temperature:18}})")
    page.wait_for_function("(() => {const el=document.querySelector('.conversation'); return el.scrollHeight-el.scrollTop-el.clientHeight<5;})()")


@pytest.mark.parametrize('width', [1280, 390])
@pytest.mark.parametrize('preview_client', [False, True])
def test_preview_drafts_and_settings_do_not_write_to_the_principal(page, width, preview_client):
    page.set_viewport_size({'width': width, 'height': 900})
    if preview_client:
        page.get_by_text('Aperçu · lecture seule', exact=True).wait_for()
    field = page.get_by_role('textbox', name='Message', exact=True)
    field.fill('Draft to exercise the candidate')
    assert page.get_by_role('button', name='Envoyer', exact=True).is_disabled() == preview_client
    if preview_client:
        field.press('Enter')
        assert 'Draft to exercise' in field.input_value()
        assert not page.evaluate("window.requests.some(r => r.path === 'agent/prompt')")
    page.screenshot(path=f'/tmp/preview-chat-{preview_client}-{width}.png')
    page.get_by_role('button', name='Réglages', exact=True).click()
    page.get_by_role('navigation', name='Sections des réglages').get_by_role('button', name='Conversation', exact=True).click()
    page.get_by_role('textbox', name='Modèle', exact=True).fill('Edited locally')
    assert page.get_by_role('button', name='Enregistrer', exact=True).is_disabled() == preview_client
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_voice_reconnect_keeps_the_chat_and_respects_binding_disable(page):
    page.evaluate("""() => {
      window.voiceEnabled = true;
      window.emit({type: 'command_event', event: {
        type: 'agent.plugin.binding.updated', plugin: 'realtime', enabled: true,
      }});
    }""")
    page.get_by_role('button', name='Démarrer la voix', exact=True).click()
    page.wait_for_function("window.requests.filter(r => r.path === 'realtime/calls/current/ready').length === 1")
    field = page.get_by_role('textbox', name='Message', exact=True)
    field.fill('Brouillon conservé pendant la relance')
    previous = page.evaluate("window.requests.find(r => r.path === 'realtime/calls').body.call_id")
    page.evaluate("id => window.emit({type: 'realtime_reconnect_requested', call_id: id})", previous)
    page.wait_for_function("window.requests.filter(r => r.path === 'realtime/calls/current/ready').length === 2")
    assert field.input_value() == 'Brouillon conservé pendant la relance'
    assert page.locator('.message').count() == 80
    assert page.evaluate('window.closedVoicePeers') == 1
    page.screenshot(path='/tmp/harness-voice-binding-reconnected.png')
    current = page.evaluate("window.requests.filter(r => r.path === 'realtime/calls').at(-1).body.call_id")
    assert current != previous
    page.evaluate("""() => {
      window.voiceEnabled = false;
      window.emit({type: 'command_event', event: {
        type: 'agent.plugin.binding.updated', plugin: 'realtime', enabled: false,
      }});
    }""")
    page.wait_for_function('window.closedVoicePeers === 2')
    page.evaluate("id => window.emit({type: 'realtime_reconnect_requested', call_id: id})", current)
    assert page.evaluate("window.requests.filter(r => r.path === 'realtime/calls').length") == 2
    assert field.input_value() == 'Brouillon conservé pendant la relance'
    assert page.get_by_role('button', name='Démarrer la voix', exact=True).count() == 0


def test_image_layout_scroll_before_load_keeps_following_latest(page):
    # A queued scroll may run after image layout but before its load handler.
    page.evaluate("""() => {
      const el = document.querySelector('.conversation');
      el.scrollTop = el.scrollHeight;
      document.addEventListener('load', event => {
        if (event.target.matches('.artifact img')) {
          window.imageGapBeforeLoad = el.scrollHeight - el.scrollTop - el.clientHeight;
          el.dispatchEvent(new Event('scroll'));
        }
      }, true);
    }""")
    page.evaluate("window.publishArtifact({type:'artifact',id:'layout-image',kind:'image',payload:{src:'/artifact-fixture.png'}})")
    page.wait_for_function("document.querySelector('.artifact img')?.naturalWidth === 640")
    assert page.evaluate('window.imageGapBeforeLoad') > 80
    page.wait_for_function("(() => {const el=document.querySelector('.conversation'); return el.scrollHeight-el.scrollTop-el.clientHeight<5;})()", timeout=2000)


def test_subagent_activity_has_its_own_label_without_changing_history(page):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.evaluate("const el=document.querySelector('.conversation'); el.scrollTop=el.scrollHeight")
    page.screenshot(path="/tmp/harness-subagent-before.png")
    page.evaluate("window.emit({type:'subagent_event', session_id:'child', task_id:'review', agent:'reviewer', event:{type:'agent.tool_call.start', user_feedback:'Vérification des sources'}})")
    activity = page.locator('.subagent-activity')
    activity.get_by_text('Sous-agent · reviewer', exact=True).wait_for()
    activity.get_by_text('Vérification des sources', exact=True).wait_for()
    assert page.locator('.message:not(.subagent-activity)').count() == 80
    page.screenshot(path="/tmp/harness-subagent-after.png")
    page.evaluate("window.emit({type:'subagent_event', session_id:'child', task_id:'review', agent:'reviewer', event:{type:'agent.task.completed'}})")
    activity.wait_for(state='detached')
    assert page.locator('.message').count() == 80


def test_framework_text_stream_commits_once_without_showing_reasoning(page):
    page.evaluate("window.emit({type: 'command_event', event: {type: 'agent.text.delta', channel: 'reasoning', item_id: 'reasoning', sequence: 0, delta: 'Private reasoning'}})")
    assert page.locator('.message').count() == 80
    page.evaluate("window.emit({type: 'command_event', event: {type: 'agent.text.delta', channel: 'output', item_id: 'framework-stream', sequence: 1, delta: 'Streaming through Framework events.'}})")
    page.get_by_text('Streaming through Framework events.', exact=True).wait_for()
    page.screenshot(path='/tmp/harness-framework-streaming.png')
    page.evaluate("window.emit({type: 'command_event', event: {type: 'agent.response_item.added', item: {id: 'framework-stream', type: 'message', role: 'assistant', content: [{type: 'output_text', text: 'Streaming through Framework events.'}]}}})")
    page.wait_for_function("document.querySelectorAll('.message').length === 81")
    assert page.get_by_text('Streaming through Framework events.', exact=True).count() == 1
    assert page.get_by_text('Private reasoning', exact=True).count() == 0
    page.screenshot(path='/tmp/harness-framework-committed.png')


@pytest.mark.parametrize("width", [1280, 390])
def test_voice_phrases_remain_visible_while_delegation_delays_canonical_commits(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page.evaluate("""window.emit({type:'command_event',event:{
      type:'agent.text.delta',channel:'output',kind:'realtime_delegation',
      item_id:'backend-pending',sequence:1,delta:'Backend work in progress'
    }})""")
    spoken = []
    for index in range(2):
        message_id = f"realtime:call:spoken-{index}:assistant"
        text = f"Phrase prononcée pendant l’attente numéro {index + 1}."
        for event in (
            {"type": "voice.transcript.updated", "role": "assistant", "text": text},
            {"type": "voice.turn.completed", "role": "assistant", "turn_id": f"spoken-{index}",
             "message_id": message_id, "transcript": text},
        ):
            page.evaluate("event => window.emit({type:'realtime_event',call_id:'call',event})", event)
        spoken.append({"id": message_id, "type": "message", "role": "assistant",
                       "kind": "realtime", "content": [{"text": text}]})
        for item in spoken:
            assert page.get_by_text(item["content"][0]["text"], exact=True).is_visible()
    # Neither a status update nor an unrelated history reconciliation may erase them.
    page.evaluate("window.emit({type:'worker_status',foreground_active:true,foreground_pending:0})")
    page.evaluate("window.emit({type:'command_completed',command:{type:'compact_request'}})")
    page.wait_for_function("window.requests.filter(r => r.path === 'session').length >= 2")
    for item in spoken:
        assert page.get_by_text(item["content"][0]["text"], exact=True).is_visible()
        page.evaluate("item => window.emit({type:'command_event',event:{type:'agent.response_item.added',item}})", item)
        assert page.get_by_text(item["content"][0]["text"], exact=True).count() == 1
    assert page.locator(".text-agent-output .message-source").count() == 0
    assert page.locator(".message-source").get_by_text("Voice agent", exact=True).count() == 2
    page.screenshot(path=f"/tmp/harness-voice-pending-{width}.png")


def test_voice_survives_server_reconnect_and_interface_publication(page):
    page.add_init_script("window.voiceEnabled = true")
    page.evaluate("""() => {
      window.voiceEnabled = true;
      window.emit({type:'command_event',event:{
        type:'agent.plugin.binding.updated',plugin:'realtime',enabled:true}});
    }""")
    page.get_by_role('button', name='Démarrer la voix', exact=True).click()
    page.wait_for_function("window.requests.filter(r => r.path === 'realtime/calls/current/ready').length === 1")
    original = page.evaluate("window.requests.find(r => r.path === 'realtime/calls').body.call_id")
    page.screenshot(path='/tmp/harness-voice-continuity-before.png')
    page.evaluate("window.emit({type:'server_restarting',instance_id:'server-one'})")
    page.locator('.server-notice').filter(has_text='Redémarrage du serveur…').wait_for()
    # The general announcement must not stop an utterance before voice drains it.
    assert not page.evaluate("window.requests.some(r => r.method === 'DELETE' && r.path === 'realtime/calls/current')")
    page.get_by_role('button', name='Terminer la voix', exact=True).wait_for()
    page.evaluate("""id => {
      window.emit({type:'realtime_restarting',call_id:id});
      window.emit({type:'worker_status',foreground_active:false,foreground_pending:0});
    }""", original)
    assert page.evaluate("window.requests.filter(r => r.path === 'realtime/calls').length") == 1
    page.evaluate("localStorage.setItem('test-server-instance','server-two'); window.socket.readyState = 3; window.socket.onclose()")
    page.wait_for_function("window.requests.filter(r => r.path === 'realtime/calls/current/ready').length === 2")
    page.locator('.server-notice').filter(has_text='Serveur redémarré.').wait_for()
    resumed = page.evaluate("window.requests.filter(r => r.path === 'realtime/calls').at(-1).body.call_id")
    assert resumed != original
    assert page.locator('.message').count() == 80
    page.evaluate("window.emit({type:'interface_refresh_requested'})")
    page.wait_for_function("window.requests?.some(r => r.path === 'realtime/calls/current/ready') && window.requests.filter(r => r.path === 'realtime/calls').length === 1")
    page.get_by_role('button', name='Terminer la voix', exact=True).wait_for()
    published = page.evaluate("window.requests.find(r => r.path === 'realtime/calls').body.call_id")
    assert published != resumed
    assert page.locator('.message').count() == 80
    page.screenshot(path='/tmp/harness-voice-continuity-after.png')
    page.get_by_role('button', name='Terminer la voix', exact=True).click()
    page.get_by_role('button', name='Démarrer la voix', exact=True).wait_for()
    page.reload()
    page.wait_for_function("document.querySelectorAll('.message').length === 80")
    assert not page.evaluate("window.requests.some(r => r.path === 'realtime/calls')")


@pytest.mark.parametrize('preview_client', [True])
def test_preview_never_resumes_voice_intent_inherited_from_the_owner(page, preview_client):
    page.add_init_script("window.voiceEnabled = true")
    page.evaluate("sessionStorage.setItem('voice:wss://harness.test/api/v1/events', JSON.stringify({wanted:true,callId:'owner'}))")
    page.reload()
    page.wait_for_function("document.querySelectorAll('.message').length === 80")
    page.get_by_role('button', name='Démarrer la voix', exact=True).wait_for()
    assert page.get_by_role('button', name='Démarrer la voix', exact=True).is_disabled()
    assert not page.evaluate("window.requests.some(r => r.path.startsWith('realtime/calls'))")


@pytest.mark.parametrize("width", [1280, 390])
def test_private_access_settings_require_opt_in_then_show_local_qr(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Appareils et accès distant", exact=True).click()
    pairing = page.get_by_role("button", name="Créer un code d’association", exact=True)
    assert pairing.is_disabled()
    enable = page.get_by_role("button", name="Activer l’accès privé Tailscale", exact=True)
    # Native JS confirmations are unavailable in the automated desktop browser.
    page.on("dialog", lambda dialog: dialog.dismiss())
    enable.click()
    confirmation = page.get_by_role("dialog", name="Activer l’accès privé Tailscale", exact=True)
    confirmation.wait_for()
    page.screenshot(path=f"/tmp/harness-device-confirmation-{width}.png")
    confirmation.get_by_role("button", name="Annuler", exact=True).click()
    assert not page.evaluate("window.requests.some(r => r.path === 'client-remote/network' && r.body)")
    enable.click()
    confirmation.get_by_role("button", name="Activer l’accès privé Tailscale", exact=True).click()
    page.get_by_text("Accès privé activé", exact=True).wait_for()
    pairing.click()
    qr = page.get_by_role("img", name="QR code secret d’association temporaire")
    qr.wait_for()
    assert qr.get_attribute("src").startswith("data:image/png;base64,")
    assert page.get_by_role("textbox", name="Lien d’association").input_value().startswith("theharness://pair?")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"/tmp/harness-device-settings-{width}.png", full_page=True)


@pytest.mark.parametrize("width", [1280, 390])
def test_status_failure_does_not_discard_history_and_recovers(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    item = {"id": "status-outage-answer", "type": "message", "role": "assistant",
            "content": [{"text": "History available despite status outage"}]}
    page.evaluate("""item => {
      localStorage.setItem('test-artifacts', JSON.stringify([item]));
      window.failStatus = true;
      window.holdStatus = true;
      window.emit({type: 'command_completed', command: {type: 'prompt_request', id: 'test'}});
    }""", item)
    page.wait_for_function("typeof window.releaseStatus === 'function'")
    page.get_by_text("History available despite status outage", exact=True).wait_for()
    page.evaluate("window.holdStatus = false; window.releaseStatus()")
    page.get_by_role("alert").filter(has_text="agent status temporarily unavailable").wait_for()
    # Recovery clears this transient error, not unrelated send failures.
    page.evaluate("""() => {
      window.failStatus = false;
      window.emit({type: 'command_completed', command: {type: 'prompt_request', id: 'test'}});
    }""")
    page.get_by_role("alert").wait_for(state="detached")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width", [1280, 390])
def test_planned_restart_has_neutral_feedback_until_new_instance_is_ready(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    field = page.locator(".composer textarea")
    field.fill("Draft preserved during restart")
    page.evaluate("window.emit({type:'server_restarting',instance_id:'server-one',phase:'restarting'})")
    notice = page.locator(".server-notice")
    notice.filter(has_text="Redémarrage du serveur…").wait_for()
    assert page.get_by_role("button", name="Envoyer", exact=True).is_disabled()
    page.evaluate("""() => {
      window.emit({type:'command_failed',error:'interrupted',command:{id:'drained',type:'prompt_request'}});
      window.emit({type:'worker_exited',returncode:0});
      window.socket.onclose();
    }""")
    page.wait_for_function("document.querySelector('.connection').dataset.state === 'Connected'")
    # A successful reconnect to the old server is not proof of a restart.
    assert notice.inner_text() == "Redémarrage du serveur…"
    assert page.get_by_role("alert").count() == 0
    assert field.input_value() == "Draft preserved during restart"
    page.reload()
    notice.filter(has_text="Redémarrage du serveur…").wait_for()
    page.evaluate("""() => {
      localStorage.setItem('test-server-instance','server-two');
      window.emit({type:'command_completed',command:{id:'resumed',type:'prompt_request'}});
    }""")
    notice.filter(has_text="Serveur redémarré.").wait_for()
    assert page.get_by_role("alert").count() == 0
    page.screenshot(path=f"/tmp/harness-server-restarted-{width}.png", full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.clock.install()
    page.clock.fast_forward(5100)
    notice.wait_for(state="detached")
    # Later healthy status refreshes must not resurrect the confirmation.
    page.evaluate("window.emit({type:'command_completed',command:{id:'refresh',type:'prompt_request'}})")
    page.wait_for_timeout(100)
    assert notice.count() == 0


def test_restart_success_timer_does_not_hide_a_subsequent_restart(page):
    page.clock.install()
    page.evaluate("""() => {
      window.emit({type:'server_restarting',instance_id:'server-one'});
      localStorage.setItem('test-server-instance','server-two');
      window.emit({type:'command_completed',command:{id:'resumed',type:'prompt_request'}});
    }""")
    notice = page.locator(".server-notice")
    notice.filter(has_text="Serveur redémarré.").wait_for()
    page.clock.fast_forward(4000)
    assert notice.is_visible()
    page.evaluate("window.emit({type:'server_restarting',instance_id:'server-two'})")
    page.clock.fast_forward(2000)
    notice.filter(has_text="Redémarrage du serveur…").wait_for()
    page.evaluate("window.emit({type:'server_restart_failed',instance_id:'server-two',error:'Supervisor unavailable'})")
    page.clock.fast_forward(31000)
    notice.filter(has_text="Le redémarrage du serveur a échoué.").wait_for()
    notice.get_by_role("button", name="Fermer", exact=True).click()
    assert notice.count() == 0


def test_restart_does_not_hide_real_errors_and_reports_explicit_failure(page):
    page.evaluate("window.emit({type:'server_restarting',instance_id:'server-one'})")
    page.evaluate("window.emit({type:'command_failed',error:'disk full',command:{id:'failed',type:'prompt_request'}})")
    page.get_by_role("alert").filter(has_text="disk full").wait_for()
    page.evaluate("window.emit({type:'server_restart_failed',instance_id:'server-one',error:'Supervisor unavailable'})")
    notice = page.locator(".server-notice")
    notice.filter(has_text="Le redémarrage du serveur a échoué.").wait_for()
    assert notice.get_attribute("role") == "alert"
    assert "Supervisor unavailable" in notice.inner_text()


def test_unplanned_interruption_remains_an_error(page):
    page.evaluate("window.emit({type:'command_failed',error:'interrupted',command:{id:'failed',type:'prompt_request'}})")
    page.get_by_role("alert").filter(has_text="interrupted").wait_for()
    assert page.locator(".server-notice").count() == 0


def test_delayed_restart_never_claims_success(page):
    page.clock.install()
    page.evaluate("window.emit({type:'server_restarting',instance_id:'server-one'})")
    page.locator(".server-notice").filter(has_text="Redémarrage du serveur…").wait_for()
    page.clock.fast_forward(31000)
    page.locator(".server-notice").filter(has_text="Le serveur ne répond pas encore. Reconnexion en cours…").wait_for()
    assert page.get_by_text("Serveur redémarré.", exact=True).count() == 0


def test_desktop_browser_button_preserves_draft_and_prevents_duplicate_requests(page):
    button = page.get_by_role("button", name="Ouvrir le navigateur", exact=True)
    assert button.is_enabled()
    assert page.locator(".topbar-actions button").evaluate_all("buttons => buttons.map(b => b.getAttribute('aria-label'))") == ["Ouvrir le navigateur", "Réglages"]
    field = page.locator(".composer textarea")
    field.fill("Brouillon conservé")
    page.screenshot(path="/tmp/harness-browser-toolbar.png")
    page.evaluate("window.holdBrowserOpen = true")
    button.click()
    page.wait_for_function("typeof window.releaseBrowserOpen === 'function'")
    assert button.is_disabled()
    assert button.get_attribute("aria-busy") == "true"
    assert page.evaluate("window.requests.filter(r => r.path === 'browser/open').map(r => r.method)") == ["POST"]
    page.evaluate("window.releaseBrowserOpen()")
    page.wait_for_function("!document.querySelector('[aria-label=\"Ouvrir le navigateur\"]').disabled")
    assert field.input_value() == "Brouillon conservé"
    page.evaluate("window.failBrowserOpen = true; window.holdBrowserOpen = false")
    button.click()
    page.get_by_role("alert").filter(has_text="Integrated browser unavailable").wait_for()
    assert button.is_enabled()


@pytest.mark.parametrize("preview_client", [True])
def test_preview_cannot_open_local_browser(page, preview_client):
    assert page.get_by_role("button", name="Ouvrir le navigateur", exact=True).is_disabled()
    assert not page.evaluate("window.requests.some(r => r.path === 'browser/open')")


def test_remote_mobile_has_no_local_browser_button(page):
    page.goto("https://harness.ts.net/")
    page.get_by_role("button", name="Réglages", exact=True).wait_for()
    assert page.get_by_role("button", name="Ouvrir le navigateur", exact=True).count() == 0
