"""Feedback on current React memoization; render counts are not a public API."""

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
    page.evaluate("window.emit({ type: 'command_event', event: { type: 'agent.text.delta', item_id: 'stream', channel: 'output', sequence: 1, delta: 'Streaming response' } })")
    page.wait_for_function("document.querySelectorAll('.message').length === 81")
    assert page.locator(".message").last.inner_text() == "Streaming response"
    assert page.evaluate("window.markdownRenders") == before + 1
    page.evaluate("window.emit({ type: 'command_event', event: { type: 'agent.text.delta', item_id: 'stream', channel: 'output', sequence: 2, delta: ' updated' } })")
    page.wait_for_function("document.querySelector('.message:last-child').textContent.includes('updated')")
    assert page.evaluate("window.markdownRenders") == before + 2
    assert field.input_value() == "a" * 1960
