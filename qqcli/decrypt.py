"""SQLCipher 解密导出。仅在 `qq init` / `qq sync`（需授权）时使用。

QQ NT（macOS）的 nt_db/*.db = 前 1024 字节明文头 + SQLCipher 密文页；
剥头后用 sqlcipher CLI 的 sqlcipher_export 导出明文。

不绑定 QQ 版本：KDF/页大小等参数取 config `cipher` 覆盖值，缺省用
QQ NT 长期稳定的默认参数；若某版本改动，用 kdf_hook.py 抓取后写回配置。
"""

import os
import subprocess

from .config import (CIPHER_DEFAULTS, WANT_DBS, find_account_dirs,
                     find_sqlcipher, load_config, plain_path)
from .errors import ConsentRequiredError, NotReadyError, QqcliError

HEADER_BYTES = 1024


def build_pragmas(cipher=None):
    """按（可覆盖的）SQLCipher 参数生成 PRAGMA 串。"""
    c = dict(CIPHER_DEFAULTS)
    for k, v in (cipher or {}).items():
        if k in c and v not in (None, ""):
            c[k] = v
    return (
        "PRAGMA cipher_page_size=%s; PRAGMA kdf_iter=%s; "
        "PRAGMA cipher_hmac_algorithm=%s; "
        "PRAGMA cipher_default_kdf_algorithm=%s; " % (
            c["page_size"], c["kdf_iter"], c["hmac"], c["default_kdf"])
    )


def decrypt_db(src, dst, passphrase, sqlcipher=None, pragmas=None):
    """剥头 -> sqlcipher_export 明文。返回 dst。"""
    sqlcipher = sqlcipher or find_sqlcipher()
    if not sqlcipher:
        raise QqcliError("未找到 sqlcipher", hint="brew install sqlcipher")
    with open(src, "rb") as f:
        f.seek(HEADER_BYTES)
        data = f.read()
    tmp = dst + ".clean.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    if os.path.exists(dst):
        os.remove(dst)
    sql = (
        "PRAGMA key='%s';" % passphrase
        + (pragmas if pragmas is not None else build_pragmas())
        + "ATTACH DATABASE '%s' AS plain KEY '';" % dst
        + "SELECT sqlcipher_export('plain');DETACH plain;"
    )
    try:
        r = subprocess.run([sqlcipher, tmp, sql], capture_output=True, text=True, timeout=300)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if not os.path.exists(dst):
        raise QqcliError("解密失败: %s %s" % (r.stdout[-200:], r.stderr[-200:]))
    return dst


def _pick_account(account=None):
    dirs = find_account_dirs()
    if not dirs:
        raise NotReadyError("未找到 QQ NT 数据目录（需先运行过 QQ）")
    if account:
        for d in dirs:
            if account in os.path.basename(d):
                return d
        raise QqcliError("未找到账号目录: %s" % account)
    if len(dirs) > 1:
        raise QqcliError(
            "发现多个账号目录，请用 --account 指定：%s"
            % ", ".join(os.path.basename(d) for d in dirs))
    return dirs[0]


def sync(passphrase, account=None, db_names=WANT_DBS, cipher=None):
    """重新解密导出到明文缓存。返回 (账号目录, [(db, dst, size)])。"""
    if not passphrase:
        raise ConsentRequiredError(
            "缺少 passphrase，无法解密",
            hint="passphrase 存于 qqmac/passphrase.txt；或先跑 qqmac/extract_key.sh")
    acct = _pick_account(account)
    os.makedirs(os.path.dirname(plain_path()), exist_ok=True)
    pragmas = build_pragmas(cipher if cipher is not None else load_config().get("cipher"))
    out = []
    for db in db_names:
        src = os.path.join(acct, "nt_db", db)
        if not os.path.exists(src):
            continue
        dst = plain_path(db)
        decrypt_db(src, dst, passphrase, pragmas=pragmas)
        out.append((db, dst, os.path.getsize(dst)))
    return acct, out


def account_db_state(account=None):
    """诊断用：列出账号目录下各库的存在与大小。"""
    acct = _pick_account(account)
    info = []
    for db in WANT_DBS:
        src = os.path.join(acct, "nt_db", db)
        info.append((db, os.path.exists(src),
                     os.path.getsize(src) if os.path.exists(src) else 0))
    return acct, info
