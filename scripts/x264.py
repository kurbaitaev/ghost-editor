"""The one x264 thread count every libx264 encode in the skill uses, so every Mac writes the same bytes.

The count lives in scripts/X264_THREADS (one line). x264 left on automatic threads uses 1.5 x the core count (12 on an
8-core MacBook Air, 15 on a 10-core Mac), and the thread count changes the bitstream: the same encode came out with a
different md5 on each machine. With a fixed -threads it was identical on both (measured 2026-10-16, ffmpeg 9.0.2,
x264 r3222). 12 is the 8-core Mac's old automatic count, so its files stay byte-identical to before, and about the
fastest on the 10-core one (8 was ~20 % slower there on preset slow).

    from x264 import THREADS as X264_THREADS
    ["-c:v", "libx264", "-threads", X264_THREADS, "-preset", "medium", ...]

Shell: -c:v libx264 -threads "$(cat "$S/scripts/X264_THREADS")". Keep -threads right after libx264: doctor.sh warns on
any libx264 encode without it. HyperFrames' own encodes get it from hf_ffmpeg.sh. Hardware encoders (h264_videotoolbox)
are not repeatable even on one Mac, so the skill does not use them.
"""
import os

THREADS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "X264_THREADS")).read().strip()
