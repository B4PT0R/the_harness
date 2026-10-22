"""Quota UI interactions use only a fake backend."""


def test_reset_requires_explicit_confirmation(page):
    gauge = page.locator(".quota-gauge")
    assert "84%" in gauge.inner_text()
    gauge.click()
    dialog = page.locator(".quota-dialog")
    assert "2099" in dialog.inner_text()
    dialog.get_by_role("button", name="Utiliser…", exact=True).click()
    assert page.evaluate("window.requests.filter(r => r.path === 'quota/consume').length") == 0
    dialog.get_by_role("button", name="Consommer ce reset", exact=True).click()
    page.wait_for_function("document.querySelector('.quota-gauge').textContent.includes('0%')")
    assert page.evaluate("window.requests.filter(r => r.path === 'quota/consume').length") == 1


def test_persistent_policy_is_explicit(page):
    page.get_by_role("button", name="Réglages", exact=True).click()
    page.get_by_role("button", name="Conversation", exact=True).click()
    policy = page.locator("#quota-policy")
    assert policy.input_value() == "block"
    policy.select_option("consume_earliest")
    page.wait_for_function("window.requests.some(r => r.path === 'quota/policy' && r.body.exhausted_policy === 'consume_earliest')")
    assert policy.input_value() == "consume_earliest"


def open_mobile(page, width=360):
    page.set_viewport_size({"width": width, "height": 740})
    page.goto("https://computer.example.ts.net/")
    page.wait_for_function("document.querySelector('.quota-gauge')?.textContent.includes('84%')")
    page.locator(".quota-gauge").click()
    return page.locator(".quota-dialog")


def test_mobile_reset_confirmation_and_small_screen_layout(page):
    dialog = open_mobile(page, 320)
    box = dialog.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 321
    assert dialog.evaluate("element => element.scrollWidth <= element.clientWidth")
    assert page.locator(".quota-gauge").bounding_box()["width"] > 0
    dialog.get_by_role("button", name="Utiliser…", exact=True).click()
    assert page.evaluate("window.requests.filter(r => r.path === 'quota/consume').length") == 0
    dialog.get_by_role("button", name="Annuler", exact=True).click()
    dialog.get_by_role("button", name="Utiliser…", exact=True).click()
    dialog.get_by_role("button", name="Consommer ce reset", exact=True).click()
    page.wait_for_function("document.querySelector('.quota-gauge').textContent.includes('0%')")
    assert page.evaluate("window.requests.filter(r => r.path === 'quota/consume').length") == 1


def test_mobile_reset_error_keeps_quota_and_confirmation(page):
    dialog = open_mobile(page)
    page.evaluate("window.failQuotaConsume = true")
    dialog.get_by_role("button", name="Utiliser…", exact=True).click()
    dialog.get_by_role("button", name="Consommer ce reset", exact=True).click()
    assert dialog.get_by_role("alert").inner_text()
    assert "84%" in page.locator(".quota-gauge").inner_text()
    assert page.evaluate("window.requests.filter(r => r.path === 'quota/consume').length") == 1
