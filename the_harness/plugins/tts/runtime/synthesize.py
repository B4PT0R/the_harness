"""One local CPU synthesis; text travels over stdin, never process arguments."""

import sys
import wave

from piper import PiperVoice


if __name__ == "__main__":
    voice = PiperVoice.load(sys.argv[1], use_cuda=False)
    with wave.open(sys.argv[2], "wb") as audio:
        voice.synthesize_wav(sys.stdin.buffer.read().decode("utf-8"), audio)
