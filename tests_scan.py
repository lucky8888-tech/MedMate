import os
import json
import tempfile
import unittest

from medmate import match_from_text
import app as app_module


class TestMatchFromText(unittest.TestCase):
    """Tests for the OCR text -> medicine matcher (pure text, no image needed)."""

    def test_confident_match(self):
        r = match_from_text("Dolo 650 Paracetamol 650 mg tablet")
        self.assertFalse(r["uncertain"])
        self.assertEqual(r["matches"][0]["brand"], "Dolo 650")
        self.assertIn("strength", r["matches"][0]["signals"])

    def test_partial_match_is_uncertain(self):
        r = match_from_text("Crocin 500")
        self.assertTrue(r["uncertain"])
        self.assertIsNotNone(r["warning"])

    def test_ambiguous_match_is_uncertain(self):
        r = match_from_text("Paracetamol 500 mg")
        self.assertTrue(r["uncertain"])
        self.assertGreaterEqual(len(r["matches"]), 2)
        self.assertEqual(r["matches"][0]["score"], r["matches"][1]["score"])

    def test_nothing_found_is_uncertain(self):
        r = match_from_text("xyz random gibberish nothing here")
        self.assertTrue(r["uncertain"])
        self.assertEqual(r["matches"], [])
        self.assertIn("colour", r["warning"].lower())

    def test_combination_strength_match(self):
        r = match_from_text("Combiflam Ibuprofen Paracetamol 400 mg + 325 mg")
        self.assertFalse(r["uncertain"])
        self.assertEqual(r["matches"][0]["brand"], "Combiflam")
        self.assertIn("strength", r["matches"][0]["signals"])


class TestFeedbackApi(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.tmp.close()
        app_module.FEEDBACK_FILE = self.tmp.name

    def tearDown(self):
        for p in (app_module.FEEDBACK_FILE, app_module.FEEDBACK_FILE + ".tmp"):
            if os.path.exists(p):
                os.remove(p)

    def test_feedback_success(self):
        resp = self.client.post("/api/feedback", json={"message": "Great app!", "category": "general"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])
        with open(app_module.FEEDBACK_FILE, encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["message"], "Great app!")

    def test_feedback_empty_rejected(self):
        resp = self.client.post("/api/feedback", json={"message": "   "})
        self.assertEqual(resp.status_code, 400)

    def test_feedback_too_long_rejected(self):
        resp = self.client.post("/api/feedback", json={"message": "x" * (app_module.FEEDBACK_MAX_LEN + 1)})
        self.assertEqual(resp.status_code, 400)


class TestScanApi(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_scan_status_shape(self):
        resp = self.client.get("/api/scan/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("ocr_available", data)
        self.assertIn("binary_ready", data)

    def test_scan_without_image_returns_400(self):
        resp = self.client.post("/api/scan", data={})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
