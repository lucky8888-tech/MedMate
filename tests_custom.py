import unittest
from medmate import suggest

class TestMedMateRules(unittest.TestCase):

    def test_1_do_not_substitute(self):
        """Test Case 1: Verifies 'Do Not Substitute' flag stops suggestions."""
        res = suggest("M001", [], do_not_substitute=True)
        self.assertEqual(len(res["alternatives"]), 0)
        self.assertIn("Do Not Substitute", res["message"])

    def test_2_missing_inactive_data_exclusion(self):
        """Test Case 2: Excludes products with blank inactive ingredients when allergies exist."""
        res = suggest("M001", ["Dye R"])
        excluded_ids = [item["id"] for item in res["excluded"]]
        self.assertIn("M003", excluded_ids)
        m003_entry = next(item for item in res["excluded"] if item["id"] == "M003")
        self.assertIn("data missing", m003_entry["reason"])

    def test_3_drug_class_allergy_trigger(self):
        """Test Case 3: Triggers safety alert/exclusion for drug class allergies."""
        res = suggest("M001", ["Analgesic"])
        self.assertEqual(len(res["alternatives"]), 0)

    def test_4_prescribed_medicine_allergy_warning(self):
        """Test Case 4: Flags alert when prescribed medicine matches allergy list."""
        res = suggest("M001", ["Zolvexol"])
        self.assertTrue(len(res["prescribed"]["flags"]) > 0)
        self.assertIn("ALERT", res["prescribed"]["flags"][0])

    def test_5_different_strength_exclusion(self):
        """Test Case 5: Ensures different strengths (M004 - 250mg) are completely ignored."""
        res = suggest("M001", [])
        alt_ids = [item["id"] for item in res["alternatives"]]
        excluded_ids = [item["id"] for item in res["excluded"]]
        self.assertNotIn("M004", alt_ids)
        self.assertNotIn("M004", excluded_ids)

if __name__ == "__main__":
    unittest.main()