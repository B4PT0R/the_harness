"""Dictation edits a draft, never sends it, on desktop and mobile layouts."""
import pytest
from playwright.sync_api import expect


MICROPHONE = """
window.dictationEnabled = true;
window.voiceEnabled = true;
window.stoppedTracks = 0;
Object.defineProperty(navigator, 'mediaDevices', { value: {
  async getUserMedia() {
    if (window.denyMicrophone) throw new DOMException('Denied', 'NotAllowedError');
    return { getTracks: () => [{stop() { window.stoppedTracks++; }}] };
  }
}});
// A real decodable PCM WAV fixture exercises WebAudio conversion, not a bypass.
window.dictationWav = (() => {
  const bytes = new ArrayBuffer(44 + 4800 * 2), view = new DataView(bytes);
  const text = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset+i, c.charCodeAt(0)));
  text(0, 'RIFF'); view.setUint32(4, bytes.byteLength-8, true); text(8, 'WAVE');
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, 24000, true); view.setUint32(28, 48000, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data');
  view.setUint32(40, 9600, true);
  return bytes;
})();
window.MediaRecorder = class {
  static isTypeSupported() { return true; }
  constructor(stream, options) { this.mimeType = options.mimeType; this.state = 'inactive'; }
  start() { this.state = 'recording'; }
  stop() {
    this.state = 'inactive';
    queueMicrotask(() => {
      this.ondataavailable({data: new Blob([window.dictationWav], {type: 'audio/wav'})});
      this.onstop();
    });
  }
};
"""


def enable(page):
    page.add_init_script(MICROPHONE)
    page.reload()
    page.get_by_role('button', name='Dicter un message', exact=True).wait_for()


@pytest.mark.parametrize('width', [1280, 390])
def test_dictation_appends_to_latest_draft_without_sending(page, width):
    enable(page)
    page.set_viewport_size({'width': width, 'height': 800})
    field = page.locator('.composer textarea')
    field.fill('Mon brouillon.')
    page.evaluate('window.holdDictation = true')
    page.get_by_role('button', name='Dicter un message', exact=True).click()
    page.get_by_text('Dictée en cours', exact=False).wait_for()
    expect(page.get_by_role('button', name='Envoyer', exact=True)).to_be_disabled()
    page.get_by_role('button', name='Terminer et transcrire la dictée', exact=True).click()
    page.get_by_text('Transcription en cours…', exact=True).wait_for()
    field.fill('Mon brouillon complété.')
    page.wait_for_function("typeof window.releaseDictation === 'function'")
    page.evaluate('window.releaseDictation()')
    expect(field).to_have_value('Mon brouillon complété. Bonjour depuis la dictée.')
    expect(field).to_be_focused()
    assert page.evaluate("window.requests.filter(r => r.path === 'dictation/transcribe').length") == 1
    assert page.evaluate("window.requests.find(r => r.path === 'dictation/transcribe').body.language") == 'fr'
    assert not page.evaluate("window.requests.some(r => r.path.startsWith('agent/'))")
    assert page.evaluate('window.stoppedTracks > 0')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.parametrize('failure', ['denyMicrophone', 'failDictation'])
def test_dictation_failure_keeps_draft(page, failure):
    enable(page)
    page.locator('.composer textarea').fill('Texte conservé')
    page.evaluate('key => { window[key] = true; }', failure)
    page.get_by_role('button', name='Dicter un message', exact=True).click()
    if failure == 'failDictation':
        page.get_by_role('button', name='Terminer et transcrire la dictée', exact=True).click()
    page.get_by_role('alert').wait_for()
    expect(page.get_by_role('alert')).to_contain_text(
        'microphone a été refusé' if failure == 'denyMicrophone' else 'Votre brouillon est conservé')
    expect(page.locator('.composer textarea')).to_have_value('Texte conservé')
    expect(page.get_by_role('button', name='Dicter un message', exact=True)).to_be_enabled()
    assert not page.evaluate("window.requests.some(r => r.path.startsWith('agent/'))")


def test_cancel_late_transcription_does_not_change_draft(page):
    enable(page)
    page.evaluate('window.holdDictation = true')
    page.get_by_role('button', name='Dicter un message', exact=True).click()
    page.get_by_role('button', name='Terminer et transcrire la dictée', exact=True).click()
    page.wait_for_function("typeof window.releaseDictation === 'function'")
    page.get_by_role('button', name='Annuler la dictée', exact=True).click()
    page.evaluate('window.releaseDictation()')
    expect(page.locator('.composer textarea')).to_have_value('')
    expect(page.get_by_role('button', name='Dicter un message', exact=True)).to_be_enabled()


def test_dictation_hidden_when_plugin_unavailable(page):
    expect(page.get_by_role('button', name='Dicter un message', exact=True)).to_have_count(0)


@pytest.mark.parametrize('width', [320, 360, 390, 480, 1280])
@pytest.mark.parametrize('busy', [False, True])
def test_all_composer_actions_fit_without_overlap(page, width, busy):
    enable(page)
    page.set_viewport_size({'width': width, 'height': 800})
    page.evaluate("busy => window.emit({type: 'worker_status', foreground_active: busy, foreground_pending: 0})", busy)
    buttons = page.locator('.composer-actions button').filter(visible=True)
    expect(buttons).to_have_count(5 if busy else 4)
    layout = buttons.evaluate_all('''buttons => {
      const form = document.querySelector('.composer').getBoundingClientRect();
      return {left: form.left, right: form.right, buttons: buttons.map(button => {
        const r = button.getBoundingClientRect();
        return {left: r.left, right: r.right, top: r.top, height: r.height,
          icon: button.classList.contains('icon-button')};
      })};
    }''')
    previous = None
    for rect in layout['buttons']:
        assert layout['left'] <= rect['left'] < rect['right'] <= layout['right']
        if rect['icon']:
            assert rect['height'] >= 40
        if previous:
            assert rect['left'] >= previous['right']
            assert abs(rect['top'] + rect['height'] / 2 - previous['top'] - previous['height'] / 2) <= 1
        previous = rect
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
