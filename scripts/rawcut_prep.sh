#!/usr/bin/env bash
# Raw-cut inputs from one phone recording (step 0 of references/take-selection.md "The raw cut, step by step").
#
#   rawcut_prep.sh <recording.MOV> <project-dir> [--gem]
#
#   build/full.wav   48 kHz mono PCM: plan_cut.py, subcheck.py and voice_smooth.py cut the voice from it
#   build/a16.wav    16 kHz mono PCM: vad_pauses.py and islands_tx.py
#   build/proxy.mp4  1080x1920 H.264, FRAME FOR FRAME with the recording (no fps change): facescan.py reads row i = frame i
#                    and --pts puts the recording's true frame times on the rows, so a dropped or added frame would shift
#                    every face flag after it. The script checks the frame count and exits 1 on a mismatch.
#   build/gem.mp4    with --gem: 540x960 copy for Gemini uploads (gem_audit.py makes its own when this is missing)
#
# Apple Silicon: decode, rotate and scale on the GPU (VideoToolbox), ~4x faster on a 4K HEVC clip; otherwise CPU.
# The picture is not tone-mapped or graded: the proxy is for analysis, the plates come from the recording itself
# (assemble.py --plan).
# The encode is libx264 with the fixed thread count either way (scripts/x264.py): the GPU decode and scale give the same
# frames on both Macs, VideoToolbox's encoder gives a different file on every run.
set -euo pipefail
usage() { sed -n 2,15p "$0" | sed 's/^# \{0,1\}//'; }
case "${1:-}" in -h|--help) usage; exit 0;; esac
[ "$#" -ge 2 ] || { usage; exit 2; }
src="$1"; proj="$2"; gem=0; [ "${3:-}" = "--gem" ] && gem=1
x264=(-c:v libx264 -threads "$(cat "$(dirname "$0")/X264_THREADS")")
[ -f "$src" ] || { echo "no such recording: $src" >&2; exit 1; }
B="$proj/build"; mkdir -p "$B"
src=$(cd "$(dirname "$src")" && pwd)/$(basename "$src")

read -r w h < <(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$src" | tr ',' ' ')
rot=$(ffprobe -v error -select_streams v:0 -show_entries stream_side_data=rotation -of csv=p=0 "$src" | head -1 | tr -d ', ')
case "${rot:-0}" in -90|270) dir=clock; t=$w; w=$h; h=$t;; 90|-270) dir=cclock; t=$w; w=$h; h=$t;; 180|-180) dir=reversal;; *) dir="";; esac
if [ "$w" -lt "$h" ]; then W=1080; H=1920; else W=1920; H=1080; fi
frames() { ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$1" | tr -d ',' | sed -n 1p; }
want=$(frames "$src")
echo "source ${w}x${h} (rotation ${rot:-none}), $want frames, $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src") s"

ffmpeg -v error -y -i "$src" -vn -ac 1 -ar 48000 -c:a pcm_s16le "$B/full.wav"
ffmpeg -v error -y -i "$B/full.wav" -ac 1 -ar 16000 -c:a pcm_s16le "$B/a16.wav"
echo "-> build/full.wav, build/a16.wav ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$B/full.wav") s)"

gpu=0
if ffmpeg -hide_banner -filters 2>/dev/null | grep -q transpose_vt; then
  vf="${dir:+transpose_vt=dir=$dir,}scale_vt=$W:$H,hwdownload,format=nv12"
  ffmpeg -v error -y -display_rotation:v:0 0 -hwaccel videotoolbox -hwaccel_output_format videotoolbox_vld -i "$src" \
    -vf "$vf" -fps_mode passthrough "${x264[@]}" -crf 20 -preset veryfast -c:a aac -b:a 192k -movflags +faststart "$B/proxy.mp4" && gpu=1 \
    || echo "VideoToolbox path failed; CPU decode"
fi
if [ "$gpu" = 0 ]; then
  ffmpeg -v error -y -i "$src" -vf "scale=$W:$H:flags=bicubic,format=yuv420p" -fps_mode passthrough \
    "${x264[@]}" -crf 20 -preset veryfast -c:a aac -b:a 192k -movflags +faststart "$B/proxy.mp4"
fi
got=$(frames "$B/proxy.mp4")
echo "-> build/proxy.mp4 ${W}x${H}, $got frames ($([ $gpu = 1 ] && echo GPU || echo CPU))"
[ "$got" = "$want" ] || { echo "FRAME COUNT MISMATCH: proxy $got, recording $want (facescan rows would drift)" >&2; exit 1; }

if [ "$gem" = 1 ]; then
  ffmpeg -v error -y -i "$B/proxy.mp4" -vf scale=$((W / 2)):$((H / 2)) "${x264[@]}" -crf 28 -preset veryfast \
    -c:a aac -b:a 96k -ac 1 -movflags +faststart "$B/gem.mp4"
  echo "-> build/gem.mp4"
fi
echo "cut.json \"source\": \"$src\""
