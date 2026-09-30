"""兑换码 - 含5个bug"""
from dataclasses import dataclass, field
import random

@dataclass
class Code:
    code: str
    used: bool = False
    type: str = "general"  # general/exclusive
    expired: bool = False
    owner: str = None  # 专属码的所有者

class RedeemSystem:
    def __init__(self):
        self.codes: dict[str, Code] = {}
        self.records: dict[str, list] = {}  # bug4: 游客不迁移
        self.used_codes: set = set()  # bug1: 非原子

    def redeem_code(self, code: str, player_id: str) -> bool:
        # bug1: 先查再标记再发奖，非原子
        if code not in self.codes:
            return False
        if self.codes[code].used:
            return False
        if self.codes[code].expired:
            return False
        self.codes[code].used = True
        # 发奖励
        if player_id not in self.records:
            self.records[player_id] = []
        self.records[player_id].append(code)
        return True

    def generate_code(self, length: int = 8) -> str:
        # bug2: 不查重
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        code = "".join(random.choice(chars) for _ in range(length))
        self.codes[code] = Code(code)
        return code

    def check_redeem_limit(self, code: str, player_id: str, player_type: str) -> bool:
        # bug3: 只检查过期，不检查玩家类型和次数
        if code not in self.codes:
            return False
        return not self.codes[code].expired

    def migrate_guest_records(self, guest_id: str, player_id: str) -> bool:
        # bug4: 不迁移游客记录
        return True

    def verify_exclusive_code(self, code: str, player_id: str) -> bool:
        # bug5: 专属码不验证使用者
        if code not in self.codes:
            return False
        return True
