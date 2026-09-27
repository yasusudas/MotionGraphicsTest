#!/usr/bin/env bash
# Recreate _temp_install/ (everything temporary, nothing written to system paths).
# Needs: uv, python3.13, curl, git, dpkg-deb (for the libEGL shim), network access to
# pypi.org, files.pythonhosted.org, github.com (+ release asset CDN), raw.githubusercontent.com,
# archive.ubuntu.com (apt-get download only).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$ROOT/_temp_install"
mkdir -p "$T"/{downloads,plugins,samples,fonts,bin,home,syslibs}
export UV_CACHE_DIR="$T/uv-cache"

# ---------------------------------------------------------------- Python (bpy 5.1.1 needs cp313)
uv venv --python "$(command -v python3.13)" "$T/venv"
uv pip install --python "$T/venv/bin/python" \
  numpy==2.5.3 scipy==1.18.1 skia-python==144.0.post2 pedalboard==0.9.24 soundfile==0.14.0 \
  mido==1.3.3 pyloudnorm==0.2.0 pillow opencv-python-headless==5.0.0.93 fonttools==4.66.0 bpy==5.1.1
# pedalboard 0.9.25 uses AVX512-FP16 in a static initialiser (SIGILL on CPUs without it) -> 0.9.24

# skia-python links libEGL.so.1: extract (not install) the Ubuntu package
( cd "$T/downloads" && apt-get download libegl1 && dpkg -x libegl1_*.deb "$T/syslibs" )

# ---------------------------------------------------------------- ffmpeg (static)
G=https://github.com
curl -sSLf -o "$T/downloads/ffmpeg.tar.xz" "$G/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
mkdir -p "$T/downloads/x_ffmpeg" && tar xJf "$T/downloads/ffmpeg.tar.xz" -C "$T/downloads/x_ffmpeg"
cp "$T"/downloads/x_ffmpeg/*/bin/ff{mpeg,probe} "$T/bin/"

# ---------------------------------------------------------------- plugins (VST3, Linux x86_64)
cd "$T/downloads"
curl -sSLfO "$G/surge-synthesizer/releases-xt/releases/download/1.3.4/surge-xt-linux-x86_64-1.3.4.tar.gz"
curl -sSLfO "$G/michaelwillis/dragonfly-reverb/releases/download/3.2.10/dragonfly-reverb-3.2.10-linux-x86_64.tar.xz"
curl -sSLfO "$G/jatinchowdhury18/AnalogTapeModel/releases/download/v2.11.4/ChowTapeModel-Linux-x64-2.11.4.deb"
mkdir -p x_surge x_dragonfly x_chow
tar xzf surge-xt-linux-x86_64-1.3.4.tar.gz -C x_surge
tar xJf dragonfly-reverb-3.2.10-linux-x86_64.tar.xz -C x_dragonfly
dpkg -x ChowTapeModel-Linux-x64-2.11.4.deb x_chow
mv "x_surge/lib/vst3/Surge XT.vst3" "x_surge/lib/vst3/Surge XT Effects.vst3" "$T/plugins/"
mv x_surge/share/surge-xt "$T/plugins/SurgeXTData"
for n in Hall Plate Room; do mv "x_dragonfly/dragonfly-reverb-3.2.10/Dragonfly${n}Reverb.vst3" "$T/plugins/"; done
mv x_dragonfly/dragonfly-reverb-3.2.10/DragonflyEarlyReflections.vst3 "$T/plugins/"
mv x_chow/usr/lib/vst3/CHOWTapeModel.vst3 "$T/plugins/"

# ---------------------------------------------------------------- samples (sparse git checkouts)
cd "$T/samples"
clone() { GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 --filter=blob:none --no-checkout "https://github.com/$1" "$2"; }
clone ritchse/tidal-drum-machines g_tdm
( cd g_tdm && git sparse-checkout set --no-cone '/machines/RolandTR808/' '/machines/RolandTR909/' && git checkout -q HEAD )
mv g_tdm/machines drum-machines
DIRT="glitch hit space speedupdown stab tech wind bleep pad padlong sf metal electro1 hardcore reverbkick ul v noise2 industrial print flick future blip"
clone tidalcycles/Dirt-Samples g_dirt
( cd g_dirt && git sparse-checkout set --no-cone $(for d in $DIRT; do printf "/%s/ " "$d"; done) && git checkout -q HEAD )
mkdir -p dirt && for d in $DIRT; do mv "g_dirt/$d" dirt/; done
clone sgossner/VCSL g_vcsl
( cd g_vcsl && git sparse-checkout set --no-cone \
    '/Idiophones/Struck Idiophones/Clash Cymbals 2/cymbal_crash2_fff1.wav' \
    '/Idiophones/Struck Idiophones/Gong 1/gong_fff.wav' \
    '/Idiophones/Struck Idiophones/Suspended Cymbal 2/susCymb2_*' \
    '/Membranophones/Struck Membranophones/Bass Drum 2/bassdrum_*' \
    '/Idiophones/Struck Idiophones/Glockenspiel/' && git checkout -q HEAD )
mkdir -p vcsl && find g_vcsl -name '*.wav' -exec mv {} vcsl/ \;
rm -rf g_tdm g_dirt g_vcsl

# ---------------------------------------------------------------- fonts (OFL, google/fonts)
R=https://raw.githubusercontent.com/google/fonts/main/ofl
cd "$T/fonts"
for p in "inter/Inter%5Bopsz,wght%5D.ttf" "inter/OFL.txt" "archivo/Archivo%5Bwdth,wght%5D.ttf" "archivo/OFL.txt" \
         "jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf" "jetbrainsmono/OFL.txt"; do
  d=$(dirname "$p"); mkdir -p "$d"
  curl -sSLf -o "$d/$(basename "$p" | sed 's/%5B/[/;s/%5D/]/')" "$R/$p"
done
echo "tools ready in $T"
