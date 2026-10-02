"""兑换码"""
from dataclasses import dataclass, field
import random
import threading

@dataclass
class Code:
    code: str
    used: bool = False
    type: str = "general"  # general/exclusive/new_user_only
    expired: bool = False
    owner: str = None  # 专属码的所有者

class RedeemSystem:
    def __init__(self, max_redeems_per_player: int = 10):
        self.codes: dict[str, Code] = {}
        self.records: dict[str, list] = {}
        self.max_redeems_per_player = max_redeems_per_player
        self._lock = threading.Lock()

    def redeem_code(self, code: str, player_id: str, player_type: str = "normal") -> bool:
        # 检查+标记+发奖在同一个锁内完成，保证原子性
        with self._lock:
            if code not in self.codes:
                return False
            c = self.codes[code]
            if c.used or c.expired:
                return False
            if not self.check_redeem_limit(code, player_id, player_type):
                return False
            if not self.verify_exclusive_code(code, player_id):
                return False
            c.used = True
            # 发奖励
            self.records.setdefault(player_id, []).append(code)
            return True

    def generate_code(self, length: int = 8) -> str:
        # 生成后查重，冲突则重新生成
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        while True:
            code = "".join(random.choice(chars) for _ in range(length))
            if code not in self.codes:
                self.codes[code] = Code(code)
                return code

    def check_redeem_limit(self, code: str, player_id: str, player_type: str) -> bool:
        if code not in self.codes:
            return False
        c = self.codes[code]
        if c.expired:
            return False
        # 新手码只允许新玩家使用
        if c.type == "new_user_only" and player_type != "new":
            return False
        # 每个玩家的兑换次数上限
        if len(self.records.get(player_id, [])) >= self.max_redeems_per_player:
            return False
        return True

    def migrate_guest_records(self, guest_id: str, player_id: str) -> bool:
        # 账号绑定时把游客身份下的兑换记录迁移到正式账号
        guest_records = self.records.pop(guest_id, [])
        if guest_records:
            self.records.setdefault(player_id, []).extend(guest_records)
        return True

    def verify_exclusive_code(self, code: str, player_id: str) -> bool:
        if code not in self.codes:
            return False
        c = self.codes[code]
        # 专属码只有所有者本人可用
        if c.type == "exclusive":
            return c.owner == player_id
        return True
