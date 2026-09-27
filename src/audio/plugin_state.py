"""Read / write VST3 plugin state blobs as exposed by pedalboard's ``raw_state``.

Layout of ``raw_state`` for JUCE-hosted VST3 plugins::

    b"VC2!" + u32le(len(xml)) + xml + b"\\0"
    xml = <VST3PluginState><IComponent>SIZE.CHARS</IComponent>
                           <IEditController>SIZE.CHARS</IEditController></VST3PluginState>

``SIZE.CHARS`` is JUCE's own MemoryBlock base64 flavour: alphabet ``.A-Za-z0-9+``,
6 bits per char packed LSB-first (not RFC 4648).

Surge XT's component state is the patch itself: ``b"sub3"`` + header ``<4s7I``
(tag, xml size, 6 wavetable sizes) + patch XML + wavetable data.  A factory
``.fxp`` file is a 60-byte fxChunkSetHeader (``CcnK``/``FPCh``) followed by the
same ``sub3`` payload.
"""
from __future__ import annotations

import re
import struct

import numpy as np

_ALPHA = b".ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+"
_LUT = np.full(256, 255, np.uint8)
_LUT[np.frombuffer(_ALPHA, np.uint8)] = np.arange(64, dtype=np.uint8)


def juce_b64decode(s: str | bytes) -> bytes:
    if isinstance(s, str):
        s = s.encode("ascii")
    size_s, chars = s.split(b".", 1)
    size = int(size_s)
    vals = _LUT[np.frombuffer(chars, np.uint8)]
    if (vals == 255).any():
        raise ValueError("invalid JUCE base64 character")
    bits = np.unpackbits(vals[:, None], axis=1, bitorder="little")[:, :6].reshape(-1)
    pad = (-bits.size) % 8
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, np.uint8)])
    out = np.packbits(bits, bitorder="little").tobytes()
    return out[:size]


def juce_b64encode(data: bytes) -> str:
    n = len(data)
    nchars = (n * 8 + 5) // 6
    bits = np.unpackbits(np.frombuffer(data, np.uint8), bitorder="little")
    bits = np.concatenate([bits, np.zeros(nchars * 6 - bits.size, np.uint8)])
    six = bits.reshape(-1, 6)
    vals = (six * (1 << np.arange(6, dtype=np.uint8))).sum(axis=1).astype(np.uint8)
    return f"{n}." + bytes(np.frombuffer(_ALPHA, np.uint8)[vals]).decode("ascii")


def split_raw_state(raw: bytes) -> dict[str, bytes]:
    """Return {'IComponent': bytes, 'IEditController': bytes} (either may be absent)."""
    if raw[:4] != b"VC2!":
        raise ValueError("not a JUCE VST3 state (missing VC2! magic)")
    (size,) = struct.unpack("<I", raw[4:8])
    xml = raw[8:8 + size].rstrip(b"\0").decode("utf-8")
    out = {}
    for tag in ("IComponent", "IEditController"):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
        if m:
            out[tag] = juce_b64decode(m.group(1).strip())
    return out


def join_raw_state(parts: dict[str, bytes]) -> bytes:
    body = "".join(f"<{k}>{juce_b64encode(v)}</{k}>" for k, v in parts.items())
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n\n'
           f"<VST3PluginState>{body}</VST3PluginState>").encode("utf-8") + b"\0"
    return b"VC2!" + struct.pack("<I", len(xml)) + xml


def with_component(raw: bytes, component: bytes) -> bytes:
    """Replace IComponent and drop IEditController (the controller resyncs from the processor)."""
    split_raw_state(raw)  # validate
    return join_raw_state({"IComponent": component})


# ---------------------------------------------------------------- Surge sub3 patches
_SUB3 = struct.Struct("<4s7I")


def fxp_to_sub3(fxp: bytes) -> bytes:
    if fxp[:4] != b"CcnK" or fxp[8:12] != b"FPCh":
        raise ValueError("not an opaque-chunk fxp")
    body = fxp[60:]
    if body[:4] != b"sub3":
        raise ValueError("fxp chunk is not a Surge sub3 patch")
    return body


def sub3_xml(patch: bytes) -> str:
    tag, xmlsize, *_ = _SUB3.unpack_from(patch)
    assert tag == b"sub3"
    return patch[_SUB3.size:_SUB3.size + xmlsize].decode("utf-8", "replace")


def sub3_replace_xml(patch: bytes, xml: str) -> bytes:
    tag, xmlsize, *wt = _SUB3.unpack_from(patch)
    xb = xml.encode("utf-8")
    rest = patch[_SUB3.size + xmlsize:]
    return _SUB3.pack(tag, len(xb), *wt) + xb + rest


def sub3_name(patch: bytes) -> str:
    m = re.search(r'<meta name="([^"]*)"', sub3_xml(patch))
    return m.group(1) if m else ""
