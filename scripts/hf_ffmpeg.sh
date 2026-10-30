#!/usr/bin/env bash
# The ffmpeg HyperFrames runs (HYPERFRAMES_FFMPEG_PATH, set by hf.sh and hf_version.py). Every call goes
# straight to the real ffmpeg except HyperFrames' audio mix, which hf_mix_order.py first puts in a fixed input order:
# HyperFrames lists the mix inputs in the order their prep happened to finish, so one reel came out with a different
# AAC stream, and sometimes 0.6 dB quieter, on every render. Details in hf_mix_order.py.
# HyperFrames' libx264 encodes (the render, its cfr pass, video proxies) set no thread count, and x264's automatic one
# follows the core count, so each Mac wrote different bytes: -threads from scripts/X264_THREADS goes in after every
# libx264 (why: x264.py).
here="$(cd "$(dirname "$0")" && pwd)"
t="$(cat "$here/X264_THREADS")"
a=(); prev=""
for x in "$@"; do
  a+=("$x")
  case "$prev" in -c:v* | -vcodec | -codec:v* | -c | -codec) [ "$x" = libx264 ] && a+=(-threads "$t") ;; esac
  prev="$x"
done
set -- "${a[@]}"
real="${HF_REAL_FFMPEG:-$(command -v ffmpeg)}"
[ -n "$real" ] || { echo "hf_ffmpeg.sh: ffmpeg not found on PATH (brew install ffmpeg)" >&2; exit 127; }
py="$(command -v python3)"
case " $* " in
  *" -/filter_complex "* | *" -filter_complex_script "*)
    [ -n "$py" ] && exec "$py" -I "$here/hf_mix_order.py" "$real" "$@" ;;
esac
exec "$real" "$@"
