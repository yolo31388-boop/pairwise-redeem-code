"""兑换码测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import RedeemSystem, RedeemCode

class TestGenerate:
    def test_code_unpredictable(self):
        rs = RedeemSystem()
        codes = rs.generate_code("general", ["item"], 5)
        # 不应是连续可预测的
        assert not all(c.startswith("CODE") for c in codes), "兑换码可预测"

class TestRedeem:
    def test_redeem_dedup(self):
        rs = RedeemSystem()
        rs.codes["TEST1"] = RedeemCode("TEST1", "general", ["item"], 0, 9999999999)
        r1 = rs.redeem("TEST1", "p1")
        r2 = rs.redeem("TEST1", "p1")
        # 第二次应失败或返回空
        assert r2 != r1 or len(rs.redeemed["p1"]) == 1, "兑换未去重"
