"""PBKDF2 参数捕获: 断点 libcrypto 的 PKCS5_PBKDF2_HMAC, 记录 QQ 实际使用的 KDF 参数。"""
import lldb
import os

_hits = 0
_HERE = os.environ.get("QQMAC_DIR") or os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "kdf_calls.txt")


def bp_callback(frame, bp_loc, extra_args, internal_dict):
    global _hits
    _hits += 1
    try:
        x0 = frame.FindRegister("x0").GetValueAsUnsigned()
        x1 = frame.FindRegister("x1").GetValueAsUnsigned()
        x2 = frame.FindRegister("x2").GetValueAsUnsigned()
        x3 = frame.FindRegister("x3").GetValueAsUnsigned()
        x4 = frame.FindRegister("x4").GetValueAsUnsigned()
        x6 = frame.FindRegister("x6").GetValueAsUnsigned()
        process = frame.GetThread().GetProcess()
        err = lldb.SBError()
        pw = b"?"
        if 0 < x1 < 512:
            m = process.ReadMemory(x0, x1, err)
            if err.Success():
                pw = m
        salt = b"?"
        if 0 < x3 <= 128:
            m = process.ReadMemory(x2, x3, err)
            if err.Success():
                salt = m
        line = "CALL pass=%r passlen=%d salt=%s saltlen=%d iter=%d dklen=%d" % (
            pw, x1, salt.hex() if isinstance(salt, bytes) else salt, x3, x4, x6)
        print("[kdf] " + line, flush=True)
        with open(OUT, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print("[kdf] err %s" % e, flush=True)
    return False  # 不停, QQ 继续跑


def setup(debugger):
    target = debugger.GetSelectedTarget()
    bp = target.BreakpointCreateByName("PKCS5_PBKDF2_HMAC", "libcrypto.dylib")
    bp.SetScriptCallbackFunction("kdf_hook.bp_callback")
    print("[kdf] bp locations=%d" % bp.GetNumLocations(), flush=True)
