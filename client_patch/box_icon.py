"""Show the Mega Box picture on the lobby's token box (sc/ui.sc).

The lobby token box draws shape 2883, the Brawl Box picture. The shop's Mega
Box picture (shape 1569) is on the same texture, so shape 2883 is pointed at
that picture: its texture coordinates are copied from shape 1569 and its
outline is scaled to the old icon's size. Both are 8-point regions, so the
file keeps its layout. The .sc header hash (MD5 of the decompressed data)
and the file's SHA-1 in fingerprint.json are updated to match.
"""
import hashlib
import json
import lzma
import struct
from pathlib import Path

BRAWL_BOX_ICON = 2883
MEGA_BOX_PICTURE = 1569


def _decompress(data):
    hash_len = struct.unpack('>I', data[6:10])[0]
    body = data[10 + hash_len:]
    # Supercell stores a 4-byte size where LZMA-alone has 8 bytes. Files this
    # module writes also keep LZMA's end marker, which Python only accepts
    # with an unknown size; the game stops at the stated size.
    size = struct.unpack('<I', body[5:9])[0]
    try:
        return lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(body[:9] + b'\0' * 4 + body[9:])
    except lzma.LZMAError:
        raw = lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(body[:5] + b'\xff' * 8 + body[9:])
        if len(raw) != size:
            raise
        return raw


def _compress(raw):
    packed = lzma.compress(raw, format=lzma.FORMAT_ALONE,
                           filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 1 << 18, 'lc': 3, 'lp': 0, 'pb': 2}])
    # Props, then the real size in 4 bytes as the client expects.
    body = packed[:5] + struct.pack('<I', len(raw)) + packed[13:]
    digest = hashlib.md5(raw).digest()
    return b'SC' + struct.pack('>II', 1, len(digest)) + digest + body


def _regions(raw):
    """Map shape id -> list of (xy offset, point count) for each region."""
    p = 12 + 5
    count = struct.unpack('<H', raw[p:p + 2])[0]
    p += 2 + 2 * count
    for _ in range(count):
        p += 1 + raw[p]
    regions = {}
    while p < len(raw):
        tag = raw[p]
        length = struct.unpack('<I', raw[p + 1:p + 5])[0]
        start = p = p + 5
        if tag == 0:
            break
        if tag in (2, 18):
            shape = struct.unpack('<H', raw[p:p + 2])[0]
            q = p + 6
            while True:
                sub = raw[q]
                sub_len = struct.unpack('<I', raw[q + 1:q + 5])[0]
                q += 5
                if sub == 0:
                    break
                if sub in (17, 22):
                    regions.setdefault(shape, []).append((q + 2, raw[q + 1]))
                q += sub_len
        p = start + length
    return regions


def _points(raw, offset, n):
    xy = [struct.unpack('<ii', raw[offset + 8 * i:offset + 8 * i + 8]) for i in range(n)]
    uv_at = offset + 8 * n
    uv = [struct.unpack('<HH', raw[uv_at + 4 * i:uv_at + 4 * i + 4]) for i in range(n)]
    return xy, uv


def patch(raw):
    raw = bytearray(raw)
    regions = _regions(raw)
    (icon_at, n), = regions[BRAWL_BOX_ICON]
    (mega_at, m), = regions[MEGA_BOX_PICTURE]
    if n != m:
        raise SystemExit('Unexpected ui.sc: box icon shapes do not match')
    icon_xy, _ = _points(raw, icon_at, n)
    mega_xy, mega_uv = _points(raw, mega_at, n)

    def box(points):
        xs = [x for x, _ in points]; ys = [y for _, y in points]
        return min(xs), min(ys), max(xs), max(ys)
    ix0, iy0, ix1, iy1 = box(icon_xy)
    mx0, my0, mx1, my1 = box(mega_xy)
    scale = min((ix1 - ix0) / (mx1 - mx0), (iy1 - iy0) / (my1 - my0))
    cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
    mcx, mcy = (mx0 + mx1) / 2, (my0 + my1) / 2
    xy = [(round(cx + (x - mcx) * scale), round(cy + (y - mcy) * scale)) for x, y in mega_xy]
    raw[icon_at:icon_at + 12 * n] = b''.join(struct.pack('<ii', *p) for p in xy) + b''.join(struct.pack('<HH', *p) for p in mega_uv)
    return bytes(raw)


def apply(assets, stock=None):
    """Patch assets/sc/ui.sc, starting from the stock file when given."""
    assets = Path(assets)
    target = assets / 'sc/ui.sc'
    source = Path(stock) if stock and Path(stock).exists() else target
    data = _compress(patch(_decompress(source.read_bytes())))
    target.write_bytes(data)
    fingerprint = assets / 'fingerprint.json'
    info = json.loads(fingerprint.read_text(encoding='utf-8'))
    for entry in info['files']:
        if entry['file'] == 'sc/ui.sc':
            entry['sha'] = hashlib.sha1(data).hexdigest()
    fingerprint.write_text(json.dumps(info, separators=(',', ':')), encoding='utf-8')


if __name__ == '__main__':
    import sys
    apply(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
