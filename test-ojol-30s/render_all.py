#!/usr/bin/env python3
"""Render one Fish Audio MP3 per dialogue line, then build the full 30s video."""
import json, os, subprocess, sys

FF = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
SK = "/home/mahmud/.hermes/skills/ink-doodle-humor-video/scripts"
P = "/home/mahmud/projects/doodle-humor-video/test-ojol-30s"
V1 = "ab5b789ad6e14420afed2d454d4fc662"   # DANU
V2 = "ee65e2ec8bfc4883961761d581dff597"   # RIKO

LINES = [
    ("scene-01", V1, "[tired]Orderan masuk, jemput di Gang Melati.", "Gang"),
    ("scene-02", V2, "[santai]Bang, masuk gang aja, deket kok, lima menit sampai.", "deket"),
    ("scene-03", V1, "[kesal]Lima menit katanya, ini udah gang keempat, makin sempit jalannya.", "keempat"),
    ("scene-04", V2, "[tenang]Tenang bang, abis ini belok kiri, langsung sampai.", "langsung"),
    ("scene-05", V1, "[panik]Bang, ini sih bukan gang lagi, motor saya aja sampai miring.", "miring"),
    ("scene-06", V2, "[yakin]Nah kan bener, deket! Itu rumahnya, yang cat hijau itu.", "deket"),
    ("scene-07", V1, "[pasrah]Bang... itu pos ronda.", "pos ronda"),
]

SCENE_IMG = {
    "scene-01": "scene-01.png", "scene-02": "scene-02.png", "scene-03": "scene-03.png",
    "scene-04": "scene-04.png", "scene-05": "scene-05.png", "scene-06": "scene-06.png",
    "scene-07": "scene-07.png",
}
# zoom target = speaking character head/mouth centre (normalized)
TARGET = {
    "scene-01": (0.50, 0.35), "scene-02": (0.42, 0.32), "scene-03": (0.50, 0.35),
    "scene-04": (0.55, 0.32), "scene-05": (0.50, 0.30), "scene-06": (0.55, 0.35),
    "scene-07": (0.45, 0.32),
}
MODE = {"scene-01": "in", "scene-02": "out", "scene-03": "in", "scene-04": "out",
        "scene-05": "in", "scene-06": "out", "scene-07": "hold"}


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def tts(text, vid, out):
    body = json.dumps({"text": text, "reference_id": vid, "format": "mp3"})
    cmd = ("curl -sS -X POST https://api.fish.audio/v1/tts "
           f"-H \"Authorization: Bearer $FISH_API_KEY\" -H \"Content-Type: application/json\" "
           f"-H \"model: $FISH_MODEL_ID\" -d '{body}' --output '{out}'")
    r = sh("set -a; source ~/.hermes/.env; set +a; " + cmd)
    return os.path.exists(out) and os.path.getsize(out) > 0


def main():
    sd = f"{P}/scenes"
    os.makedirs(sd, exist_ok=True)
    spec = []
    for name, vid, text, hl in LINES:
        mp3 = f"{sd}/{name}-line.mp3"
        ok = tts(text, vid, mp3)
        size = os.path.getsize(mp3) if os.path.exists(mp3) else 0
        print(f"{name} tts={'OK' if ok else 'FAIL'} bytes={size}")
        if not ok:
            sys.exit(1)
        spec.append({"text": text.split("]", 1)[1], "highlight": hl, "mp3": mp3})

    json.dump(spec, open(f"{P}/lines.json", "w"), ensure_ascii=False, indent=1)

    # cap_y per scene (baseline in ASS px, 1080x1920 frame), measured from the
    # largest empty cream zone on the scene image (vision + ink scan). Never over a face.
    CAP_Y = {"scene-01": 1875, "scene-02": 1870, "scene-03": 1875, "scene-04": 1850,
             "scene-05": 1875, "scene-06": 1840, "scene-07": 1850}
    clips = []
    for name, _, _, _ in LINES:
        px, py = TARGET[name]
        out = f"{sd}/{name}.mp4"
        # PER-SCENE captions: each clip starts at t=0, so its caption must too.
        one = next(s for s in spec if s["mp3"].endswith(f"{name}-line.mp3"))
        json.dump([one], open(f"{sd}/{name}-cap.json", "w"), ensure_ascii=False)
        r = sh(f"PYTHONPATH={SK} python3 {SK}/sync_captions.py {sd}/{name}-cap.json {sd}/{name}.ass "
               f"--cap-y {CAP_Y[name]}")
        if not os.path.exists(f"{sd}/{name}.ass"):
            print(name, "caption FAIL:", r.stderr.strip()[-200:]); sys.exit(1)
        r = sh(f"python3 {SK}/build_scene.py {sd}/{SCENE_IMG[name]} {sd}/{name}-line.mp3 {out} "
               f"--px {px} --py {py} --zoom 1.30 --mode {MODE[name]} --ass {sd}/{name}.ass")
        print(name, "build:", r.stdout.strip() or r.stderr.strip()[-200:])
        clips.append(out)

    with open(f"{P}/concat.txt", "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    final = f"{P}/final-30s.mp4"
    r = sh(f"{FF} -v error -f concat -safe 0 -i {P}/concat.txt -c copy {final} -y")
    if r.returncode != 0:
        r = sh(f"{FF} -v error -f concat -safe 0 -i {P}/concat.txt "
               f"-c:v libx264 -preset veryfast -c:a aac {final} -y")
    dur = sh(f"/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffprobe -v error "
             f"-show_entries format=duration -of csv=p=0 {final}").stdout.strip()
    print("FINAL:", final, "duration:", dur, "bytes:", os.path.getsize(final) if os.path.exists(final) else 0)


if __name__ == "__main__":
    main()
