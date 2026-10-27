import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import hot_low

class HotLowTests(unittest.TestCase):
    def test_verified_low_requires_matching_source_and_low_price(self):
        source={"source":"SteamRaw","price":28,"url":"https://steamraw.com/app/1"}
        self.assertTrue(hot_low.valid_low(28.00,source))
        self.assertTrue(hot_low.valid_low(27.99,source))
        self.assertFalse(hot_low.valid_low(35.0,source))
        self.assertFalse(hot_low.valid_low(28,{"source":"project_history","price":28}))
        self.assertFalse(hot_low.valid_low(28,None))

    def test_popularity_scan_has_no_taste_tags_or_user_preference_filters(self):
        observed=[]
        def mock_search(url,timeout=12):
            observed.append(url)
            return {"results_html":'<a data-ds-appid="1086940"></a><a data-ds-appid="570"></a>'}
        with patch.object(hot_low,"request_json",side_effect=mock_search):
            ids=hot_low.popular_deals(pages=1)
        self.assertEqual(ids,[1086940,570])
        self.assertIn("filter=topsellers",observed[0])
        self.assertIn("specials=1",observed[0])
        self.assertNotIn("tags=",observed[0])

if __name__=="__main__":
    unittest.main()
