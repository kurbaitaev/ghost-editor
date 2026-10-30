"""Run HyperFrames' audio mix with its inputs in a fixed order (called by hf_ffmpeg.sh; stdlib only).

HyperFrames (0.8.159, engine audioMixer.ts) prepares every audio track at once (Promise.all) and appends each to the mix
list when its ffmpeg prep finishes, so the amix input order changes from render to render. The float sum then differs
only by rounding (~-155 dB, wherever 3+ tracks sound together), but the AAC encoder turns that into a different stream
(~-33 dB apart), and the true-peak guard after it (ebur128 in 0.1 dB steps against -1 dBTP) lowers some renders by
0.6 dB and not others. Here the inputs are sorted by file name (<element id>-trimmed.wav and the like) and the graph
is written to a new file beside HyperFrames' own (HyperFrames deletes that temp folder after the mix). Any call that
does not look exactly like that mix runs unchanged.

    hf_mix_order.py <real ffmpeg> <ffmpeg args...>
"""
import os
import re
import sys

real, args = sys.argv[1], sys.argv[2:]


def ordered(a):
    k = next(i for i, x in enumerate(a) if x in ("-/filter_complex", "-filter_complex_script"))
    path = a[k + 1]
    graph = open(path).read()
    if "amix=inputs=" not in graph:
        return None
    pos = [i + 1 for i, x in enumerate(a[:-1]) if x == "-i"]
    src = [a[i] for i in pos]
    n = len(src)
    chains, rest = {}, []
    for part in graph.split(";"):
        m = re.fullmatch(r"\[(\d+):a\]([^\[\]]*)\[a(\d+)\]", part)
        if m and m.group(1) == m.group(3):
            chains[int(m.group(1))] = m.group(2)
        else:
            rest.append(part)
    labels = "".join(f"[a{i}]" for i in range(n))
    if sorted(chains) != list(range(n)) or not any(p.startswith(f"{labels}amix=inputs={n}:") for p in rest):
        return None
    order = sorted(range(n), key=lambda i: (os.path.basename(src[i]), src[i]))
    if order == list(range(n)):
        return None
    out = os.path.join(os.path.dirname(path), "graph.ordered.txt")
    with open(out, "w") as f:
        f.write(";".join([f"[{j}:a]{chains[i]}[a{j}]" for j, i in enumerate(order)] + rest))
    b = list(a)
    for j, i in enumerate(order):
        b[pos[j]] = src[i]
    b[k + 1] = out
    log = os.environ.get("HF_MIX_ORDER_LOG")
    if log:
        with open(log, "a") as f:
            f.write(f"{n} inputs: " + " ".join(os.path.basename(src[i]) for i in order) + "\n")
    return b


try:
    b = ordered(args)
except Exception:
    b = None
os.execv(real, [real] + (b or args))
