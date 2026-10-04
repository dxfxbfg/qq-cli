"""异常与退出码。退出码对标 qqcli-rs 的 agent 契约。

    0  成功
    1  一般错误（参数、解析、IO）
    2  需要用户授权（解密）
    3  环境未就绪（未初始化 / 明文库缺失）
"""

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NEEDS_CONSENT = 2
EXIT_NOT_READY = 3


class QqcliError(Exception):
    """带退出码的业务异常。"""

    exit_code = EXIT_ERROR

    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint


class NotReadyError(QqcliError):
    """明文库或配置缺失，需要先 qq init / qq sync。"""

    exit_code = EXIT_NOT_READY


class ConsentRequiredError(QqcliError):
    """需要用户明确授权才能解密。"""

    exit_code = EXIT_NEEDS_CONSENT
