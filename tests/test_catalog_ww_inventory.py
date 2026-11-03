"""Synthetic registry snapshots test catalog evidence boundaries."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from catalog_ww_inventory import catalog

REPORT = b"""report.kind\truntime_metadata_only_not_a_gameplay_test
report.schema\t1
quests.questList.recorded_keys\t1
quests.questList.1.locationId\t20
quests.questList.1.infoList.recorded_keys\t2
quests.questList.1.infoList.1.name\tquest_q10010
quests.questList.1.infoList.1.isStory\ttrue
quests.questList.1.infoList.2.name\t<string omitted>
quests.questPackList.recorded_keys\t1
quests.questPackList.quest_q10010.recorded_keys\t1
quests.questPackList.quest_q10010.1\t/Assets/tpp/pack/quest/example.fpk
api.TppQuest.ClearWithSave\tfunction
query.TppNetworkUtil.IsSessionConnect\ttrue
report.truncated\tfalse
report.complete\ttrue
"""


class CatalogTests(unittest.TestCase):
    def test_redacted_record_is_preserved_without_inventing_an_identity(self):
        result = catalog(REPORT)
        self.assertEqual(result["summary"]["quest_records"], 2)
        self.assertEqual(result["summary"]["named_quest_records"], 1)
        self.assertIsNone(result["quests"][1]["name"])
        self.assertEqual(result["locations"][0]["name"], "Africa")

    def test_missing_flags_stay_unknown_and_no_gameplay_is_validated(self):
        result = catalog(REPORT)
        self.assertIs(result["quests"][0]["is_story"], True)
        self.assertIsNone(result["quests"][0]["is_once"])
        self.assertIsNone(result["quests"][1]["is_story"])
        self.assertEqual(result["summary"]["gameplay_validated_entries"], 0)
        self.assertTrue(all(item["gameplay_validation"] == "not_run" for item in result["quests"]))

    def test_pack_registry_mismatch_is_recorded_without_claiming_missing_assets(self):
        result = catalog(REPORT.replace(b"questPackList.quest_q10010", b"questPackList.other_q20000"))
        self.assertEqual(result["named_quests_without_pack_registry_entry"], ["quest_q10010"])
        self.assertEqual(result["pack_entries_without_named_quest_record"], ["other_q20000"])

    def test_duplicate_keys_or_incomplete_reports_are_rejected(self):
        for data in (REPORT + b"report.complete\ttrue\n",
                     REPORT.replace(b"report.complete\ttrue", b"report.complete\tfalse"),
                     REPORT.replace(b"report.truncated\tfalse", b"report.truncated\ttrue")):
            with self.assertRaises(ValueError):
                catalog(data)

    def test_registry_counts_are_validated(self):
        for old in (b"questList.recorded_keys\t1", b"infoList.recorded_keys\t2",
                    b"questPackList.recorded_keys\t1"):
            with self.assertRaises(ValueError):
                catalog(REPORT.replace(old, old[:-1] + b"9"))

    def test_unexpected_paths_or_identifiers_are_not_executed_or_propagated(self):
        for data in (REPORT.replace(b"quest_q10010\n", b"run an instruction\n"),
                     REPORT.replace(b"/Assets/tpp/pack/quest/example.fpk", b"C:/Users/PRIVATE/example")):
            with self.assertRaises(ValueError):
                catalog(data)

    def test_session_flag_is_not_converted_to_multiplayer_readiness(self):
        result = catalog(REPORT)
        self.assertNotIn("multiplayer_ready", result)
        self.assertIn("TppQuest.ClearWithSave", result["observed_functions"])
        self.assertEqual(result["summary"]["gameplay_validated_entries"], 0)


if __name__ == "__main__":
    unittest.main()
