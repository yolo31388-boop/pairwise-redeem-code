"""兑换码与礼包系统。

修复六类问题：
1. 每个码有单用户兑换次数限制（max_per_user）。
2. 有效期同时校验开始与结束时间。
3. 礼包内容支持随机抽取与保底（pity）机制。
4. 码区分类型：general / exclusive / one_time，专属码绑定用户。
5. 码使用 secrets 随机字符串生成，不可预测。
6. 兑换幂等：同一 request_id 重复提交只生效一次。
"""
from dataclasses import dataclass, field
import secrets
import string
import time

CODE_ALPHABET = string.ascii_uppercase + string.digits
VALID_TYPES = ("general", "exclusive", "one_time")


class RedeemError(Exception):
    """兑换失败基类。"""


class CodeNotFoundError(RedeemError):
    pass


class CodeExpiredError(RedeemError):
    pass


class CodeNotStartedError(RedeemError):
    pass


class UserNotBoundError(RedeemError):
    pass


class UserLimitReachedError(RedeemError):
    pass


class CodeExhaustedError(RedeemError):
    pass


@dataclass
class RedeemCode:
    code: str
    type: str = "general"  # general / exclusive / one_time
    content: list = field(default_factory=list)
    start_time: float = 0
    end_time: float = 9_999_999_999
    max_per_user: int = 1
    bound_user: str = None
    # 一次性码是否还有效
    used: bool = False
    # 随机奖池的完整配置（dict 形式，见 open_gift）
    pool: dict = None

    @property
    def pool_config(self):
        if isinstance(self.pool, dict):
            return self.pool
        if isinstance(self.content, dict):
            return self.content
        return None


def _random_code(length: int) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def generate_random_code(length: int = 12) -> str:
    """对外暴露的随机码生成器：不可预测。"""
    return _random_code(length)


