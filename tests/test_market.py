import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import market

class MarketTests(unittest.TestCase):
    def test_steampy_result_and_subid(self):
        def fake(url):
            self.assertIn("subId=443",url)
            self.assertIn("type=subid",url)
            return {"success":True,"result":{"id":123,"keyPrice":"8.90"}}
        with patch.object(market,"fetch",side_effect=fake):
            offer=market.steampy(435150,[443])
        self.assertEqual(offer["price"],8.9)
        self.assertIn("cdkDetail",offer["url"])

    def test_cici_rows_must_match_package(self):
        response={"code":200,"rows":[{"gameId":443,"lastLowSellPrice":9.8},
                                     {"gameId":999,"lastLowSellPrice":1.0}]}
        with patch.object(market,"fetch",return_value=response):
            offer=market.steamcici(435150,[443])
        self.assertEqual(offer["price"],9.8)
        self.assertEqual(offer["kind"],"historical_listing")

    def test_reject_placeholder_and_keep_reasonable_offers(self):
        entries=[
            {"platform":"SteamPY","price":0.1},
            {"platform":"SteamPY","price":8.5},
            {"platform":"SteamCiCi","price":22.0},
        ]
        result=market.clean_offers(entries,30.4)
        self.assertEqual([item["price"] for item in result],[8.5,22.0])
        self.assertEqual(market.clean_offers([{"platform":"SteamPY","price":0.1}],30.4),[])

    def test_prices_are_not_claimed_live(self):
        with patch.object(market,"steampy",return_value={"price":8.0}), \
             patch.object(market,"steamcici",return_value=None), \
             patch.object(market,"steamraw",return_value=None):
            g=market.enrich({"appid":435150,"steam_subids":[443]}, {})
        self.assertIsNone(g["key_price"])
        self.assertEqual(len(g["key_offers"]),1)

if __name__=="__main__":
    unittest.main()
