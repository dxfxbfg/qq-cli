"""lldb helper v6: 异步模式 + 事件监听。final 版。

lldb batch:
    lldb -b /Applications/QQ.app/Contents/MacOS/QQ \
      -o "command script import <此文件>" \
      -o "process launch -s" \
      -o "qqwait"
"""
import lldb
import os
import struct
import time

WRAPPER = "wrapper.node"
# 目录优先取环境变量 QQMAC_DIR（由 extract_key.sh 导出），否则用本文件所在目录
_HERE = os.environ.get("QQMAC_DIR") or os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_HERE, "hook.log")
KEY_PATH = os.path.join(_HERE, "db_key.txt")
_logf = None


def log(msg):
    global _logf
    if _logf is None:
        _logf = open(LOG_PATH, "a", buffering=1)
    line = "[hook %s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    _logf.write(line + "\n")


def _find_all_vas():
    cache = os.path.join(_HERE, "va_cache.txt")
    if os.path.exists(cache):
        vals = [int(x, 16) for x in open(cache).read().split()]
        if vals:
            return vals
    vas = _find_all_vas_impl()
    if vas:
        open(cache, "w").write(" ".join(hex(v) for v in vas))
    return vas


def _find_all_vas_impl():
    WRAPPER_PATH = "/Applications/QQ.app/Contents/Resources/app/wrapper.node"
    data = open(WRAPPER_PATH, "rb").read()
    magic = struct.unpack(">I", data[:4])[0]
    arm64_off = 0
    if magic == 0xCAFEBABE:
        narch = struct.unpack(">I", data[4:8])[0]
        arm64_off = None
        for i in range(narch):
            base = 8 + i * 20
            if struct.unpack(">i", data[base:base+4])[0] == 0x0100000C:
                arm64_off = struct.unpack(">I", data[base+8:base+12])[0]
        if arm64_off is None:
            return []
        sl = data[arm64_off:]
    else:
        sl = data
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
    txt = sl[tf:tf+ts]
    i1 = data.find(b"nt_sqlite3_key_v2: db=")
    i2 = data.find(b"nt_sqlite3_key_v2: no key")
    if i1 < 0 or i2 < 0:
        return []
    va1, va2 = i1 - arm64_off, i2 - arm64_off

    def adc(buf, imm):
        return [i for i in range(0, len(buf)-4, 4)
                if struct.unpack("<I", buf[i:i+4])[0] & 0xFFC00000 == 0x91000000
                and struct.unpack("<I", buf[i:i+4])[0] >> 10 & 0xFFF == imm]
    # 向上找最近的函数序言: PACIBSP / STP X29,X30,[SP,#imm]! / SUB SP
    def prologue_pos(start):
        for back in range(0, min(start, 8192), 4):
            pos = start - back
            ins = struct.unpack("<I", txt[pos:pos+4])[0]
            if ins == 0xD503237F:
                return pos
            if (ins & 0xFFC003FF) == 0xA90003FF:  # stp x29,x30,[sp,#imm]!
                return pos
            if (ins & 0xFF8003FF) == 0xD10003FF:  # sub sp,sp,#imm
                return pos
        return None

    vas = []
    for h1 in adc(txt, va1 & 0xFFF):
        for h2 in adc(txt, va2 & 0xFFF):
            if abs(h1 - h2) < 4096:
                p = prologue_pos(min(h1, h2))
                if p is not None:
                    vas.append(tv + p)
    seen = set()
    out = []
    for v in vas:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _loaded(target):
    for m in target.module_iter():
        if m.file and str(m.file.basename) == WRAPPER:
            return True
    return False


def _module_base(target):
    for m in target.module_iter():
        if m.file and str(m.file.basename) == WRAPPER:
            return m.ResolveFileAddress(0).GetLoadAddress(target)
    return None


