#!/usr/bin/env python3
"""精确定位 nt_sqlite3_key_v2: 完整解析 ADRP+ADD 对, 目标地址必须精确等于诊断字符串 VA。"""
import struct

WRAPPER = "/Applications/QQ.app/Contents/Resources/app/wrapper.node"
data = open(WRAPPER, "rb").read()

# arm64 slice
narch = struct.unpack(">I", data[4:8])[0]
arm64_off = None
for i in range(narch):
    base = 8 + i * 20
    if struct.unpack(">i", data[base:base+4])[0] == 0x0100000C:
        arm64_off = struct.unpack(">I", data[base+8:base+12])[0]
        break
sl = data[arm64_off:]

# __text
ncmds = struct.unpack("<I", sl[16:20])[0]
off = 32
tv = tf = ts = 0
for _ in range(ncmds):
    cmd, csz = struct.unpack("<II", sl[off:off+8])
    if cmd == 0x19:
        nsects = struct.unpack("<I", sl[off+64:off+68])[0]
        s = off + 72
        for _ in range(nsects):
            sn = sl[s:s+16].rstrip(b"\x00").decode("ascii", "replace")
            sg = sl[s+16:s+32].rstrip(b"\x00").decode("ascii", "replace")
            if sn == "__text" and sg == "__TEXT":
                tv = struct.unpack("<Q", sl[s+32:s+40])[0]
                ts = struct.unpack("<Q", sl[s+40:s+48])[0]
                tf = struct.unpack("<I", sl[s+48:s+52])[0]
            s += 80
    off += csz
text = sl[tf:tf+ts]

i1 = data.find(b"nt_sqlite3_key_v2: db=", arm64_off)
i2 = data.find(b"nt_sqlite3_key_v2: no key", arm64_off)
str1_va = i1 - arm64_off
str2_va = i2 - arm64_off
print(f"str1 @ {str1_va:#x}  str2 @ {str2_va:#x}")

def sign_extend(val, bits):
    if val & (1 << (bits - 1)):
        val -= (1 << bits)
    return val

refs = []
n = len(text) // 4
# ADRP: op=1 immlo[30:29] 10000 immhi[23:5] Rn[4:0]
for idx in range(n - 8):
    ins = struct.unpack_from("<I", text, idx * 4)[0]
    if (ins & 0x9F000000) != 0x90000000:
        continue
    rd = ins & 0x1F
    immlo = (ins >> 29) & 3
    immhi = (ins >> 5) & 0x7FFFF
    imm = sign_extend((immhi << 2) | immlo, 21)
    pc_page = (tv + idx * 4) & ~0xFFF
    target_page = pc_page + (imm << 12)
    # 后续 8 条内找 ADD Xd, Xd, #imm
    for j in range(1, 8):
        if idx + j >= n:
            break
        ins2 = struct.unpack_from("<I", text, (idx + j) * 4)[0]
        if (ins2 & 0xFF800000) != 0x91000000:
            continue
        if (ins2 & 0x1F) != rd:            # Rn must == rd
            continue
        if ((ins2 >> 5) & 0x1F) != rd:     # Rd must == rd
            continue
        imm12 = (ins2 >> 10) & 0xFFF
        full = target_page + imm12
        if full == str1_va:
            refs.append((tv + idx * 4, tv + (idx + j) * 4, 1))
        elif full == str2_va:
            refs.append((tv + idx * 4, tv + (idx + j) * 4, 2))

print(f"精确引用点: {len(refs)}")
for adrp_va, add_va, which in refs:
    print(f"  str{which}: ADRP@{adrp_va:#x} ADD@{add_va:#x}")

# 从引用点向上找序言
def find_prologue(pos):
    start_idx = (pos - tv) // 4
    for back in range(0, min(start_idx, 4096)):
        idx = start_idx - back
        ins = struct.unpack_from("<I", text, idx * 4)[0]
        if ins == 0xD503237F or (ins & 0xFFC003FF) == 0xA90003FF or (ins & 0xFF8003FF) == 0xD10003FF:
            # 检查该位置前一条是否 RET/函数尾 (判定真边界)
            return tv + idx * 4
    return None

for adrp_va, add_va, which in refs:
    p = find_prologue(adrp_va)
    print(f"str{which} 引用点 {adrp_va:#x} -> 序言/入口 {hex(p) if p else None}")
