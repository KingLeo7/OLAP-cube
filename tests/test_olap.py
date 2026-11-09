import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import olap
from app import app


def spec(rows=("location", "city"), cols=("time", "quarter"), filters=None):
    return {"rows": {"dim": rows[0], "level": rows[1]},
            "cols": {"dim": cols[0], "level": cols[1]},
            "filters": filters or {}}


class OlapTests(unittest.TestCase):
    def test_grand_total_matches_report(self):
        self.assertEqual(olap.query(spec())["grand"], 671.0)

    def test_rollup_and_drilldown_keep_totals(self):
        quarter = olap.query(spec(cols=("time", "quarter")))
        month = olap.query(spec(cols=("time", "month")))
        year = olap.query(spec(cols=("time", "year")))
        self.assertEqual(quarter["grand"], month["grand"])
        self.assertEqual(quarter["grand"], year["grand"])
        self.assertEqual(len(month["cols"]), 12)
        self.assertEqual(year["cols"], ["2025"])

    def test_bhubaneswar_quarters(self):
        r = olap.query(spec())
        i = r["rows"].index("Bhubaneswar")
        self.assertEqual(r["matrix"][i], [62.0, 72.0, 82.0, 95.0])

    def test_slice(self):
        r = olap.query(spec(filters={"quarter": ["Q4"]}))
        self.assertEqual(r["cols"], ["Q4"])
        self.assertEqual(r["grand"], 203.0)
        self.assertEqual(r["ops"][-2]["type"], "slice")

    def test_dice(self):
        r = olap.query(spec(rows=("product", "category"),
                            filters={"city": ["Bhubaneswar", "Cuttack"],
                                     "category": ["Electronics", "Clothing"],
                                     "quarter": ["Q1", "Q2"]}))
        self.assertEqual(r["grand"], 45 + 27 + 30 + 21)
        self.assertIn("dice", [o["type"] for o in r["ops"]])

    def test_pivot_swaps_axes(self):
        a = olap.query(spec(filters={"quarter": ["Q4"]}))
        b = olap.query(spec(rows=("time", "quarter"), cols=("location", "city"),
                            filters={"quarter": ["Q4"]}))
        self.assertEqual(a["grand"], b["grand"])
        self.assertEqual(a["rows"], b["cols"])

    def test_remove_dimension(self):
        r = olap.query(spec(cols=("time", "all")))
        self.assertEqual(r["cols"], ["All"])
        self.assertEqual(r["grand"], 671.0)

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            olap.query(spec(rows=("time", "city")))
        with self.assertRaises(ValueError):
            olap.query(spec(rows=("time", "year"), cols=("time", "month")))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def test_pages_and_api(self):
        self.assertEqual(self.c.get("/").status_code, 200)
        self.assertEqual(self.c.get("/api/meta").get_json()["facts"], 216)
        r = self.c.post("/api/query", json=spec())
        self.assertEqual(r.get_json()["grand"], 671.0)
        self.assertEqual(self.c.post("/api/query", json={}).status_code, 400)
        bad = self.c.post("/api/query", json=spec(rows=("time", "city")))
        self.assertEqual(bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
