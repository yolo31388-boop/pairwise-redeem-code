"""兑换码 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from redeem.code import RedeemSystem, Code

class TestAtomicRedeem:
    def test_same_code_cannot_be_redeemed_twice(self):
        rs = RedeemSystem()
        rs.codes["CODE1"] = Code("CODE1")
        r1 = rs.redeem_code("CODE1", "p1")
        r2 = rs.redeem_code("CODE1", "p2")
        assert r1 == True
        assert r2 == False

class TestGenerateUnique:
    def test_generated_code_is_unique(self):
        rs = RedeemSystem()
        rs.codes["ABC123"] = Code("ABC123")
        # 生成的码不应该和已有的重复
        code = rs.generate_code()
        assert code != "ABC123"

class TestPlayerTypeLimit:
    def test_new_user_code_cannot_be_used_by_old_user(self):
        rs = RedeemSystem()
        rs.codes["NEW1"] = Code("NEW1", type="new_user_only")
        assert rs.check_redeem_limit("NEW1", "p1", "old") == False

class TestGuestMigration:
    def test_guest_records_migrated_to_account(self):
        rs = RedeemSystem()
        rs.records["guest_1"] = ["CODE1", "CODE2"]
        rs.migrate_guest_records("guest_1", "player_1")
        assert "player_1" in rs.records
        assert len(rs.records["player_1"]) == 2

class TestExclusiveCode:
    def test_exclusive_code_only_for_owner(self):
        rs = RedeemSystem()
        rs.codes["EXCL1"] = Code("EXCL1", type="exclusive", owner="p1")
        assert rs.verify_exclusive_code("EXCL1", "p2") == False
        assert rs.verify_exclusive_code("EXCL1", "p1") == True
