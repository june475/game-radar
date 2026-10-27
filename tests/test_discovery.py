import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from discovery import classify,parse_release,discovery_score,parse_ids

class DiscoveryTests(unittest.TestCase):
    def test_date_formats(self):
        self.assertEqual(parse_release("2026 年 10 月 27 日"),dt.date(2026,10,27))
        self.assertEqual(parse_release("Oct 27, 2026"),dt.date(2026,10,27))
        self.assertIsNone(parse_release("即将推出"))

    def test_low_price_high_rating_discovery(self):
        self.assertIsNone(discovery_score({"review_pct":84,"review_count":2000,"price":8}))
        self.assertIsNone(discovery_score({"review_pct":97,"review_count":50,"price":8}))
        self.assertIsNone(discovery_score({"review_pct":97,"review_count":2000,"price":45}))
        low=discovery_score({"review_pct":96,"review_count":2000,"price":9})
        high=discovery_score({"review_pct":96,"review_count":2000,"price":35})
        self.assertGreater(low,high)
        self.assertEqual(classify("explore","Sep 1, 2019",False,dt.date(2026,10,27)),"explore")
        self.assertEqual(parse_ids('{"results_html":"<a data-ds-appid=\\\"12345\\\"></a>"}'),[12345])

    def test_independent_pools(self):
        today=dt.date(2026,10,27)
        self.assertEqual(classify("new","Oct 26, 2026",False,today),"new")
        self.assertIsNone(classify("deal","Oct 26, 2026",False,today))
        self.assertEqual(classify("deal","Sep 1, 2020",False,today),"deal")
        self.assertIsNone(classify("new","Sep 1, 2020",False,today))
        self.assertIsNone(classify("new","未知",False,today))
        self.assertIsNone(classify("new","Nov 1, 2026",True,today))

if __name__=="__main__":
    unittest.main()
