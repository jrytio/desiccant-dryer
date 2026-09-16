#!/usr/bin/env python3
"""Fetch /screen.png from a board and check it is a real 240x240 frame.

Usage: scripts/check-screen-png.py <host-or-ip> [out.png]

Fails if the response is not a decodable 240x240 indexed PNG, or if the
image is a single flat colour (which is what a blank or unrendered frame
looks like and is the failure this guards against).
"""
import sys
import urllib.request
import zlib
import struct


def chunks(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    off = 8
    while off < len(data):
        (length,) = struct.unpack(">I", data[off : off + 4])
        kind = data[off + 4 : off + 8]
        body = data[off + 8 : off + 8 + length]
        yield kind, body
        off += 12 + length


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: check-screen-png.py <host> [out.png]")
    url = f"http://{sys.argv[1]}/screen.png"
    raw = urllib.request.urlopen(url, timeout=20).read()
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(raw)

    ihdr = idat = None
    for kind, body in chunks(raw):
        if kind == b"IHDR":
            ihdr = body
        elif kind == b"IDAT":
            idat = (idat or b"") + body
    assert ihdr is not None and idat is not None, "missing IHDR/IDAT"

    w, h, depth, color = struct.unpack(">IIBB", ihdr[:10])
    assert (w, h) == (240, 240), f"expected 240x240, got {w}x{h}"
    assert depth == 8 and color == 3, f"expected 8-bit indexed, got depth={depth} color={color}"

    pixels = zlib.decompress(idat)
    stride = w + 1
    assert len(pixels) == h * stride, f"expected {h * stride} bytes, got {len(pixels)}"
    body = bytes(b for y in range(h) for b in pixels[y * stride + 1 : (y + 1) * stride])
    distinct = len(set(body))
    assert distinct > 4, f"image is flat ({distinct} distinct colours) - nothing was drawn"

    print(f"OK {w}x{h} indexed PNG, {distinct} distinct colours, {len(raw)} bytes")


if __name__ == "__main__":
    main()