def _capture(process, bp_addrs):
    frame = process.GetSelectedThread().GetFrameAtIndex(0)
    pc = frame.GetPC()
    hit = None
    for a in bp_addrs:
        if a <= pc <= a + 8:
            hit = a
            break
    if hit is None:
        return False
    x2 = frame.FindRegister("x2").GetValueAsUnsigned()
    x3 = frame.FindRegister("x3").GetValueAsUnsigned()
    x1 = frame.FindRegister("x1").GetValueAsUnsigned()
    err = lldb.SBError()
    if not (4 <= x3 <= 64):
        log("hit %#x nKey=%d suspicious -> continue" % (hit, x3))
        return False
    mem = process.ReadMemory(x2, x3, err)
    if err.Fail():
        log("hit but mem read failed")
        return False
    try:
        key = mem.decode("ascii")
        if not all(32 <= c < 127 for c in mem):
            raise ValueError("non-printable")
    except Exception:
        log("hit but not ascii: %s" % mem.hex())
        return False
    zdb = "?"
    if x1:
        s = process.ReadCStringFromMemory(x1, 64, err)
        if err.Success():
            zdb = s
    log("HIT %#x nKey=%d zDb=%s KEY=%s" % (hit, x3, zdb, key))
    with open(KEY_PATH, "w") as f:
        f.write(key)
    return True


def qqwait_command(debugger, command, exe_ctx, result, _dict):
    target = exe_ctx.GetTarget()
    process = exe_ctx.GetProcess()
    if not process or not process.IsValid():
        log("no process")
        return
    log("start pid=%d" % process.GetProcessID())

    vas = _find_all_vas()
    log("candidate VAs: %s" % [hex(v) for v in vas])
    if not vas:
        return

    # 1) async 模式恢复运行, 轮询模块列表等 wrapper.node
    debugger.SetAsync(True)
    process.Continue()
    log("resumed async")
    base = None
    for i in range(300):
        time.sleep(0.2)
        if _loaded(target):
            base = _module_base(target)
            if base:
                log("wrapper loaded at %0.1fs, base=%#x" % ((i+1)*0.2, base))
                break
    if base is None:
        log("timeout waiting wrapper.node")
        process.Detach()
        return

    # 2) 停下设断点
    process.Stop()
    for _ in range(30):
        time.sleep(0.1)
        if process.GetState() == lldb.eStateStopped:
            break
    if process.GetState() != lldb.eStateStopped:
        log("cannot interrupt")
        process.Detach()
        return
    bp_addrs = [base + v for v in vas]
    nloc = 0
    for a in bp_addrs:
        bp = target.BreakpointCreateByAddress(a)
        nloc += bp.GetNumLocations()
    log("breakpoints %s loc=%d" % ([hex(a) for a in bp_addrs], nloc))
    if nloc == 0:
        process.Detach()
        return
    debugger.HandleCommand("settings set target.process.stop-on-sharedlibrary-events false")

    # 3) 继续运行, 用 listener 等断点命中
    listener = lldb.SBListener("qqkey")
    process.GetBroadcaster().AddListener(listener, lldb.SBProcess.eBroadcastBitStateChanged)
    process.Continue()
    log("waiting for login/hit (11 min timeout) ...")
    event = lldb.SBEvent()
    while True:
        if not listener.WaitForEvent(660, event):
            log("timeout, no hit")
            process.Detach()
            return
        if not lldb.SBProcess.EventIsProcessEvent(event):
            continue
        st = lldb.SBProcess.GetStateFromEvent(event)
        if st == lldb.eStateExited:
            log("process exited")
            return
        if st == lldb.eStateStopped:
            thread = process.GetSelectedThread()
            if thread.IsValid() and _capture(process, bp_addrs):
                process.Detach()
                log("done, detached")
                return
            log("stop not ours, resume")
            process.Continue()
        # 其他状态忽略继续等


def __lldb_init_module(debugger, _dict):
    debugger.HandleCommand("command script add -f getkey_helper.qqwait_command qqwait")
