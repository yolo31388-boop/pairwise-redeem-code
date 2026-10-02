"""兑换码系统

修复点：
1. redeem_code 全程加锁，查-标记-发奖原子化
2. generate_code 循环生成直到不与已有码重复
3. check_redeem_limit 校验过期、玩家类型、同类型兑换次数、专属码归属
4. migrate_guest_records 把游客兑换记录合并迁移到正式账号
5. verify_exclusive_code 校验专属码只能所有者使用
"""
from dataclasses import dataclass
import random
import threading

GENERAL = "general"
EXCLUSIVE = "exclusive"
NEW_USER_ONLY = "new_user_only"

_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@dataclass
class Code:
    code: str
    used: bool = False
    type: str = GENERAL  # general / exclusive / new_user_only
    expired: bool = False
    owner: str | None = None  # 专属码的所有者


class RedeemSystem:
    def __init__(self):
        self.codes: dict[str, Code] = {}
        self.records: dict[str, list[str]] = {}
        self.used_codes: set[str] = set()
        # 兑换全局锁：保证“查状态 -> 标记已用 -> 发奖记录”临界区原子，
        # 等价于数据库事务/分布式锁在内存实现里的作用。
        self._lock = threading.RLock()
        # 游客ID -> 正式账号ID 的映射，迁移后历史记录仍可追溯
        self._guest_aliases: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 兑换
    # ------------------------------------------------------------------
    def redeem_code(self, code: str, player_id: str, player_type: str | None = None) -> bool:
        with self._lock:
            target = self.codes.get(code)
            if target is None or target.used or target.expired:
                return False
            if not self._check_limit(target, player_id, player_type):
                return False

            target.used = True
            self.used_codes.add(code)

            owner_id = self._canonical_id(player_id)
            self.records.setdefault(owner_id, []).append(code)
            return True

    def _check_limit(self, target: Code, player_id: str, player_type: str | None) -> bool:
        # 新人专享码：只有 new 玩家可用；player_type 未知时不做此项限制
        if target.type == NEW_USER_ONLY and player_type is not None and player_type != "new":
            return False
        # 专属码只能所有者兑换
        if target.type == EXCLUSIVE and not self.verify_exclusive_code(target.code, player_id):
            return False
        # 同一类型的码每个玩家限兑一次
        owner_id = self._canonical_id(player_id)
        for redeemed in self.records.get(owner_id, []):
            redeemed_code = self.codes.get(redeemed)
            if redeemed_code is not None and redeemed_code.type == target.type:
                return False
        return True

    # ------------------------------------------------------------------
    # 生成
    # ------------------------------------------------------------------
    def generate_code(
        self,
        length: int = 8,
        code_type: str = GENERAL,
        owner: str | None = None,
    ) -> str:
        with self._lock:
            for _ in range(1000):
                code = "".join(random.choice(_CHARS) for _ in range(length))
                if code not in self.codes and code not in self.used_codes:
                    self.codes[code] = Code(code, type=code_type, owner=owner)
                    return code
            raise RuntimeError("无法生成唯一兑换码，请增加码长度")

    # ------------------------------------------------------------------
    # 限制校验
    # ------------------------------------------------------------------
    def check_redeem_limit(self, code: str, player_id: str, player_type: str) -> bool:
        with self._lock:
            target = self.codes.get(code)
            if target is None or target.expired or target.used:
                return False
            return self._check_limit(target, player_id, player_type)

    # ------------------------------------------------------------------
    # 游客记录迁移
    # ------------------------------------------------------------------
    def migrate_guest_records(self, guest_id: str, player_id: str) -> bool:
        with self._lock:
            guest_records = self.records.get(guest_id)
            if guest_records is None:
                return False

            merged = list(self.records.get(player_id, []))
            for code in guest_records:
                if code not in merged:
                    merged.append(code)

            self.records[player_id] = merged
            del self.records[guest_id]

            root = self._canonical_id(player_id)
            self._guest_aliases[guest_id] = root
            # 若该游客之前还吸收过更早的游客身份，一并把旧别名指过来
            for alias, target in list(self._guest_aliases.items()):
                if target == guest_id:
                    self._guest_aliases[alias] = root
            return True

    # ------------------------------------------------------------------
    # 专属码
    # ------------------------------------------------------------------
    def verify_exclusive_code(self, code: str, player_id: str) -> bool:
        with self._lock:
            target = self.codes.get(code)
            if target is None:
                return False
            if target.type != EXCLUSIVE:
                return True
            return target.owner == player_id

    # ------------------------------------------------------------------
    # 查询辅助
    # ------------------------------------------------------------------
    def get_code_type(self, code: str) -> str | None:
        with self._lock:
            target = self.codes.get(code)
            return None if target is None else target.type

    def get_redeem_history(self, player_id: str) -> list[str]:
        with self._lock:
            return list(self.records.get(self._canonical_id(player_id), []))

    def _canonical_id(self, player_id: str) -> str:
        seen = set()
        current = player_id
        while current in self._guest_aliases and current not in seen:
            seen.add(current)
            current = self._guest_aliases[current]
        return current
