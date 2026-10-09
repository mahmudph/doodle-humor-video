#!/usr/bin/env python3
"""Full render pipeline for anak-kos-mie video."""
import json, os, subprocess, sys

FF = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
FP = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffprobe"
SK = "/home/mahmud/.hermes/skills/ink-doodle-humor-video/scripts"
P = "/home/mahmud/projects/doodle-humor-video/anak-kos-mie"
V1 = "ab5b789ad6e14420afed2d454d4fc662"   # BAGAS
V2 = "ee65e2ec8bfc4883961761d581dff597"   # TIO

LINES = [
    ("scene-01", V1, "Guys, tutorial mie hemat satu bungkus tiga kali makan.", "hemat"),
    ("scene-02", V2, "Airnya dikit amat, mateng kagak tuh?", "dikit"),
    ("scene-02", V1, "Irit gas, bro. Air dikit mateng cepet.", "Irit"),
    ("scene-03", V2, "Terus kenapa mie-nya lu remas-remas?", "remas-remas"),
    ("scene-03", V1, "Biar muat panci kecil, biar hemat juga.", "hemat"),
    ("scene-04", V2, "Bumbu kenapa cuma setengah?", "setengah"),
    ("scene-04", V1, "Setengah sekarang, setengah buat besok.", "besok"),
    ("scene-05", V1, "Loh kok mati? Mie-nya kurang air ya?", "mati"),
    ("scene-05", V2, "Gasnya habis dari kemarin, bro.", "habis"),
    ("scene-06", V1, "Jadi yang habis bukan mie gue...", "habis"),
    ("scene-06", V2, "Gaya hemat lu yang habis duluan.", "habis"),
]

CAP_Y = {"scene-01":1850,"scene-02":1870,"scene-03":1850,"scene-04":1870,"scene-05":1850,"scene-06":1850}
TARGET = {"scene-01":(0.50,0.32),"scene-02":(0.45,0.35),"scene-03":(0.50,0.32),"scene-04":(0.48,0.35),"scene-05":(0.50,0.32),"scene-06":(0.50,0.35)}
MODE = {"scene-01":"in","scene-02":"out","scene-03":"in","scene-04":"out","scene-05":"hold","scene-06":"hold"}
BEAT = {"scene-01":"none","scene-02":"none","scene-03":"none","scene-04":"none","scene-05":"shake","scene-06":"snap"}


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

    #1. TTS per line
    from collections import defaultdict
    spec = []
    scene_counts = defaultdict(int)
    for scene, vid, text, hl in LINES:
        scene_counts[scene] += 1
        mp3 = f"{sd}/{scene}-line-{scene_counts[scene]}.mp3"
        if not os.path.exists(mp3):
            ok = tts(text, vid, mp3)
            print(f"  tts {os.path.basename(mp3)}: {'OK' if ok else 'FAIL'} ({os.path.getsize(mp3) if os.path.exists(mp3) else 0}B)")
            if not ok: sys.exit(1)
        spec.append({"text": text, "highlight": hl, "mp3": mp3})

    #2. Group by scene → per-scene captions + clips
    by_scene = defaultdict(list)
    for s in spec: by_scene[s["mp3"].split("-line-")[0].split("/")[-1]].append(s)

    clips = []
    for scene in ["scene-01","scene-02","scene-03","scene-04","scene-05","scene-06"]:
        lines = by_scene[scene]
        cap_json = f"{sd}/{scene}-cap.json"
        cap_ass = f"{sd}/{scene}.ass"
        json.dump(lines, open(cap_json, "w"), ensure_ascii=False)
        r = sh(f"PYTHONPATH={SK} python3 {SK}/sync_captions.py {cap_json} {cap_ass} --cap-y {CAP_Y[scene]}")
        if not os.path.exists(cap_ass):
            print(f"  caption FAIL for {scene}: {r.stderr[-200:]}"); sys.exit(1)

        # combine voice lines into single audio (concat mp3s)
        concat_txt = f"{sd}/{scene}-concat.txt"
        with open(concat_txt, "w") as f:
            for l in lines: f.write(f"file '{l['mp3']}'\n")
        combined = f"{sd}/{scene}-voice.mp3"
        sh(f"{FF} -v error -f concat -safe 0 -i {concat_txt} -c copy {combined} -y")

        out = f"{sd}/{scene}.mp4"
        px, py = TARGET[scene]
        r = sh(f"python3 {SK}/build_scene.py {sd}/{scene}.png {combined} {out} "
               f"--px {px} --py {py} --zoom 1.25 --mode {MODE[scene]} --beat {BEAT[scene]} --ass {cap_ass}")
        print(f"  {scene}: {r.stdout.strip()[-120:] or r.stderr.strip()[-120:]}")
        clips.append(out)

    #3. concat all scenes
    concat_final = f"{P}/concat.txt"
    with open(concat_final, "w") as f:
        for c in clips: f.write(f"file '{c}'\n")
    final = f"{P}/final.mp4"
    sh(f"{FF} -v error -f concat -safe 0 -i {concat_final} -c copy {final} -y")
    d = dur(final)
    print(f"FINAL: {final} duration={d}s size={os.path.getsize(final)}B")


if __name__ == "__main__":
    main()
