# OPUS — Motion Studies

A 16-second Swiss / editorial motion-design showreel made entirely by code:
sample-based drums plus a software synth (Surge XT, VST3) through VST effects for the
soundtrack, Blender for two glossy 3D objects, skia-python for every flat graphic, and
ffmpeg for the edit.

**Output:** [`out/OPUS_motion_16s.mp4`](out/OPUS_motion_16s.mp4) · 1920×1080 · 30 fps · 16.0 s ·
H.264 + AAC. Also in `out/`: `opus_soundtrack.wav` (24-bit, −12 LUFS, −1 dBTP), ten poster
stills and `CREDITS.txt`.

## The film

120 BPM, so one beat is exactly 15 frames. There are ten compositions; each cut lands on
the beat and each transition is made from something already on screen.

| # | beats | composition | palette | transition out |
|---|---|---|---|---|
| 01 POINT | 0–4 | a red point generates the 12-column grid; GRID revealed column by column | paper · black · red | the point becomes a circle wipe |
| 02 MOTION | 4–7 | seven stepped, stretching rows of MOTION collapse into one | red · black · paper | its O zooms into… |
| 03 RADIAL | 7–10 | …a ring → disk, 48-ray burst, orbiting nodes, type on a circle, halftone wave | cobalt · paper | halftone gaps grow into black bars |
| 04 RHYTHM | 10–12 | letter widths and heights driven by drum hits and the spectrum | black · paper · lime | stutter, then the word collapses into a line |
| 05 FORM | 12–16 | **chrome twisted torus** (Blender) on a cobalt disc; FORM flips on the beat | paper · black · cobalt | the torus faces camera; its hole irises open |
| 06 TYPE | 16–19 | variable-font specimen: weight morphs 900↔180, glyph flips | red · paper · black | the specimen's "+" becomes a cross wipe |
| 07 SIGN | 19–22 | rippling field of rotating crosses and stars, asterisk, bass-driven sine | black · red · paper | cross arms extend into stripes |
| 08 WAVE | 22–24 | wave field with WAVE riding it, filter-sweep burst | cobalt · paper · lime | lines straighten and thicken; their gaps become… |
| 09 LENS | 24–28 | …the rules behind a **glass sphere** that refracts the real layout (Cycles) | paper · cobalt · black | rules cascade to black; the sphere shrinks into… |
| 10 OPUS | 28–32 | …the red period of OPUS.; letters drop in on the hits; the index locks up | black · paper · red | — |

A thin interface layer runs over everything: timecode, bar.beat counter, a 32-beat ruler,
page numbers, registration marks and tiny figure captions. Post-processing is kept
restrained: 5-subframe motion blur (180° shutter), highlight-only bloom, 0.07–0.4 %
chromatic aberration (pushed by the impacts), a subtle vignette and midtone film grain.

## Pipeline

```
src/config.py        tempo, format, palette, scene table          (single source of truth)
src/timeline.py      every musical / visual event -> $OPUS_BUILD/timeline.json
src/layout.py        12-col grid + anchors shared by Blender and skia
src/audio/           plugin_state.py (JUCE VST3 state / Surge sub3 patches), surge.py,
                     dsp.py, make_music.py  -> out/opus_soundtrack.wav, analysis.npz
src/blender/         build_scene.py (new scenes OPUS_CHROME / OPUS_GLASS), render_3d.py
src/gfx/             draw.py (fonts, easing, text), scenes.py (10 compositions), compose.py
tools/               viz_audio.py, sheet.py, qa_luma.py (flash check), qa_sync.py (A/V sync)
scene/opus_scene.blend
```

Run it:

```bash
src/setup_tools.sh          # builds _temp_install/ (venv, plugins, samples, fonts, ffmpeg)
src/render_all.sh all       # or: audio | plates | scene | 3d | 2d | encode | qa
```

Order matters: audio (writes the analysis the visuals react to) → S9 plates (the 2D
backdrop the glass refracts) → Blender scene → 3D renders → 2D composite → encode → QA.
Heavy intermediates go to `$OPUS_BUILD` (the session scratchpad by default).

## Notes

- Made in a headless Linux cloud container, not on macOS. So Blender is the official
  `bpy` 5.1.1 module (Blender as a Python module, driven from the command line), with no
  GUI and no Blender MCP. The Linux builds of the plugins came from their GitHub releases.
  The macOS-only steps (dmg mounting, `~/.Trash`, sandbox escalation) didn't apply.
- pedalboard 0.9.25 crashes on this CPU (AVX512-FP16 in a static initialiser), so it is
  pinned to 0.9.24.
- skia-python needs `libEGL.so.1`. It is extracted from the Ubuntu deb into
  `_temp_install/syslibs` rather than installed system-wide.
- The audio was checked numerically and visually (LUFS per section, stem RMS,
  spectrogram), not by ear.
