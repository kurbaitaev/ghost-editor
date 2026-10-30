#!/usr/bin/env bash
# The ffmpeg finals.py's no-music render runs (HYPERFRAMES_FFMPEG_PATH, nomusic() only): hf_ffmpeg.sh unchanged, plus,
# once HyperFrames' audio mix has succeeded, the same mix again to 32-bit float PCM at $HF_MIX_PCM.
# Why: HyperFrames encodes its mix straight to AAC 192k, and ffmpeg's AAC encoder overshoots a hard transient at the
# very start of a stream (a frame-0 boom measured -17.4 dBFS in the mix, -12.4 after one AAC pass, -4.5 after
# the three passes of a final). From the PCM the no-music version gets a single AAC pass, at delivery.
here="$(cd "$(dirname "$0")" && pwd)"
case " $* " in
  *" -/filter_complex "* | *" -filter_complex_script "*)
    "$here/hf_ffmpeg.sh" "$@"; rc=$?
    if [ "$rc" = 0 ] && [ -n "$HF_MIX_PCM" ] && [ ! -f "$HF_MIX_PCM" ]; then
      a=(); skip=0; i=0
      for x in "$@"; do
        i=$((i+1))
        if [ "$skip" = 1 ]; then skip=0; continue; fi
        case "$x" in -acodec | -c:a | -b:a) skip=1; continue ;; esac
        [ "$i" = "$#" ] && continue                      # HyperFrames' own output (the last argument)
        a+=("$x")
      done
      "$here/hf_ffmpeg.sh" "${a[@]}" -acodec pcm_f32le "$HF_MIX_PCM" > /dev/null 2>&1 || rm -f "$HF_MIX_PCM"
    fi
    exit $rc ;;
esac
exec "$here/hf_ffmpeg.sh" "$@"