class RedeemSystem:
    def __init__(self, clock=time.time):
        self.codes = {}
        # user -> {code: 兑换次数}
        self.user_usage = {}
        # request_id -> (user, code, 首次返回内容)，保证幂等
        self.requests = {}
        # user -> 已兑换码集合（与历史结构保持一致）
        self.redeemed = {}
        # user -> {gift_id: 已开启次数}，用于保底计数
        self.open_counts = {}
        self._clock = clock

    # ------------------------------------------------------------------
    # 生成
    # ------------------------------------------------------------------
    def generate_code(self, type="general", content=None, count=1,
                      start_time=0, end_time=9_999_999_999,
                      max_per_user=1, bound_user=None, length=12,
                      pool=None):
        if type not in VALID_TYPES:
            raise ValueError(f"未知兑换码类型: {type}")
        if content is None:
            content = []
        codes = []
        for _ in range(count):
            value = _random_code(length)
            while value in self.codes:
                value = _random_code(length)
            rc = RedeemCode(
                code=value,
                type=type,
                content=list(content) if not isinstance(content, dict) else dict(content),
                start_time=start_time,
                end_time=end_time,
                max_per_user=max_per_user,
                bound_user=bound_user,
                pool=pool,
            )
            self.codes[value] = rc
            codes.append(value)
        return codes

    def add_code(self, code, **kwargs):
        """手工登记一个码（测试 / 运营导入）。"""
        kwargs.setdefault("type", "general")
        kwargs.setdefault("content", [])
        rc = RedeemCode(code=code, **kwargs)
        self.codes[code] = rc
        return rc

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def validate_code(self, code, user_id=None, now=None):
        rc = self.codes.get(code)
        if rc is None:
            return False
        return self._validate(rc, user_id, now) is None

    def _check_window(self, rc, now):
        if now < rc.start_time:
            raise CodeNotStartedError("兑换码尚未生效")
        if now > rc.end_time:
            raise CodeExpiredError("兑换码已过期")

    def _validate(self, rc, user_id, now):
        """返回错误对象；None 表示通过。"""
        if now is None:
            now = self._clock()
        if now < rc.start_time:
            return CodeNotStartedError("兑换码尚未生效")
        if now > rc.end_time:
            return CodeExpiredError("兑换码已过期")
        if rc.type == "one_time" and rc.used:
            return CodeExhaustedError("一次性码已被使用")
        if rc.type == "exclusive":
            if rc.bound_user is None:
                return UserNotBoundError("专属码未绑定用户")
            if user_id is None or user_id != rc.bound_user:
                return UserNotBoundError("专属码只能由绑定用户兑换")
        if user_id is not None:
            used = self.user_usage.get(user_id, {}).get(rc.code, 0)
            if used >= rc.max_per_user:
                return UserLimitReachedError("已达到单用户兑换次数上限")
        return None

    # ------------------------------------------------------------------
    # 兑换（幂等）
    # ------------------------------------------------------------------
    def redeem(self, code, user_id, request_id=None, now=None):
        rc = self.codes.get(code)
        if rc is None:
            return None

        # 幂等：同一请求重复提交，直接返回首次结果且不重复发奖。
        if request_id is not None:
            cached = self.requests.get(request_id)
            if cached is not None:
                cached_user, cached_code, cached_result = cached
                if cached_user == user_id and cached_code == code:
                    return list(cached_result) if isinstance(cached_result, list) else cached_result
                return None

        if self._validate(rc, user_id, now) is not None:
            return None

        result = list(rc.content)
        # 记账
        self.user_usage.setdefault(user_id, {})[rc.code] = \
            self.user_usage.get(user_id, {}).get(rc.code, 0) + 1
        self.redeemed.setdefault(user_id, set()).add(code)
        if rc.type == "one_time":
            rc.used = True
        if request_id is not None:
            self.requests[request_id] = (user_id, code, list(result))
        return result

    # ------------------------------------------------------------------
    # 礼包开启（随机 + 保底）
    # ------------------------------------------------------------------
    def open_gift(self, gift_id, user_id=None, draws=1):
        rc = self.codes.get(gift_id)
        if rc is None:
            return []

        config = rc.pool_config
        if config is None:
            return list(rc.content)

        pool = config.get("pool", config.get("items", []))
        if isinstance(pool, dict):
            entries = []
            for name, weight in pool.items():
                if isinstance(weight, (list, tuple)):
                    weight, rare = weight[0], bool(weight[1]) if len(weight) > 1 else False
                    entries.append({"item": name, "weight": weight, "rare": rare})
                else:
                    entries.append({"item": name, "weight": weight, "rare": False})
        else:
            entries = []
            for entry in pool:
                if isinstance(entry, dict):
                    item = entry.get("item", entry.get("name"))
                    weight = entry.get("weight", 1)
                    rare = entry.get("rare", entry.get("rarity") == "rare")
                elif isinstance(entry, (list, tuple)):
                    item, weight = entry[0], entry[1] if len(entry) > 1 else 1
                    rare = len(entry) > 2 and bool(entry[2])
                else:
                    item, weight, rare = entry, 1, False
                entries.append({"item": item, "weight": weight, "rare": bool(rare)})

        normal = [e for e in entries if not e["rare"]]
        rare = [e for e in entries if e["rare"]]
        pity_threshold = config.get("pity", config.get("guarantee", 0))

        counts = self.open_counts.setdefault(user_id, {}) if user_id is not None else {}
        results = []
        for _ in range(max(1, int(draws))):
            count_since_rare = counts.get(gift_id, 0)
            force_rare = bool(rare) and pity_threshold and count_since_rare + 1 >= pity_threshold
            chosen = self._draw(rare if force_rare else (entries or rare))
            results.append(chosen["item"])
            if chosen["rare"]:
                counts[gift_id] = 0
            else:
                counts[gift_id] = count_since_rare + 1
        return results

    @staticmethod
    def _draw(entries):
        total = sum(max(0, e["weight"]) for e in entries)
        if total <= 0:
            return secrets.choice(entries)
        point = secrets.randbelow(total)
        upto = 0
        for entry in entries:
            upto += max(0, entry["weight"])
            if point < upto:
                return entry
        return entries[-1]
