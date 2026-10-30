#!/usr/bin/env bash
# The pinned HyperFrames CLI: `$S/scripts/hf.sh render -o build/reel.mp4` = npx -y hyperframes@<scripts/HF_VERSION> ...
# An HF_VERSION environment variable overrides the file for a one-off test (doctor.sh warns while it is set).
# HyperFrames runs ffmpeg through hf_ffmpeg.sh, which fixes the audio mix's input order (why: hf_mix_order.py).
v="${HF_VERSION:-$(cat "$(dirname "$0")/HF_VERSION")}"
export HYPERFRAMES_FFMPEG_PATH="${HYPERFRAMES_FFMPEG_PATH:-$(cd "$(dirname "$0")" && pwd)/hf_ffmpeg.sh}"
exec npx -y "hyperframes@$v" "$@"
