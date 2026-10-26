import sys
import unittest
import tempfile
import sqlite3
import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from storage import save,statistics

class StorageTests(unittest.TestCase):
    def test_repeated_daily_update_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"radar.db"
            now=datetime.datetime(2026,10,26,14,0,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
            games=[{"appid":123,"name":"测试游戏","genres":["策略"],"review_pct":95,
                    "review_count":1000,"recommend_score":9,
                    "mobile":{"android":"已上线","ios":"已上线","source":"https://example.org"},
                    "key_offers":[{"platform":"SteamPY","subid":456,"price":8.5,"kind":"reference",
                                   "status":"待核实","url":"https://example.org"}]}]
            raw=[{"id":123,"name":"测试游戏","final_price":1200,"original_price":5000,"discount_percent":76}]
            cfg={"owned":["Game Already Owned"]}
            epic={"example":{"title":"Free Example","date":"2026-10-01","source":"https://example.org"}}
            save(path,games,raw,cfg,{},epic,now)
            save(path,games,raw,cfg,{},epic,now)
            stats=statistics(path)
            self.assertEqual(stats["game_info"],1)
            self.assertEqual(stats["steam_price_history"],1)
            self.assertEqual(stats["key_price_history"],1)
            self.assertEqual(stats["epic_free_history"],1)
            self.assertEqual(stats["mobile_platform"],1)
            self.assertEqual(stats["user_owned_games"],1)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT price FROM steam_price_history").fetchone()[0],12.0)
                self.assertEqual(db.execute("SELECT price FROM key_price_history").fetchone()[0],8.5)

    def test_release_date_and_schema_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"radar.db"
            with sqlite3.connect(path) as db:
                db.execute("""CREATE TABLE game_info (
                    appid INTEGER PRIMARY KEY, name TEXT NOT NULL, name_en TEXT,
                    genres_json TEXT NOT NULL DEFAULT '[]', review_pct REAL,
                    review_count INTEGER, recommend_score REAL, updated_at TEXT NOT NULL)""")
            game={"appid":123,"name":"Example","release_date":"2026年10月26日","coming_soon":False}
            save(path,[game],[],{"owned":[]},{},{})
            with sqlite3.connect(path) as db:
                row=db.execute("SELECT release_date,coming_soon FROM game_info WHERE appid=123").fetchone()
                self.assertEqual(row,("2026年10月26日",0))

    def test_daily_rows_accumulate(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"radar.db"
            for day in (26,27):
                save(path,[],[{"id":456,"final_price":1099,"original_price":2000}],
                    {"owned":[]},{},{},datetime.datetime(2026,10,day,14,0,tzinfo=datetime.timezone.utc))
            self.assertEqual(statistics(path)["steam_price_history"],2)

if __name__=="__main__":
    unittest.main()
