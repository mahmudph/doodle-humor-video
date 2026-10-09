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
    ("shot-01", V1, "[frustrated] Udah setengah jam antre, semoga saldo gue masih aman...", "aman"),
    ("shot-02", V1, "[shocked] HAH?! Cuma lima belas ribu?!", "lima belas ribu"),
    ("shot-03", V1, "[resigned] Ya ampun, tanggal tua emang nggak pernah gagal bikin gue miskin.", "tanggal tua"),
    ("shot-04", V1, "[anxious] Duit segini cuma cukup buat beli mi instan. Telurnya? Ya, mimpi aja dulu.", "mimpi"),
    ("shot-05", V2, "[cheerful] Haha, udah, makan mi di rumah gue aja. Gue traktir!", "traktir"),
    ("shot-06", V1, "[cheerful] TIOOO! Mulai hari ini, separuh hartaku adalah milikmu!", "milikmu"),
    ("shot-07", V2, ".", "none"),
    ("shot-08", V2, "[calm] Gas, utang lu yang kemarin kapan dibayar?", "dibayar"),
    ("shot-09", V1, "[resigned] ...Persahabatan kita sedang diuji, Tio.", "diuji"),
]

ZOOM = {
    "shot-01": (0.5, 0.40, 1.25, "in"),
    "shot-02": (0.5, 0.35, 1.30, "in"),
    "shot-03": (0.5, 0.35, 1.25, "in"),
    "shot-04": (0.5, 0.40, 1.30, "in"),
    "shot-05": (0.5, 0.45, 1.25, "in"),
    "shot-06": (0.5, 0.40, 1.35, "in"),
    "shot-07": (0.5, 0.35, 1.15, "in"),
    "shot-08": (0.5, 0.35, 1.30, "in"),
    "shot-09": (0.5, 0.40, 1.35, "hold"),
}

CAP_Y = {f"shot-{i:02d}": 1850 for i in range(1, 10)}
CAP_Y["shot-05"] = 1830
CAP_Y["shot-09"] = 1820

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def dur(path):
    r = subprocess.run([FP,"-v","error","-show_entries","format=duration","-of","csv=p=0",path], capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    sd = f"{P}/scenes"
    for shot, vid, text, hl in LINES:
        mp3 = f"{sd}/{shot}-voice.mp3"
        if text == ".":
            if not os.path.exists(mp3):
                sh(f"{FF} -v error -f lavfi -i anullsrc=r=44100:cl=stereo -t 0.8 -q:a 5 -y {mp3}")
            print(f"  tts {shot}: SILENT 0.8s")
            continue
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
        silent = (text == ".")
        cap_text = re.sub(r"^\[[^\]]+\]\s*", "", text)
        if not silent:
            json.dump([{"text": cap_text, "highlight": hl or cap_text.split()[-1], "mp3": mp3}],
                      open(cap_json,"w"), ensure_ascii=False)
            r = sh(f"PYTHONPATH={SK} python3 {SK}/sync_captions.py {cap_json} {cap_ass} --cap-y {CAP_Y[shot]}")
            if not os.path.exists(cap_ass):
                print(f"  caption FAIL {shot}: {r.stderr[-200:]}"); sys.exit(1)

        out = f"{sd}/{shot}.mp4"
        px, py, z, mode = ZOOM[shot]
        beat = "snap" if shot == "shot-08" else ("hold-beat" if silent else "none")
        ass_arg = "" if silent else f" --ass {cap_ass}"
        r = sh(f"python3 {SK}/build_scene.py {sd}/{shot}.png {mp3} {out} "
               f"--px {px} --py {py} --zoom {z} --mode {mode} --beat {beat}{ass_arg}")
        if not os.path.exists(out):
            print(f"  build FAIL {shot}: {r.stderr[-200:]}"); sys.exit(1)
        clips.append(out)
        print(f"  {shot}: mp4 {os.path.getsize(out)}B d={round(dur(out),2)}s")

    concat_txt = f"{P}/concat.txt"
    open(concat_txt,"w").writelines(f"file '{c}'\n" for c in clips)
    final_raw = f"{P}/final-raw.mp4"
    sh(f"{FF} -v error -f concat -safe 0 -i {concat_txt} -c copy {final_raw} -y")

    ad = f"{P}/audio"
    import glob
    bgms = sorted(glob.glob("/home/mahmud/.hermes/cache/scratch/bgm-*.mp3"))
    final = f"{P}/final.mp4"

    # SFX placement from cumulative clip starts (verified ojol-hujan recipe)
    durs = [dur(c) for c in clips]
    starts = {}
    t = 0.0
    for (shot, *_), d_ in zip(LINES, durs):
        starts[shot] = int(t * 1000)
        t += d_
    total_ms = int(t * 1000)

    click = f"{ad}/sfx-click.mp3"       # receipt/ATM print at balance reveal (shot-02)
    trom = f"{ad}/sfx-trombone.mp3"     # sad trombone at punchline (shot-08)
    have_click = os.path.exists(click)
    have_trom  = os.path.exists(trom)
    n_in = 2 + have_click + have_trom

    fc = [f"[1:a]volume=0.12,atrim=0:{round(t)},asetpts=PTS-STARTPTS[bgm]"]
    idx = 2
    labels = ["[0:a]", "[bgm]"]
    if have_click:
        fc.append(f"[{idx}:a]adelay={starts.get('shot-02',0)}|{starts.get('shot-02',0)},volume=0.7[click]")
        labels.append("[click]"); idx += 1
    if have_trom:
        fc.append(f"[{idx}:a]adelay={starts.get('shot-08',0)}|{starts.get('shot-08',0)},volume=0.5[trom]")
        labels.append("[trom]"); idx += 1
    fc.append("".join(labels) + f"amix=inputs={n_in}:duration=first:dropout_transition=0[aout]")
    inputs = f"-i {bgms[0]}" if bgms else "-f lavfi -i anullsrc=r=44100:cl=stereo"
    inputs += (f" -i {click}" if have_click else "") + (f" -i {trom}" if have_trom else "")
    sh(f"{FF} -v error -i {final_raw} {inputs} "
       f'-filter_complex "{";".join(fc)}" '
       '-map 0:v -map "[aout]" -c:v copy -c:a aac -shortest -y ' + final)

    d = dur(final)
    print(f"FINAL: {final} duration={round(d,1)}s size={os.path.getsize(final)}B")

if __name__ == "__main__":
    main()
