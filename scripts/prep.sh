#!/usr/bin/env bash
# Transcode a phone recording into the reel's source: 1080x1920, 30 fps,
# H.264, with the VOICE loudness-normalized to -16 LUFS (two-pass loudnorm).
#
#   prep.sh <recording> <project-dir>        -> <project>/assets/talk.mp4
#
# Normalizing the voice here, before any SFX is mixed, is what keeps the SFX
# levels in build.mjs meaningful: the kit's role levels assume a -16 LUFS
# voice. The old pipeline lifted the finished mix instead, so every SFX got
# +10 dB and hit the limiter.
#
# A portrait phone file is a landscape HEVC stream with a rotation tag;
# ffmpeg rotates before the filter graph, so the target is 1080:1920. A
# landscape source is centre-cropped to 9:16. An HDR source (iPhone HLG / PQ, BT.2020) is tone-mapped to SDR BT.709
# first (grade_lib.py sdr-vf: a LUT, since this ffmpeg has no zscale): one HDR plate would make the whole HyperFrames
# render HDR. Keyframes every 1 s (-g 30): HyperFrames seeks every plate on every frame.
set -euo pipefail
[ "$#" -eq 2 ] || { echo "usage: prep.sh <recording> <project-dir>" >&2; exit 2; }
src="$1"; proj="$2"; out="$proj/assets/talk.mp4"
mkdir -p "$proj/assets"

read -r w h < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$src" | tr -d '\r' | tr ',' ' ')
rot=$(ffprobe -v error -select_streams v:0 -show_entries stream_side_data=rotation -of csv=p=0 "$src" | head -1 | tr -d ' ,\r-')
if [ "${rot:-0}" = "90" ] || [ "${rot:-0}" = "270" ]; then t=$w; w=$h; h=$t; fi
echo "source ${w}x${h} (rotation ${rot:-none}), $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src") s"
if [ "$w" -lt "$h" ]; then vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30"
else vf="crop=ih*9/16:ih,scale=1080:1920,fps=30"; echo "landscape source: centre-cropping to 9:16"; fi

HERE="$(cd "$(dirname "$0")" && pwd)"
tr=$(ffprobe -v error -select_streams v:0 -show_entries stream=color_transfer -of csv=p=0 "$src" | head -1 | tr -d ',\r')
if [ "$tr" = "arib-std-b67" ] || [ "$tr" = "smpte2084" ]; then
  PY=python3; $PY -c "import numpy" 2>/dev/null || PY="$HOME/.venvs/media/bin/python"
  "$PY" -c "import numpy" 2>/dev/null || { echo "HDR source ($tr): tone-mapping needs python with numpy (set PATH or ~/.venvs/media)" >&2; exit 1; }
  mkdir -p "$proj/build"
  vf="$("$PY" "$HERE/grade_lib.py" sdr-vf "$src" "$proj/build/sdr.cube"),$vf"
  echo "HDR source ($tr): tone-mapped to SDR BT.709 (build/sdr.cube)"
fi

echo "== measuring voice loudness"
stats=$(ffmpeg -hide_banner -nostats -i "$src" -vn -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
g() { echo "$stats" | python3 -c "import json,sys;print(json.load(sys.stdin)['$1'])"; }
echo "input: $(g input_i) LUFS, true peak $(g input_tp) dBTP"
af="loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,aresample=48000"

# Hardware H.264 where one actually works (Apple VideoToolbox, NVIDIA, Intel QSV, AMD AMF): ffmpeg lists every encoder
# it was built with, so each is tried on one test frame. Otherwise libx264 (several times slower on a 4K source).
enc=(-c:v libx264 -crf 17 -preset fast)
for hw in h264_videotoolbox h264_nvenc h264_qsv h264_amf; do
  if ffmpeg -v error -f lavfi -i testsrc=size=1080x1920:rate=30 -frames:v 1 -c:v "$hw" -b:v 14M -f null - >/dev/null 2>&1; then
    enc=(-c:v "$hw" -b:v 14M); echo "encoder: $hw"; break
  fi
done
ffmpeg -v error -y -i "$src" -vf "$vf" "${enc[@]}" -pix_fmt yuv420p -g 30 -keyint_min 30 \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -af "$af" -c:a aac -b:a 192k -ac 2 -movflags +faststart "$out"
echo "-> $out"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 "$out"
ffmpeg -hide_banner -nostats -i "$out" -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | sed 's/^/output voice /'
