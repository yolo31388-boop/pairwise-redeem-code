"""兑换码礼包系统（实现见 redeem/code.py，此处做兼容导出）。"""
from redeem.code import (
    RedeemCode,
    RedeemSystem,
    RedeemError,
    CodeNotFoundError,
    CodeExpiredError,
    CodeNotStartedError,
    UserNotBoundError,
    UserLimitReachedError,
    CodeExhaustedError,
    generate_random_code,
    VALID_TYPES,
)

__all__ = [
    "RedeemCode",
    "RedeemSystem",
    "RedeemError",
    "CodeNotFoundError",
    "CodeExpiredError",
    "CodeNotStartedError",
    "UserNotBoundError",
    "UserLimitReachedError",
    "CodeExhaustedError",
    "generate_random_code",
    "VALID_TYPES",
]
