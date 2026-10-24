"""One settings surface; client identity, not viewport, controls local tools."""
import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("width", [320, 390, 1280])
@pytest.mark.parametrize("remote", [False, True])
def test_settings_share_sections_and_save_without_host_tools(page, width, remote):
    page.set_viewport_size({"width": width, "height": 800})
    # Simulate an authenticated remote desktop on the same host: no hostname heuristic.
    page.evaluate("value => { window.remoteClient = value; }", remote)
    page.get_by_role("button", name="Réglages", exact=True).click()
    settings = page.locator(".settings")
    nav = settings.locator(".settings-nav")
    expect(nav.get_by_role("button")).to_have_count(6 if remote else 7)
    expect(settings.locator(".file-editor-settings")).to_have_count(0 if remote else 1)
    if remote:
        expect(nav.get_by_role("button", name="Appareils et accès distant")).to_have_count(0)
        expect(settings.get_by_text("Les réglages de la conversation", exact=False)).to_be_visible()
    else:
        nav.get_by_role("button", name="Appareils et accès distant").click()
        expect(settings.get_by_role("button", name="Créer un code d’association")).to_be_visible()
    for label, selector in [("Conversation", "#settings-conversation"), ("Voix", "#settings-voice"),
                            ("Capacités", "#settings-capabilities"), ("Avancé", "#settings-advanced"),
                            ("Données", "#settings-data")]:
        nav.get_by_role("button", name=label, exact=True).click()
        expect(settings.locator(selector)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    nav.get_by_role("button", name="Voix", exact=True).click()
    settings.get_by_role("combobox", name="Voix utilisée").select_option("breeze")
    settings.get_by_role("button", name="Enregistrer", exact=True).click()
    expect(settings.get_by_text("Réglages enregistrés.", exact=True)).to_be_visible()
    assert page.evaluate("window.requests.find(r => r.path === 'config' && r.method === 'PATCH').body.realtime.voice") == "breeze"
    if remote:
        assert not page.evaluate("window.requests.some(r => ['local-files/settings', 'client-remote/network', 'client-remote/pairings'].includes(r.path))")
    if width == 390 and remote:
        page.screenshot(path="/tmp/shared-settings-remote.png")


def test_android_origin_uses_the_shared_settings_panel(page):
    page.goto("https://computer.example.ts.net/")
    page.get_by_role("button", name="Réglages", exact=True).click()
    nav = page.locator(".settings-nav")
    expect(nav.get_by_role("button")).to_have_count(6)
    nav.get_by_role("button", name="Voix", exact=True).click()
    expect(page.get_by_role("combobox", name="Voix utilisée")).to_be_enabled()
    assert not page.evaluate("window.requests.some(r => r.path === 'client-remote/network')")
