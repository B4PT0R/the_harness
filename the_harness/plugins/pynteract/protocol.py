"""Small bounded JSON protocol shared only by this plugin's two processes."""

import json

MAX_FRAME = 1024 * 1024
MAX_CODE = 128 * 1024
MAX_OUTPUT_TOKENS = 4_000
MAX_CAPTURE_CHARS = 256 * 1024
MAX_STREAM_BYTES = 256 * 1024


def encode(value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    if len(data) > MAX_FRAME:
        raise ValueError("Pynteract JSON frame exceeds 1 MiB; export a smaller projection or a file.")
    return data


async def receive(reader):
    line = await reader.readline()
    if not line:
        raise EOFError("Pynteract connection closed; the session process may have exited.")
    if len(line) > MAX_FRAME or not line.endswith(b"\n"):
        raise ValueError("Invalid or oversized Pynteract frame.")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Pynteract frames must be JSON objects.")
    return value


async def send(writer, value):
    writer.write(encode(value))
    await writer.drain()
