import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import hot_low

class HotLowTests(unittest.TestCase):
    def test_discounted_game_has_no_history_dependency(self):
        with patch.object(hot_low,"popular_deals",return_value=[101]), \
             patch.object(hot_low,"details",return_value={
                 "name":"Popular Game","price_overview":{
                     "final":1999,"initial":3999,"discount_percent":50}}):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                previous=hot_low.OUTPUT
                hot_low.OUTPUT=Path(tmp)/"hot_low.json"
                try: result=hot_low.collect(max_checked=1)
                finally: hot_low.OUTPUT=previous
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["price"],19.99)
        self.assertEqual(result[0]["discount"],50)
        self.assertNotIn("low_verified",result[0])

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
