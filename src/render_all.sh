#!/usr/bin/env bash
# Stage runner:  src/render_all.sh [audio|plates|scene|3d|2d|encode|qa|all]
# Heavy intermediates live in $OPUS_BUILD (default: the session scratchpad, see env.sh).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$OPUS_ROOT"
stage="${1:-all}"
WORKERS="${WORKERS:-4}"

audio() {   # Surge XT etc. write their user data under $HOME: keep it inside _temp_install
  HOME="$OPUS_TOOLS/home" "$OPUS_PY" src/audio/make_music.py
  "$OPUS_PY" tools/viz_audio.py
}
plates() { "$OPUS_PY" src/gfx/compose.py --plates 352-424 --workers "$WORKERS"; }
scene() { OPUS_SAVE="$OPUS_ROOT/scene/opus_scene.blend" "$OPUS_PY" src/blender/build_scene.py; }
render3d() {
  "$OPUS_PY" src/blender/render_3d.py --scene OPUS_CHROME --start 176 --end 241 --samples 96 \
      --out "$OPUS_BUILD/frames3d/chrome_####" "$@"
  "$OPUS_PY" src/blender/render_3d.py --scene OPUS_GLASS --start 358 --end 420 --border-track glass \
      --out "$OPUS_BUILD/frames3d/glass_####" "$@"
}
comp2d() { "$OPUS_PY" src/gfx/compose.py --all --workers "$WORKERS"; }
encode() {
  ffmpeg -y -v error -framerate 30 -i "$OPUS_BUILD/comp/c_%04d.png" -i out/opus_soundtrack.wav \
    -vf "scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p" \
    -c:v libx264 -preset slow -crf 17 -profile:v high -tune film \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
    -c:a aac -b:a 320k -ar 48000 -shortest -movflags +faststart out/OPUS_motion_16s.mp4
  ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,color_space,sample_rate,channels:format=duration,bit_rate \
    -of compact out/OPUS_motion_16s.mp4
}
qa() { "$OPUS_PY" tools/qa_luma.py; "$OPUS_PY" tools/qa_sync.py; }

case "$stage" in
  audio) audio ;; plates) plates ;; scene) scene ;; 3d) render3d --skip-existing ;;
  2d) comp2d ;; encode) encode ;; qa) qa ;;
  all) audio; plates; scene; render3d; comp2d; encode; qa ;;
  *) echo "unknown stage $stage"; exit 1 ;;
esac
