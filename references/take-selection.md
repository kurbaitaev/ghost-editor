# Choosing takes from a multi-take recording

_Adapted from mariagorskikh/talking-head-reel (MIT, see UPSTREAM-LICENSE). In this skill the chosen takes go straight into `reel.json` → `takes`; there is no separate cut.py step._

People record the way people record: say a sentence, dislike it, say it
again, keep going when it lands, and restart the whole thing once they
have warmed up. So the recording is a script read two or three times
over, with the fluent versions towards the end, and the transcript table
is a map of it. The job is to pick one version of each sentence and lay
them back to back in script order.

## Procedure

1. Get the script the speaker meant to say (ask for it, or reconstruct it
   from the fullest take). Number its sentences.
2. Go down the whisper segment table and tag every segment with the
   sentence number it is a take of, or `x` for restarts, mutters ("okay,
   again"), and abandoned starts.
3. For each sentence, list its takes with their original seconds and pick:
   - the take that matches the script's meaning (not necessarily its
     words; the live wording is usually better);
   - fluent, no stumble inside the sentence, no filler the speaker would
     cut;
   - later over earlier, all else equal, because people warm up;
   - inside a run: when sentences 5, 6, 7, 8 come in one breath, take the
     run as one segment rather than the best of each, so the delivery
     stays continuous and there is one cut instead of four.
4. Splices from a different run are fine for one-liners (a joke, a call to
   action that landed only once) if the framing matches; the snap zoom at
   the cut hides small differences, a lighting change does not.
5. Cut points from WORD times (`transcribe.py`'s raw json, or `cut.py`'s
   table): `a` = first word start minus 0.10 to 0.15 s, `b` = last word end
   plus 0.20 to 0.30 s, never later than the start of the next spoken
   word. When a whisper word is suspiciously long (a "but" that lasts
   three seconds), the sound is somewhere inside it; find it with
   `ffmpeg -ss <t> -t <d> -i src -af silencedetect=noise=-32dB:d=0.25 -f null -`
   and start just before the last sound.
6. Pauses inside a take longer than about 1 s can be removed with a cut
   and a snap zoom. Pauses under 0.5 s stay; they are the speaker's
   rhythm.
7. Lines never said do not appear, not as captions, not as cards. If the
   script had a joke the speaker did not deliver, say so in the handover.

## Worked example (a fictional recording)

The script, sentence by sentence:

1. One thing nobody tells you about launching on GitHub.
2. We shipped in three weeks. Two founders, one laptop, zero designers.
3. I thought nobody would care. Then fifty people signed up on day one,
   and they found us on Instagram, X and LinkedIn.
4. What I would do differently: post before you feel ready, talk to every
   user, ship the boring version first.
5. Link below. Cheers.

The transcript table shows two runs: 0:00 to 0:33 and 0:45 to 1:05, the
second one after an "okay, again". Picks:

| # | chosen (original s) | why | rejected |
|---|---|---|---|
| 1, 2, 3 | 10.0 - 33.0, one run | fluent, the numbers land, the platform names are in one breath | 0.9 - 9.2: sentence 1 said twice with a restart in the middle |
| 4, 5 | 48.0 - 65.0, one run | the complete close, ends on "Cheers" | 33.4 - 44.8: sentence 4 without its last item, then "okay, again" |

Result: 2 takes, 40 s of speech, 3 s frozen outro. That is the cut in
`assets/reel-segments.example.json` and the timeline in
`assets/Reel.example.tsx`; the word timings in `reel-words.json` are
spread evenly over each sentence, which real whisper output is not, so
expect real beats to need the transcript table, not a guess.
