import datetime as dt
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import enrich_missing as worker

class FieldEnrichmentTests(unittest.TestCase):
    def test_existing_enrichment_respects_retry_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn=worker.connect(Path(tmp)/"radar.db")
            game={"appid":101,"key_offers":[],"steam_subids":[800]}
            now=dt.datetime(2026,10,27,tzinfo=dt.timezone.utc)
            self.assertTrue(worker.eligible(conn,game,"keys",now))
            worker.record(conn,101,"keys","no_quote",now=now)
            self.assertFalse(worker.eligible(conn,game,"keys",now+dt.timedelta(hours=1)))
            self.assertTrue(worker.eligible(conn,game,"keys",now+dt.timedelta(hours=25)))
            conn.close()

    def test_keys_preserve_known_quotes_when_api_empty(self):
        game={"appid":101,"price":30.0,"steam_subids":[800],
              "key_offers":[{"platform":"SteamPY","price":8.5}]}
        with patch.object(worker,"steampy",return_value=None),\
             patch.object(worker,"steamcici",return_value=None):
            status,_=worker.update_one(game,"keys")
        self.assertEqual(status,"no_quote")
        self.assertEqual(game["key_offers"][0]["price"],8.5)

    def test_missing_price_is_not_invented(self):
        game={"appid":101,"price":30.4,"steam_subids":[800],
              "key_offers":[]}
        with patch.object(worker,"steampy",return_value={"platform":"SteamPY","price":0.1}),\
             patch.object(worker,"steamcici",return_value=None):
            status,_=worker.update_one(game,"keys")
        self.assertEqual(status,"no_quote")
        self.assertEqual(game["key_offers"],[])

    def test_staggered_worker_only_enriches_selected_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            games=folder/"games.json"
            database=folder/"radar.db"
            game={"appid":101,"name":"Test","category":"deal","price":15.0,
                  "steam_deck":None,"key_offers":[]}
            games.write_text(json.dumps({"meta":{},"games":[game]}),"utf-8")
            with patch.object(worker,"deck_lookup",return_value={
                      "compatibility":"可玩","source_url":"https://example.org"}):
                result=worker.run("deck",limit=1,db_path=database,games_path=games)
            self.assertEqual(result["checked"],1)
            obj=json.loads(games.read_text("utf-8"))["games"][0]
            self.assertEqual(obj["steam_deck"],"可玩")
            self.assertEqual(obj["key_offers"],[])

if __name__=="__main__":
    unittest.main()
