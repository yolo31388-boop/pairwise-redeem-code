"""兑换码礼包 - 带6个bug"""
from dataclasses import dataclass, field
import random

@dataclass
class RedeemCode:
    code: str
    type: str  # general/exclusive/one_time
    content: list
    start_time: float
    end_time: float
    max_per_user: int = 1
    bound_user: str = None

class RedeemSystem:
    def __init__(self):
        self.codes: dict[str, RedeemCode] = {}
        self.redeemed: dict[str, set] = {}  # user -> set of codes
        self.counter = 0

    def generate_code(self, type, content, count=1):
        # bug5: 自增ID
        codes = []
        for i in range(count):
            self.counter += 1
            code = f"CODE{self.counter:06d}"
            self.codes[code] = RedeemCode(code, type, content, 0, 9999999999)
            codes.append(code)
        return codes

    def redeem(self, code, user_id):
        rc = self.codes[code]
        # bug1: 不检查单用户限制
        # bug2: 不检查结束时间
        # bug6: 不去重
        self.redeemed.setdefault(user_id, set()).add(code)
        return rc.content

    def open_gift(self, gift_id, user_id):
        # bug3: 固定内容
        return self.codes[gift_id].content if gift_id in self.codes else ["item1"]

    def validate_code(self, code, user_id):
        rc = self.codes.get(code)
        if not rc:
            return False
        # bug4: 不区分类型
        return True
