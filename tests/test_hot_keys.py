import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import hot_keys

class HotKeysTests(unittest.TestCase):
    def test_api_offers_and_cooldown_persist(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            file=directory/"hot_low.json"
            db=directory/"data.db"
            file.write_text(json.dumps({"meta":{},"games":[{
                "appid":300,"steam_subids":[456],"price":50,"key_offers":[]
            }]}),encoding="utf-8")
            with patch.object(hot_keys,"steampy",return_value={
                     "platform":"SteamPY","price":24.0,"kind":"reference","subid":456}), \
                 patch.object(hot_keys,"steamcici",return_value=None):
                first=hot_keys.run(5,file,db)
                second=hot_keys.run(5,file,db)
            self.assertEqual(first["checked"],1)
            self.assertEqual(second["checked"],0)
            result=json.loads(file.read_text("utf-8"))["games"][0]
            self.assertEqual(result["key_offers"][0]["price"],24)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM hot_key_checks").fetchone()[0],1)

    def test_placeholder_is_rejected_but_old_offer_is_kept(self):
        game={"appid":300,"steam_subids":[456],"price":30.4,
              "key_offers":[{"platform":"SteamCiCi","price":20,"kind":"historical_listing"}]}
        with patch.object(hot_keys,"steampy",return_value={
                     "platform":"SteamPY","price":0.10,"kind":"reference"}), \
             patch.object(hot_keys,"steamcici",return_value=None):
            status,_=hot_keys.enrich_one(game)
        self.assertEqual(status,"no_quote")
        self.assertEqual(len(game["key_offers"]),1)
        self.assertEqual(game["key_offers"][0]["platform"],"SteamCiCi")

if __name__=="__main__":
    unittest.main()
