#!/usr/bin/env python3
"""Full render for ojol-hujan: 11 shot-per-line, TTS, captions, BGM."""
import json, os, subprocess, sys

FF = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
FP = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffprobe"
SK = "/home/mahmud/.hermes/skills/ink-doodle-humor-video/scripts"
P = "/home/mahmud/projects/doodle-humor-video/ojol-hujan"
V1 = "ab5b789ad6e14420afed2d454d4fc662"
V2 = "ee65e2ec8bfc4883961761d581dff597"

# (shot, voice_id, text, highlight)
LINES = [
    ("shot-01", V1, "[frustrated] Waduh, hujan deres banget.", "deres"),
    ("shot-02", V2, "[anxious] Bang, berhenti dulu, gue gak bawa jas hujan.", "jas hujan"),
    ("shot-03", V1, "[calm] Tenang, gue ada satu.", "satu"),
    ("shot-04", V2, "[doubtful] Satu doang? Buat siapa?", "Satu"),
    ("shot-05", V1, "[confident] Buat lu aja, gue tahan.", "tahan"),
    ("shot-06", V2, "[stubborn] Gak usah bang, gue tahan aja.", "tahan"),
    ("shot-07", V1, "[annoyed] Yaudah, gue pakai sendiri.", "sendiri"),
    ("shot-08", V2, "[panicked] Bang, tungguin...", "tungguin"),
    ("shot-09", V1, "[generous] Nih, pakai aja.", "pakai"),
    ("shot-10", V2, "[shocked] Bang, punggung lu basah.", "basah"),
    ("shot-11", V1, "[cheerful] Yang penting niatnya baik, yang basa biar Allah yang atur.", "Allah"),
]

ZOOM = {f"shot-{i:02d}": (0.5, 0.35, 1.25, "in") for i in range(1,12)}
ZOOM["shot-11"] = (0.5, 0.35, 1.35, "hold")

CAP_Y = {f"shot-{i:02d}": 1850 for i in range(1,12)}
CAP_Y["shot-01"] = 1870
CAP_Y["shot-02"] = 1870
CAP_Y["shot-08"] = 1870


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def tts(text, vid, out):
    body = json.dumps({"text": text, "reference_id": vid, "format": "mp3"})
    cmd = ("curl -sS -X POST https://api.fish.audio/v1/tts "
           f"-H \"Authorization: Bearer $FISH_API_KEY\" -H \"Content-Type: application/json\" "
           f"-H \"model: $FISH_MODEL_ID\" -d '{body}' --output '{out}'")
    r = sh("set -a; source ~/.hermes/.env; set +a; " + cmd)
    return os.path.exists(out) and os.path.getsize(out) > 0


def dur(path):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    sd = f"{P}/scenes"
    os.makedirs(sd, exist_ok=True)
    from collections import defaultdict

    #1. TTS
    for shot, vid, text, hl in LINES:
        mp3 = f"{sd}/{shot}-voice.mp3"
        if not os.path.exists(mp3):
            ok = tts(text, vid, mp3)
            print(f"  tts {shot}: {'OK' if ok else 'FAIL'} ({os.path.getsize(mp3) if os.path.exists(mp3) else 0}B)")
            if not ok: sys.exit(1)

    clips = []
    import re
    for shot, vid, text, hl in LINES:
        mp3 = f"{sd}/{shot}-voice.mp3"
        cap_json = f"{sd}/{shot}-cap.json"
        cap_ass = f"{sd}/{shot}.ass"
        # Strip [emotion] cues from CAPTION text (TTS keeps them for emotion control)
        cap_text = re.sub(r"^\[[^\]]+\]\s*", "", text)
        json.dump([{"text": cap_text, "highlight": hl, "mp3": mp3}],
                  open(cap_json, "w"), ensure_ascii=False)
        r = sh(f"PYTHONPATH={SK} python3 {SK}/sync_captions.py {cap_json} {cap_ass} --cap-y {CAP_Y[shot]}")
        if not os.path.exists(cap_ass):
            print(f"  caption FAIL {shot}"); sys.exit(1)

        out = f"{sd}/{shot}.mp4"
        px, py, z, mode = ZOOM[shot]
        beat = "snap" if shot == "shot-11" else "none"
        r = sh(f"python3 {SK}/build_scene.py {sd}/{shot}.png {mp3} {out} "
               f"--px {px} --py {py} --zoom {z} --mode {mode} --beat {beat} --ass {cap_ass}")
        print(f"  {shot}: {r.stdout.strip()[-80:] or r.stderr.strip()[-80:]}")
        clips.append(out)

    # concat + BGM
    concat_txt = f"{P}/concat.txt"
    with open(concat_txt, "w") as f:
        for c in clips: f.write(f"file '{c}'\n")
    final_raw = f"{P}/final-raw.mp4"
    sh(f"{FF} -v error -f concat -safe 0 -i {concat_txt} -c copy {final_raw} -y")

    bgm = "/home/mahmud/.hermes/cache/scratch/bgm-30s.mp3"
    final = f"{P}/final.mp4"
    sh(f"{FF} -v error -i {final_raw} -i {bgm} "
       f"-filter_complex \"[1:a]volume=0.12,atrim=0:30,asetpts=PTS-STARTPTS[bgm];"
       f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]\" "
       f"-map 0:v -map \"[aout]\" -c:v copy -c:a aac -shortest {final} -y")

    d = dur(final)
    print(f"FINAL: {final} duration={round(d,1)}s size={os.path.getsize(final)}B")


if __name__ == "__main__":
    main()
