#!/usr/bin/env python3
"""静态定位 wrapper.node 中 nt_sqlite3_key_v2 函数 VA（arm64 slice）。"""
import struct

WRAPPER = "/Applications/QQ.app/Contents/Resources/app/wrapper.node"

data = open(WRAPPER, "rb").read()
magic = struct.unpack(">I", data[:4])[0]
if magic == 0xCAFEBABE:
    narch = struct.unpack(">I", data[4:8])[0]
    arm64_off = None
    for i in range(narch):
        base = 8 + i * 20
        cputype = struct.unpack(">i", data[base:base+4])[0]
        offset = struct.unpack(">I", data[base+8:base+12])[0]
        if cputype == 0x0100000C:
            arm64_off = offset
    assert arm64_off is not None, "no arm64 slice"
    sl = data[arm64_off:]
elif struct.unpack("<I", data[:4])[0] == 0xFEEDFACF:
    sl = data
    arm64_off = 0
else:
    raise SystemExit("unknown format")

ncmds = struct.unpack("<I", sl[16:20])[0]
off = 32
text_vmaddr = text_fileoff = text_size = 0
for _ in range(ncmds):
    cmd, csz = struct.unpack("<II", sl[off:off+8])
    if cmd == 0x19:
        nsects = struct.unpack("<I", sl[off+64:off+68])[0]
        s = off + 72
        for _ in range(nsects):
            sname = sl[s:s+16].rstrip(b"\x00").decode("ascii", "replace")
            sgname = sl[s+16:s+32].rstrip(b"\x00").decode("ascii", "replace")
            saddr, ssz = struct.unpack("<QQ", sl[s+32:s+48])
            sfoff = struct.unpack("<I", sl[s+48:s+52])[0]
            if sname == "__text" and sgname == "__TEXT":
                text_vmaddr, text_fileoff, text_size = saddr, sfoff, ssz
            s += 80
    off += csz

n1 = b"nt_sqlite3_key_v2: db="
n2 = b"nt_sqlite3_key_v2: no key"
i1 = data.find(n1)
i2 = data.find(n2)
assert i1 >= 0 and i2 >= 0, "diagnostic strings not found"
va1, va2 = i1 - arm64_off, i2 - arm64_off

text = sl[text_fileoff:text_fileoff+text_size]

def find_add(buf, imm12):
    return [i for i in range(0, len(buf)-4, 4)
            if (struct.unpack("<I", buf[i:i+4])[0] & 0xFFC00000) == 0x91000000
            and ((struct.unpack("<I", buf[i:i+4])[0] >> 10) & 0xFFF) == imm12]

pairs = []
for a in find_add(text, va1 & 0xFFF):
    for b in find_add(text, va2 & 0xFFF):
        if abs(a - b) < 4096:
            pairs.append((a, b))

func_vas = []
for a, b in pairs:
    start = min(a, b)
    found = None
    for back in range(0, min(start, 4096), 4):
        pos = start - back
        if (struct.unpack("<I", text[pos:pos+4])[0] & 0xFF8003FF) == 0xD10003FF:
            found = pos
    if found is not None:
        func_vas.append(text_vmaddr + found)

func_vas = sorted(set(func_vas))
if func_vas:
    print(f"FUNC_VA=0x{func_vas[0]:X}")
else:
    print("FUNC_VA_NOT_FOUND")
