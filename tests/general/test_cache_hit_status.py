import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("width", [320, 360, 1280])
def test_cache_status_displays_unknown_zero_and_smoothed_api_measurements(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    badge = page.locator(".cache-hit")
    expect(badge).to_have_text("Cache – %")
    expect(badge).to_have_attribute("title", "Cache API non mesuré. Appels de l’agent conversationnel uniquement, hors voix et sous-agents.")
    page.evaluate("""() => window.emit({type: 'worker_status', cache_hit: {
      alpha: 0.1, ema_percent: 0, last_percent: 0, samples: 1,
      unreported: 0, updated_at: 1800000000,
    }})""")
    expect(badge).to_have_text("Cache 0 %")
    page.evaluate("""() => window.emit({type: 'worker_status', cache_hit: {
      alpha: 0.1, ema_percent: 87.25, last_percent: null, samples: 20,
      unreported: 1, updated_at: 1800000000,
    }})""")
    expect(badge).to_have_text("Cache 87,3 %")
    assert "20 mesures" in badge.get_attribute("title")
    assert "dernier appel : – %" in badge.get_attribute("title")
    assert "1 appels non mesurables (exclus)" in badge.get_attribute("title")
    assert "α = 0,1" in badge.get_attribute("title")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert badge.bounding_box()["x"] > page.locator(".brand").bounding_box()["x"] + page.locator(".brand").bounding_box()["width"]
