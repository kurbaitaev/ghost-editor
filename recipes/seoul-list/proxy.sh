#!/usr/bin/env bash
# Seoul list: B-roll proxies for the montage.
#
#   bash proxy.sh OUTDIR CLIP [CLIP ...]
#
# Each clip becomes OUTDIR/<name>.mp4: 1080x1920, 30 fps CFR, H.264 CRF 18, bt709 tv range, no audio
# (the reel is VO-led; B-roll sound is never used). Rotation metadata is applied, full-range (yuvj)
# sources are converted, 50/60 fps sources drop to 30 by frame selection (no blending). Sources whose
# short side is under 1080 are refused (no 720p B-roll); pass ALLOW_LOW=1 to override knowingly.
# Proxy times equal source times, so an edit list can quote either. Existing proxies are kept unless
# FORCE=1. Run it on the machine that holds the footage; only OUTDIR needs copying anywhere else.
# HDR sources (iPhone HLG / PQ) are tone-mapped to SDR BT.709 (grade_lib.py sdr-vf), or one clip turns the whole render HDR.
# 23.976/24/25 fps sources get duplicated frames at 30 (judder) and a warning; RETIME=1 plays every source frame once
# instead (x1.2-1.25 speed; proxy time = source time x src_fps/30, written to <name>.json). Graded, retimed inserts for a
# real reel: scripts/insert_prep.py --ref <face plate> (references/broll.md).
set -euo pipefail
out="${1:?usage: proxy.sh OUTDIR CLIP [CLIP ...]}"; shift
mkdir -p "$out"
for src in "$@"; do
  name="$(basename "${src%.*}")"
  dst="$out/$name.mp4"
  if [ -s "$dst" ] && [ "${FORCE:-0}" != 1 ]; then echo "keep  $dst"; continue; fi
  w=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 "$src" | head -1)
  h=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 "$src" | head -1)
  short=$(( w < h ? w : h ))
  if [ "$short" -lt 1080 ] && [ "${ALLOW_LOW:-0}" != 1 ]; then echo "SKIP  $src: ${w}x${h} is below 1080p (ALLOW_LOW=1 to force)"; continue; fi
  fps=$(ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate -of csv=p=0 "$src" | head -1 | tr -d ',')
  fpsf=$(python3 -c "n,d='$fps'.split('/') if '/' in '$fps' else ('$fps','1'); print(round(float(n)/float(d),3))")
  pre="fps=30"
  if python3 -c "import sys; sys.exit(0 if 20 < $fpsf < 29.9 else 1)"; then
    if [ "${RETIME:-0}" = 1 ]; then pre="setpts=PTS*$fpsf/30,fps=30"; echo "{\"src_fps\": $fpsf, \"time_scale\": $(python3 -c "print(round($fpsf/30, 6))")}" > "$out/$name.json"
    else echo "warn  $src is $fpsf fps: duplicated frames at 30 (judder); RETIME=1 or insert_prep.py plays every frame once"; fi
  fi
  tr=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of csv=p=0 "$src" | head -1 | tr -d ',')
  hdr=""
  if [ "$tr" = "arib-std-b67" ] || [ "$tr" = "smpte2084" ]; then
    PY=python3; $PY -c "import numpy" 2>/dev/null || PY="$HOME/.venvs/media/bin/python"
    hdr="$("$PY" "$(cd "$(dirname "$0")/../../scripts" && pwd)/grade_lib.py" sdr-vf "$src" "$out/$name.sdr.cube"),"
    echo "hdr   $src ($tr): tone-mapped to SDR BT.709"
  fi
  ffmpeg -v error -y -i "$src" -an \
    -vf "${hdr}${pre},scale=1080:1920:force_original_aspect_ratio=increase:out_range=tv:flags=lanczos,crop=1080:1920,setsar=1,format=yuv420p" \
    -c:v libx264 -threads "$(cat "$(dirname "$0")/../../scripts/X264_THREADS")" -preset medium -crf 18 -g 30 -bf 2 -movflags +faststart \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv "$dst.tmp.mp4"
  mv "$dst.tmp.mp4" "$dst"
  # provenance sidecar (as insert_prep.py writes): broll_qa.py checks no posed stock models, own footage only the speaker
  PYK=python3; $PYK -c "import numpy" 2>/dev/null || PYK="$HOME/.venvs/media/bin/python"
  "$PYK" -c "import sys, json; sys.path.insert(0, sys.argv[3]); import grade_lib as G; json.dump({'src': sys.argv[1], 'kind': G.guess_kind(sys.argv[1]), 'in': 0.0}, open(sys.argv[2] + '.json', 'w'))" \
    "$(cd "$(dirname "$src")" && pwd)/$(basename "$src")" "$dst" "$(cd "$(dirname "$0")/../../scripts" && pwd)" 2>/dev/null || true
  printf "made  %s  %s frames\n" "$dst" "$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 "$dst")"
done
