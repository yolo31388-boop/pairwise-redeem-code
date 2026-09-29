"""兑换码礼包系统"""
from dataclasses import dataclass
import random
import secrets
import string
import time


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
    PITY_THRESHOLD = 10  # 连续未中稀有物品后触发保底
    CODE_LENGTH = 16

    def __init__(self):
        self.codes: dict[str, RedeemCode] = {}
        self.redeemed: dict[str, set] = {}  # user -> set of codes
        self.redeem_counts: dict[tuple, int] = {}  # (user, code) -> 已兑换次数
        self.global_redeemed: set = set()  # 一次性码的全局兑换记录
        self.idempotency_keys: dict[str, object] = {}  # request_id -> 首次兑换结果
        self.pity_counters: dict[tuple, int] = {}  # (user, gift) -> 连续未中稀有次数

    def generate_code(self, type, content, count=1, max_per_user=1,
                      bound_user=None, start_time=0, end_time=9999999999):
        # 修复bug5: 用加密安全的随机字符串，不可预测
        alphabet = string.ascii_uppercase + string.digits
        codes = []
        for _ in range(count):
            while True:
                code = "".join(secrets.choice(alphabet)
                               for _ in range(self.CODE_LENGTH))
                if code not in self.codes:
                    break
            self.codes[code] = RedeemCode(
                code, type, content, start_time, end_time,
                max_per_user=max_per_user, bound_user=bound_user,
            )
            codes.append(code)
        return codes

    def validate_code(self, code, user_id, now=None):
        rc = self.codes.get(code)
        if not rc:
            return False
        # 修复bug2: 同时检查开始和结束时间
        now = time.time() if now is None else now
        if not (rc.start_time <= now <= rc.end_time):
            return False
        # 修复bug4: 区分类型，专属码校验绑定用户，一次性码校验全局未用
        if rc.type == "exclusive" and rc.bound_user != user_id:
            return False
        if rc.type == "one_time" and code in self.global_redeemed:
            return False
        # 修复bug1: 单用户兑换次数限制
        if self.redeem_counts.get((user_id, code), 0) >= rc.max_per_user:
            return False
        return True

    def redeem(self, code, user_id, request_id=None):
        # 修复bug6: 幂等，同一请求重复提交返回首次结果，不重复发奖
        if request_id is not None and request_id in self.idempotency_keys:
            return self.idempotency_keys[request_id]
        if not self.validate_code(code, user_id):
            result = None
        else:
            rc = self.codes[code]
            self.redeemed.setdefault(user_id, set()).add(code)
            self.redeem_counts[(user_id, code)] = \
                self.redeem_counts.get((user_id, code), 0) + 1
            if rc.type == "one_time":
                self.global_redeemed.add(code)
            result = rc.content
        if request_id is not None:
            self.idempotency_keys[request_id] = result
        return result

    def open_gift(self, gift_id, user_id):
        # 修复bug3: 随机抽取内容，并带保底机制
        rc = self.codes.get(gift_id)
        if not rc or not rc.content:
            return []
        content = rc.content
        weights = [item.get("weight", 1) if isinstance(item, dict) else 1
                   for item in content]
        rare = [item for item in content
                if isinstance(item, dict) and item.get("rare")]
        key = (user_id, gift_id)
        self.pity_counters[key] = self.pity_counters.get(key, 0) + 1
        if rare and self.pity_counters[key] >= self.PITY_THRESHOLD:
            item = random.choice(rare)  # 保底：必出稀有
            self.pity_counters[key] = 0
        else:
            item = random.choices(content, weights=weights, k=1)[0]
            if item in rare:
                self.pity_counters[key] = 0
        return [item]
