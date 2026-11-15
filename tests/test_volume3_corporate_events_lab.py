import copy
import unittest
from examples.volume3_corporate_events_lab import audit, load

class CorporateEventsLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_fixture_is_frozen_synthetic(self):
        self.assertEqual(self.data["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(len(self.data["events"]), 7)

    def test_late_vendor_receipt_is_not_available_at_decision(self):
        result = audit(self.data)
        event = next(item for item in result["events"] if item["event_id"] == "EV03")
        self.assertIn("NOT_RECEIVED_BY_DECISION", event["exclusion_reasons"])

    def test_mapping_availability_and_effective_time_are_both_required(self):
        result = audit(self.data)
        event = next(item for item in result["events"] if item["event_id"] == "EV04")
        self.assertEqual(event["mapping_status"], "UNKNOWN_MAPPING")

    def test_ambiguous_historical_alias_is_not_guessed(self):
        result = audit(self.data)
        event = next(item for item in result["events"] if item["event_id"] == "EV07")
        self.assertEqual(event["mapping_status"], "AMBIGUOUS_MAPPING")

    def test_overlapping_events_are_clustered_not_independent(self):
        result = audit(self.data)
        self.assertEqual(result["overlap_event_ids"], ["EV01", "EV02"])

    def test_incomplete_event_window_is_not_imputed(self):
        result = audit(self.data)
        event = next(item for item in result["events"] if item["event_id"] == "EV06")
        self.assertEqual(event["window_status"], "INCOMPLETE_WINDOW")

    def test_control_adjusted_car_and_placebo_are_reported_separately(self):
        result = audit(self.data)
        self.assertEqual({item["event_id"] for item in result["event_results"]}, {"EV05"})
        row = result["event_results"][0]
        self.assertAlmostEqual(row["control_adjusted_car"], row["event_car"] - row["matched_control_car"])
        self.assertIn("placebo_car", row)

    def test_future_returns_cannot_change_pit_eligibility_or_mapping(self):
        changed = copy.deepcopy(self.data)
        before = [(item["event_id"], item["pit_eligible"], item["issuer_id"]) for item in audit(changed)["events"]]
        for row in changed["observations"]:
            row["security_return"] += 0.25
        after = [(item["event_id"], item["pit_eligible"], item["issuer_id"]) for item in audit(changed)["events"]]
        self.assertEqual(before, after)

    def test_strict_time_equality_is_rejected(self):
        changed = copy.deepcopy(self.data)
        changed["events"][0]["received_at"] = changed["events"][0]["decision_at"]
        event = next(item for item in audit(changed)["events"] if item["event_id"] == "EV01")
        self.assertIn("NOT_RECEIVED_BY_DECISION", event["exclusion_reasons"])

    def test_duplicate_offset_rows_are_rejected(self):
        changed = copy.deepcopy(self.data)
        changed["observations"].append(copy.deepcopy(changed["observations"][0]))
        with self.assertRaises(ValueError):
            audit(changed)

    def test_synthetic_results_never_claim_market_validation(self):
        result = audit(self.data)
        self.assertFalse(result["market_pit_proven"])
        self.assertFalse(result["causal_effect_proven"])
        self.assertFalse(result["real_event_alpha_proven"])
        self.assertFalse(result["execution_proven"])

if __name__ == "__main__":
    unittest.main()
