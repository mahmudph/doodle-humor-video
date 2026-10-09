#!/usr/bin/env python3
"""Render antri-atm: 6 shot-per-line, caption strip, Ken Burns, BGM."""
import json, os, subprocess, sys, re

FF = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
FP = "/home/mahmud/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffprobe"
SK = "/home/mahmud/.hermes/skills/ink-doodle-humor-video/scripts"
P = "/home/mahmud/projects/doodle-humor-video/antri-atm"

V1 = "ab5b789ad6e14420afed2d454d4fc662"  # BAGAS
V2 = "ee65e2ec8bfc4883961761d581dff597"  # TIO

LINES = [
    ("shot-01", V1, "[frustrated] Udah setengah jam antre, pas mau cek saldo... eh.", None),
    ("shot-02", V1, "[shocked] Rp15.000?? Emang nggak transfer gaji tadi?", None),
    ("shot-03", V1, "[resigned] Maksudnya... uang gajian ya sudah akhir bulan.", None),
    ("shot-04", V1, "[anxious] Cuma buat beli mie instan aja nih...", None),
    ("shot-05", V2, "[cheerful] Yaudah, makan mie bareng aja, aku pulangin.", None),
    ("shot-06", V1, "[grateful] Tio, kamu paling good person di dunia ini.", "dunia ini"),
]

ZOOM = {
    "shot-01": (0.5, 0.40, 1.25, "in"),
    "shot-02": (0.5, 0.35, 1.30, "in"),
    "shot-03": (0.5, 0.35, 1.25, "in"),
    "shot-04": (0.5, 0.40, 1.30, "in"),
    "shot-05": (0.5, 0.45, 1.25, "in"),
    "shot-06": (0.5, 0.40, 1.35, "hold"),
}

CAP_Y = {"shot-06": 1820, "shot-05": 1830}
for s in ["shot-01","shot-02","shot-03","shot-04"]:
    CAP_Y[s] = 1850

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def dur(path):
    r = subprocess.run([FP,"-v","error","-show_entries","format=duration","-of","csv=p=0",path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    sd = f"{P}/scenes"
    for shot, vid, text, hl in LINES:
        mp3 = f"{sd}/{shot}-voice.mp3"
        if not os.path.exists(mp3) or os.path.getsize(mp3) < 1000:
            body = json.dumps({"text": text, "reference_id": vid, "format": "mp3"})
            cmd = ("curl -sS -X POST https://api.fish.audio/v1/tts "
                   '-H "Authorization: Bearer $FISH_API_KEY" -H "Content-Type: application/json" '
                   f'-H "model: $FISH_MODEL_ID" -d \'{body}\' --output \'{mp3}\'')
            r = sh("set -a; source ~/.hermes/.env; set +a; " + cmd)
            print(f"  tts {shot}: {'OK' if os.path.exists(mp3) and os.path.getsize(mp3)>1000 else 'FAIL'} ({os.path.getsize(mp3) if os.path.exists(mp3) else 0}B)")

    clips = []
    for shot, vid, text, hl in LINES:
        mp3 = f"{sd}/{shot}-voice.mp3"
        cap_json = f"{sd}/{shot}-cap.json"
        cap_ass  = f"{sd}/{shot}.ass"
        cap_text = re.sub(r"^\[[^\]]+\]\s*", "", text)
        json.dump([{"text": cap_text, "highlight": hl or cap_text.split()[-1], "mp3": mp3}],
                  open(cap_json,"w"), ensure_ascii=False)
        r = sh(f"PYTHONPATH={SK} python3 {SK}/sync_captions.py {cap_json} {cap_ass} --cap-y {CAP_Y[shot]}")
        if not os.path.exists(cap_ass):
            print(f"  caption FAIL {shot}: {r.stderr[-200:]}"); sys.exit(1)

        out = f"{sd}/{shot}.mp4"
        px, py, z, mode = ZOOM[shot]
        beat = "snap" if shot == "shot-06" else "none"
        r = sh(f"python3 {SK}/build_scene.py {sd}/{shot}.png {mp3} {out} "
               f"--px {px} --py {py} --zoom {z} --mode {mode} --beat {beat} --ass {cap_ass}")
        if not os.path.exists(out):
            print(f"  build FAIL {shot}: {r.stderr[-200:]}"); sys.exit(1)
        clips.append(out)
        print(f"  {shot}: mp4 {os.path.getsize(out)}B d={round(dur(out),2)}s")

    concat_txt = f"{P}/concat.txt"
    open(concat_txt,"w").writelines(f"file '{c}'\n" for c in clips)
    final_raw = f"{P}/final-raw.mp4"
    sh(f"{FF} -v error -f concat -safe 0 -i {concat_txt} -c copy {final_raw} -y")

    import glob
    bgms = sorted(glob.glob("/home/mahmud/.hermes/cache/scratch/bgm-*.mp3"))
    final = f"{P}/final.mp4"
    if bgms:
        sh(f"{FF} -v error -i {final_raw} -i {bgms[0]} "
           f'-filter_complex "[1:a]volume=0.12,atrim=0:30,asetpts=PTS-STARTPTS[bgm];'
           f'[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]" '
           '-map 0:v -map "[aout]" -c:v copy -c:a aac -shortest -y ' + final)
    else:
        sh(f"cp {final_raw} {final}")

    d = dur(final)
    print(f"FINAL: {final} duration={round(d,1)}s size={os.path.getsize(final)}B")

if __name__ == "__main__":
    main()
