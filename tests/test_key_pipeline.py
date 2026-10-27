import datetime as dt
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import key_pipeline
import monitor_actions

class SharedKeyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.a=self.root/"games.json"
        self.b=self.root/"hot_low.json"
        self.db=self.root/"radar.db"
        self.now=dt.datetime(2026,10,27,12,tzinfo=dt.timezone.utc)
        self.a.write_text(json.dumps({"games":[{"appid":101,"price":40,
            "steam_subids":[200],"key_offers":[]}]}))
        self.b.write_text(json.dumps({"games":[{"appid":101,"price":40,
            "steam_subids":[200],"key_offers":[]}]}))

    def tearDown(self):
        self.temp.cleanup()

    def test_deduplication_and_cooldown(self):
        seen=[]
        def source(aid,packages):
            seen.append((aid,packages))
            return {"platform":"SteamPY","price":25.5,"checked_at":self.now.isoformat(),
                    "kind":"reference","subid":200}
        def no_quote(aid,packages):
            seen.append((aid,packages))
            return None
        r=key_pipeline.run([self.a,self.b],self.db,limit=5,now=self.now,
            lookups=(source,no_quote))
        self.assertEqual(r["checked"],1)
        self.assertEqual(len(seen),2)
        for p in (self.a,self.b):
            game=json.loads(p.read_text())["games"][0]
            self.assertEqual(game["key_offers"][0]["price"],25.5)
        again=key_pipeline.run([self.a,self.b],self.db,limit=5,
            now=self.now+dt.timedelta(hours=1),lookups=(source,no_quote))
        self.assertEqual(again["checked"],0)
        self.assertEqual(len(seen),2)

    def test_expired_and_missing_dates_hidden(self):
        def offer(time):
            return {"platform":"SteamPY","price":12,"checked_at":time}
        current=self.now.isoformat()
        expired=(self.now-dt.timedelta(hours=73)).isoformat()
        self.assertEqual(len(key_pipeline.valid_display_offers([offer(current)],40,self.now)),1)
        self.assertFalse(key_pipeline.valid_display_offers([offer(expired)],40,self.now))
        self.assertFalse(key_pipeline.valid_display_offers([{"platform":"SteamPY","price":12}],40,self.now))

    def test_migrates_hot_retry_without_new_duplicate(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE hot_key_checks (appid INTEGER PRIMARY KEY,status TEXT,checked_at TEXT,retry_after TEXT)")
            db.execute("INSERT INTO hot_key_checks VALUES (101,'no_quote',?,?)",
                (self.now.isoformat(),(self.now+dt.timedelta(hours=24)).isoformat()))
        with sqlite3.connect(self.db) as db:
            key_pipeline.setup(db)
            self.assertFalse(key_pipeline.due(db,101,self.now))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM enrichment_state WHERE appid=101 AND task='keys'").fetchone()[0],1)

class MonitorTests(unittest.TestCase):
    def test_latest_failure_reported(self):
        now=dt.datetime(2026,10,27,12,tzinfo=dt.timezone.utc)
        runs=[{"name":name,"created_at":"2026-10-27T11:00:00Z",
               "status":"completed","conclusion":"success"} for name in monitor_actions.REQUIRED]
        self.assertEqual(monitor_actions.analyze(runs,now),[])
        runs[0]["conclusion"]="failure"
        issues=monitor_actions.analyze(runs,now)
        self.assertEqual(len(issues),1)
        self.assertIn("失败",issues[0])

if __name__=="__main__":
    unittest.main()
