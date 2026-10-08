#!/usr/bin/env python3
"""Best take per script line (source seconds), then remove pauses inside each take
using the audio (silencedetect), keeping small pads. -> build/takes.json"""
import json, re, subprocess
SRC = "build/proxy.mp4"
LINES = [  # (a, b, text) - last clean take of each line
    (16.45, 19.3, "Миллениалы вечно ностальгируют. Конечно!"),
    (51.4, 57.8, "Мы застали мир до того, как всё стало подпиской, алгоритмом или ежемесячным платежом."),
    (66.45, 70.4, "Над нами смеются за то, что мы скучаем по прошлому? А как иначе?"),
    (77.55, 81.25, "Мы помним, когда встречи с друзьями ещё не были контентом."),
    (85.4, 89.5, "Когда фотографии делали на память, а не в доказательство того, что ты где-то был."),
    (94.2, 97.3, "Когда в интернет заходили, а не жили в нём."),
    (107.1, 111.6, "Мы как будто успели пожить в нескольких разных версиях мира."),
    (123.8, 128.2, "Сначала можно было просто пойти гулять и вернуться домой, когда стемнеет."),
    (157.6, 163.9, "Потом пришлось разбираться с электронной почтой. ВК, Mail.ru, Instagram, TikTok."),
    (169.2, 172.5, "А теперь чуть ли не каждому холодильнику нужен Wi-Fi."),
    (176.2, 180.8, "Сначала был домашний телефон, потом раскладушка, потом смартфон."),
    (208.45, 214.3, "А теперь телефон сам редактирует фотографии, отвечает на вопросы и ругает тебя за то, сколько времени ты в нём сидишь."),
    (219.05, 221.3, "Мы ещё учились красиво писать от руки."),
    (223.6, 227.8, "Как будто потом нам сказали: «А, ладно, всё, уже не надо»."),
    (237.45, 242.0, "Я помню, как мы запоминали номера телефонов. А теперь даже трубку не хотим поднимать."),
    (261.7, 265.2, "Помню, как таксисты смотрели маршрут на распечатанной карте."),
    (271.3, 274.9, "Один неправильный поворот, и всё. Приходилось вместе разбираться."),
    (290.4, 295.9, "Мы пережили столько обновлений, что за словами «у нас новая функция» слышится:"),
    (304.1, 308.5, "«Тебе снова придётся во всём разбираться. А потом ещё объяснять другим»."),
    (315.7, 318.5, "Мы ностальгируем не потому, что состарились."),
    (327.3, 330.6, "А потому, что каждые несколько лет нам приходится заново учиться жить."),
]
NOISE, MIN_SIL, PAD = -34, 0.7, 0.12
takes = []
for a, b, text in LINES:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", str(a), "-t", str(b - a), "-i", SRC, "-vn",
                          "-af", f"silencedetect=noise={NOISE}dB:d={MIN_SIL}", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    sil = list(zip(st, en + [b - a] * (len(st) - len(en))))
    # speech = complement of silences
    keep, t = [], 0.0
    for s0, s1 in sil:
        if s0 > t: keep.append((t, s0))
        t = max(t, s1)
    if t < b - a: keep.append((t, b - a))
    parts = [(round(a + max(0, k0 - PAD), 3), round(a + min(b - a, k1 + PAD), 3)) for k0, k1 in keep if k1 - k0 > 0.12]
    # merge parts closer than 2*PAD
    merged = []
    for p in parts:
        if merged and p[0] - merged[-1][1] < 0.06: merged[-1] = (merged[-1][0], p[1])
        else: merged.append(p)
    # breaths before a line: start the line at the voice onset (RMS > -30 dB for 30 ms), not at the padded edge
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(merged[0][0]), "-t", "2.2", "-i", SRC, "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    import array, math
    smp = array.array("h", raw); win = 80; run = 0; onset = None
    for i in range(0, len(smp) - win, win):
        rms = math.sqrt(sum(x * x for x in smp[i:i + win]) / win) or 1
        run = run + 1 if 20 * math.log10(rms / 32768) > -30 else 0
        if run >= 3: onset = (i - 2 * win) / 8000; break
    if onset is not None and 0.08 < onset < min(1.8, merged[0][1] - merged[0][0] - 0.25):
        merged[0] = (round(merged[0][0] + onset - 0.07, 3), merged[0][1])
    # quiet word endings sit under the threshold: give the last part of a line a longer tail
    merged[-1] = (merged[-1][0], round(min(b, merged[-1][1] + 0.12), 3))
    takes.append({"text": text, "parts": merged, "dur": round(sum(q - p for p, q in merged), 2)})
    print(f"{a:6.1f}-{b:6.1f}  {len(merged)} parts {takes[-1]['dur']:5.2f}s  {text[:60]}")
json.dump(takes, open("build/takes.json", "w"), ensure_ascii=False, indent=1)
print("total speech", round(sum(t['dur'] for t in takes), 1), "s,", sum(len(t['parts']) for t in takes), "cuts")
