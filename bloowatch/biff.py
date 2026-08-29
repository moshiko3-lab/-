#!/usr/bin/env python3
"""Minimal BIFF8 (.xls) reader -- enough for Bloowatch's daily-report export.

Bloowatch returns a legacy OLE2/BIFF workbook. We only need the cell grid, so
we walk the record stream and pick up SST strings, LABELSST, NUMBER, RK and
MULRK cells.
"""
import struct


def _rk(v):
    """Decode an RK-encoded number."""
    cents = v & 0x01
    if v & 0x02:                       # integer, stored in the top 30 bits
        n = float(v >> 2)
        if v & 0x80000000:             # sign-extend
            n = float((v >> 2) - 0x40000000)
    else:                              # top 30 bits of an IEEE double
        n = struct.unpack("<d", struct.pack("<Q", (v & 0xFFFFFFFC) << 32))[0]
    return n / 100.0 if cents else n


def _sst(body):
    """Parse a Shared String Table record body into a list of strings."""
    out = []
    if len(body) < 8:
        return out
    n = struct.unpack("<I", body[4:8])[0]
    p = 8
    for _ in range(n):
        if p + 3 > len(body):
            break
        ln = struct.unpack("<H", body[p:p + 2])[0]
        flags = body[p + 2]
        p += 3
        wide = flags & 0x01
        if flags & 0x08:               # rich text runs
            p += 2
        if flags & 0x04:               # far-east extension
            p += 4
        take = ln * (2 if wide else 1)
        raw = body[p:p + take]
        p += take
        try:
            out.append(raw.decode("utf-16-le" if wide else "latin-1"))
        except Exception:
            out.append("")
    return out


def cells(data):
    """Return {(row, col): value} for the first worksheet in the workbook."""
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("not an OLE2 file")
    stream = data[512:]                # the workbook stream starts here
    strings, grid = [], {}
    pos = 0
    while pos + 4 <= len(stream):
        rid, rlen = struct.unpack("<HH", stream[pos:pos + 4])
        body = stream[pos + 4:pos + 4 + rlen]
        if len(body) < rlen:
            break
        if rid == 0x00FC:                                   # SST
            strings = _sst(body)
        elif rid == 0x00FD and rlen >= 10:                  # LABELSST
            r, c, _ = struct.unpack("<HHH", body[:6])
            i = struct.unpack("<I", body[6:10])[0]
            grid[(r, c)] = strings[i] if i < len(strings) else ""
        elif rid == 0x0203 and rlen >= 14:                  # NUMBER
            r, c, _ = struct.unpack("<HHH", body[:6])
            grid[(r, c)] = struct.unpack("<d", body[6:14])[0]
        elif rid == 0x027E and rlen >= 10:                  # RK
            r, c, _ = struct.unpack("<HHH", body[:6])
            grid[(r, c)] = _rk(struct.unpack("<I", body[6:10])[0])
        elif rid == 0x00BD and rlen >= 6:                   # MULRK
            r, c1 = struct.unpack("<HH", body[:4])
            n = (rlen - 6) // 6
            for k in range(n):
                off = 4 + k * 6
                grid[(r, c1 + k)] = _rk(struct.unpack("<I", body[off + 2:off + 6])[0])
        pos += 4 + rlen
    return grid


def rows(data):
    """Return the sheet as a list of row lists."""
    g = cells(data)
    if not g:
        return []
    maxr = max(r for r, _ in g)
    maxc = max(c for _, c in g)
    return [[g.get((r, c), "") for c in range(maxc + 1)] for r in range(maxr + 1)]
