"""兑换码 - 修复验证测试"""
import pytest, sys, os, threading
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

    def test_concurrent_redeem_only_one_succeeds(self):
        rs = RedeemSystem()
        rs.codes["HOT1"] = Code("HOT1")
        results = []
        barrier = threading.Barrier(200)

        def attempt(i):
            barrier.wait()
            results.append(rs.redeem_code("HOT1", f"p{i}"))

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert results.count(True) == 1
        assert results.count(False) == 199
        assert sum(len(v) for v in rs.records.values()) == 1

    def test_expired_code_cannot_be_redeemed(self):
        rs = RedeemSystem()
        rs.codes["OLD1"] = Code("OLD1", expired=True)
        assert rs.redeem_code("OLD1", "p1") == False


class TestGenerateUnique:
    def test_generated_code_is_unique(self):
        rs = RedeemSystem()
        rs.codes["ABC123"] = Code("ABC123")
        code = rs.generate_code()
        assert code != "ABC123"

    def test_many_generated_codes_all_unique(self):
        rs = RedeemSystem()
        codes = {rs.generate_code(length=4) for _ in range(500)}
        assert len(codes) == 500
        assert len(rs.codes) == 500


class TestPlayerTypeLimit:
    def test_new_user_code_cannot_be_used_by_old_user(self):
        rs = RedeemSystem()
        rs.codes["NEW1"] = Code("NEW1", type="new_user_only")
        assert rs.check_redeem_limit("NEW1", "p1", "old") == False

    def test_new_user_code_ok_for_new_user(self):
        rs = RedeemSystem()
        rs.codes["NEW1"] = Code("NEW1", type="new_user_only")
        assert rs.check_redeem_limit("NEW1", "p1", "new") == True

    def test_same_type_code_limited_per_player(self):
        rs = RedeemSystem()
        rs.codes["G1"] = Code("G1", type="general")
        rs.codes["G2"] = Code("G2", type="general")
        assert rs.redeem_code("G1", "p1") == True
        assert rs.check_redeem_limit("G2", "p1", "old") == False
        assert rs.redeem_code("G2", "p1") == False


class TestGuestMigration:
    def test_guest_records_migrated_to_account(self):
        rs = RedeemSystem()
        rs.records["guest_1"] = ["CODE1", "CODE2"]
        rs.migrate_guest_records("guest_1", "player_1")
        assert "player_1" in rs.records
        assert len(rs.records["player_1"]) == 2

    def test_history_queryable_by_guest_id_after_binding(self):
        rs = RedeemSystem()
        rs.records["guest_1"] = ["CODE1"]
        rs.migrate_guest_records("guest_1", "player_1")
        assert rs.get_redeem_history("guest_1") == ["CODE1"]
        assert rs.get_redeem_history("player_1") == ["CODE1"]
        assert "guest_1" not in rs.records

    def test_migration_merges_with_existing_records(self):
        rs = RedeemSystem()
        rs.records["guest_1"] = ["CODE1", "CODE2"]
        rs.records["player_1"] = ["CODE2", "CODE3"]
        rs.migrate_guest_records("guest_1", "player_1")
        assert sorted(rs.records["player_1"]) == ["CODE1", "CODE2", "CODE3"]


class TestExclusiveCode:
    def test_exclusive_code_only_for_owner(self):
        rs = RedeemSystem()
        rs.codes["EXCL1"] = Code("EXCL1", type="exclusive", owner="p1")
        assert rs.verify_exclusive_code("EXCL1", "p2") == False
        assert rs.verify_exclusive_code("EXCL1", "p1") == True

    def test_exclusive_code_cannot_be_redeemed_by_other(self):
        rs = RedeemSystem()
        rs.codes["EXCL1"] = Code("EXCL1", type="exclusive", owner="p1")
        assert rs.redeem_code("EXCL1", "p2") == False
        assert rs.redeem_code("EXCL1", "p1") == True

    def test_code_types_are_distinguishable(self):
        rs = RedeemSystem()
        rs.codes["G1"] = Code("G1", type="general")
        rs.codes["E1"] = Code("E1", type="exclusive", owner="p1")
        assert rs.get_code_type("G1") == "general"
        assert rs.get_code_type("E1") == "exclusive"
        assert rs.get_code_type("MISSING") is None
