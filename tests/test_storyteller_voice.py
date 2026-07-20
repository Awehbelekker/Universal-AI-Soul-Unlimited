"""Storyteller WAV shift (parent clone distinctness)."""

import io
import wave


def _tiny_wav(seconds: float = 0.05, rate: int = 16000) -> bytes:
    import struct

    n = int(rate * seconds)
    frames = b"".join(struct.pack("<h", 0) for _ in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def test_storyteller_shift_changes_framerate():
    from core.voice_pipeline.desktop_voice import storyteller_shift_wav

    raw = _tiny_wav()
    with wave.open(io.BytesIO(raw), "rb") as w:
        orig = w.getframerate()
    shifted = storyteller_shift_wav(raw, rate_factor=1.07)
    with wave.open(io.BytesIO(shifted), "rb") as w:
        new = w.getframerate()
    assert new != orig
    assert abs(new - int(orig * 1.07)) <= 1
