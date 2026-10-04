"""路径与配置：明文库位置、配置文件读写、账号目录发现。"""

import glob
import json
import os
import stat

from .errors import NotReadyError

HOME = os.path.expanduser("~")
QQMAC = os.environ.get("QQCLI_HOME") or os.path.join(HOME, ".qqmac")
PLAIN = os.environ.get("QQCLI_PLAIN_DIR") or os.path.join(QQMAC, "plain")
CONFIG_PATH = os.path.join(QQMAC, "config.json")

# 需要解密导出的库
WANT_DBS = ("nt_msg.db", "group_info.db", "profile_info.db", "recent_contact.db")

# sqlcipher CLI 查找路径
SQLCIPHER_CANDIDATES = (
    "/opt/homebrew/bin/sqlcipher",
    "/usr/local/bin/sqlcipher",
    "sqlcipher",
)

# SQLCipher 参数默认值。QQ NT 长期使用这组参数，故不限版本可用；
# 若某版本改用不同参数，用 kdf_hook.py 抓取后写入 config.json 的 "cipher" 覆盖：
#   {"cipher": {"page_size": 4096, "kdf_iter": 4000,
#               "hmac": "HMAC_SHA1", "default_kdf": "PBKDF2_HMAC_SHA512"}}
CIPHER_DEFAULTS = {
    "page_size": 4096,
    "kdf_iter": 4000,
    "hmac": "HMAC_SHA1",
    "default_kdf": "PBKDF2_HMAC_SHA512",
}


def find_sqlcipher():
    for cand in SQLCIPHER_CANDIDATES:
        if os.path.isabs(cand):
            if os.path.exists(cand):
                return cand
        else:
            for d in os.environ.get("PATH", "").split(os.pathsep):
                p = os.path.join(d, cand)
                if os.path.exists(p):
                    return p
    return None


def plain_path(name="nt_msg.db"):
    return os.path.join(PLAIN, name)


def ensure_plain(name="nt_msg.db"):
    """明文库必须存在，否则抛 NotReadyError。"""
    path = plain_path(name)
    if not os.path.exists(path):
        raise NotReadyError(
            "明文库缺失: %s" % path,
            hint="先运行: qq sync（或首次 qq init）",
        )
    return path


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(QQMAC, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(CONFIG_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass


def find_account_dirs():
    """返回 QQ 账号数据目录列表（含 nt_db 的 nt_qq_* 目录）。"""
    pat = os.path.join(
        HOME,
        "Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/nt_qq_*",
    )
    return [p for p in glob.glob(pat) if os.path.isdir(os.path.join(p, "nt_db"))]
