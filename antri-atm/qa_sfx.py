#!/usr/bin/env python3
"""QA: confirm SFX click + trombone audible in final.mp4 (peak level vs silence)."""
import struct, subprocess, wave, sys

FF = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
FINAL = "/home/mahmud/projects/doodle-humor-video/antri-atm/final.mp4"

def peak_at(t, dur=1.5, tag="x"):
    wav = f"/tmp/atm-sfx-{tag}.wav"
    subprocess.run([FF, "-v", "error", "-ss", str(t), "-t", str(dur),
                    "-i", FINAL, "-ac", "1", "-y", wav], check=True)
    w = wave.open(wav)
    data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    return max(abs(s) for s in samples)

# shot starts: computed in render; click at shot-02 (~9s), trombone at shot-08 (~24s)
click = peak_at(8.8, 1.5, "click")
trom  = peak_at(24.0, 2.0, "trom")
print(f"click peak={click}  trombone peak={trom}")
assert click > 1000, "click SFX missing/too quiet"
assert trom > 1000, "trombone SFX missing/too quiet"
print("SFX PASS")
