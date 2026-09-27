# Source this before running any stage:  source src/env.sh
# Everything temporary lives in _temp_install/; heavy intermediates go to $OPUS_BUILD.
export OPUS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OPUS_TOOLS="$OPUS_ROOT/_temp_install"
export OPUS_PY="$OPUS_TOOLS/venv/bin/python"
_SCRATCH="/tmp/claude-0/-home-user-MotionGraphicsTest/d8ea797e-938c-5104-8c59-36eddee5cb9f/scratchpad"
if [ -z "${OPUS_BUILD:-}" ]; then
  if [ -d "$_SCRATCH" ]; then OPUS_BUILD="$_SCRATCH/build"; else OPUS_BUILD="$OPUS_ROOT/build"; fi
fi
export OPUS_BUILD
export PATH="$OPUS_TOOLS/bin:$PATH"
# skia-python needs libEGL.so.1; extracted (not installed) from the Ubuntu libegl1 deb
export LD_LIBRARY_PATH="$OPUS_TOOLS/syslibs/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Surge XT factory data without a system install (see SurgeStorage::getOverrideDataHome)
export SURGE_DATA_HOME="$OPUS_TOOLS/plugins/SurgeXTData"
export PYTHONPATH="$OPUS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$OPUS_BUILD"
