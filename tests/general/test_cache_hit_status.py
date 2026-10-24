import re

import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize("width", [320, 360, 1280])
def test_cache_status_displays_unknown_zero_and_smoothed_api_measurements(page, width):
    page.set_viewport_size({"width": width, "height": 800})
    badge = page.locator(".cache-hit")
    expect(badge.locator("text")).to_have_text("–")
    expect(badge).to_have_attribute("aria-label", re.compile(r"^Cache – %\."))
    expect(badge).to_have_attribute("title", "Cache API non mesuré. Appels de l’agent conversationnel uniquement, hors voix et sous-agents.")
    page.evaluate("""() => window.emit({type: 'worker_status', cache_hit: {
      alpha: 0.1, ema_percent: 0, last_percent: 0, samples: 1,
      unreported: 0, updated_at: 1800000000,
    }})""")
    expect(badge.locator("text")).to_have_text("0%")
    expect(badge.locator(".gauge-fill")).to_have_attribute("stroke-dasharray", "0 100")
    page.evaluate("""() => window.emit({type: 'worker_status', cache_hit: {
      alpha: 0.1, ema_percent: 87.25, last_percent: null, samples: 20,
      unreported: 1, updated_at: 1800000000,
    }})""")
    expect(badge.locator("text")).to_have_text("87%")
    expect(badge.locator(".gauge-fill")).to_have_attribute("stroke-dasharray", "87.25 100")
    expect(badge).to_have_attribute("aria-label", re.compile(r"^Cache 87,3 %\."))
    assert "20 mesures" in badge.get_attribute("title")
    assert "dernier appel : – %" in badge.get_attribute("title")
    assert "1 appels non mesurables (exclus)" in badge.get_attribute("title")
    assert "α = 0,1" in badge.get_attribute("title")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert badge.bounding_box()["x"] > page.locator(".brand").bounding_box()["x"] + page.locator(".brand").bounding_box()["width"]


@pytest.mark.parametrize('width', [320, 360, 390, 480, 720, 1280])
def test_technical_indicators_share_top_left_without_crowding_actions(page, width):
    page.set_viewport_size({'width': width, 'height': 800})
    page.evaluate('''window.emit({type: 'worker_status', local_input_tokens: 40,
      context_token_limit: 200, cache_hit: {ema_percent: 100, alpha: 0.1,
      samples: 20, last_percent: 100, unreported: 0, updated_at: 1800000000}})''')
    indicators = page.locator('.topbar-left .technical-status')
    expect(indicators.locator('.quota-gauge')).to_be_visible()
    expect(indicators.locator('.gauge-caption')).to_have_text(['7D', 'CTX', 'CH'])
    expect(indicators.locator('.gauge-ring')).to_have_count(3)
    geometry = indicators.locator('.technical-gauge').evaluate_all("""nodes => nodes.map(node => {
      const ring = node.querySelector('svg').getBoundingClientRect();
      const caption = node.querySelector('.gauge-caption').getBoundingClientRect();
      return [ring.width, ring.height, caption.top >= ring.bottom];
    })""")
    assert geometry == [[32, 32, True]] * 3
    expect(indicators.locator('.context-gauge')).to_be_enabled()
    expect(indicators.locator('.cache-hit text')).to_have_text('100%')
    expect(page.locator('.composer .quota-gauge, .composer .context-gauge, .topbar-actions .cache-hit')).to_have_count(0)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    layout = page.locator('.topbar').evaluate('''bar => {
      const rect = selector => {
        const r = bar.querySelector(selector).getBoundingClientRect();
        return {left: r.left, right: r.right, top: r.top, bottom: r.bottom};
      };
      return {indicators: rect('.technical-status'), actions: rect('.topbar-actions')};
    }''')
    left, right = layout['indicators'], layout['actions']
    assert left['right'] <= right['left']
    assert abs((left['top'] + left['bottom']) - (right['top'] + right['bottom'])) <= 2
    indicators.locator('.quota-gauge').click()
    dialog = page.get_by_role('dialog')
    expect(dialog).to_be_visible()
    dialog.get_by_role('button', name='Fermer', exact=True).click()
    indicators.locator('.context-gauge').click()
    page.wait_for_function("window.requests.some(r => r.path === 'agent/compact')")
    expect(indicators.locator('.context-gauge')).to_have_attribute('aria-busy', 'true')
