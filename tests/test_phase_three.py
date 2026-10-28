import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import export_price_history as history
from recommend_quality import review_confidence,rank_recommendation
from review_analysis import classify_texts

class PhaseThreeTests(unittest.TestCase):
    def test_low_review_count_does_not_overpower_mature_rating(self):
        self.assertLess(review_confidence(10),review_confidence(10000))
        newer={"recommend_score":8,"review_pct":98,"review_count":10}
        mature={"recommend_score":8,"review_pct":98,"review_count":10000}
        self.assertLess(rank_recommendation(newer),rank_recommendation(mature))
        self.assertEqual(rank_recommendation({"recommend_score":5,"review_pct":None}),5)

    def test_review_negation_and_topic_ratios(self):
        data=classify_texts(["没有卡顿","经常卡顿","翻译很差"])
        topics={item["name"]:item["mentions"] for item in data["categories"]}
        self.assertEqual(topics.get("性能/技术问题"),1)
        self.assertEqual(data["sample_size"],3)
        self.assertIn("topic_share",data)

    def test_real_price_history_from_sqlite(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"game.db"
            out=Path(temp)/"prices.json"
            with sqlite3.connect(db) as c:
                c.execute("""CREATE TABLE steam_price_history(
                     appid INTEGER,observed_date TEXT,price REAL,currency TEXT)""")
                c.execute("""CREATE TABLE key_price_history(
                     appid INTEGER,observed_date TEXT,price REAL,platform TEXT,kind TEXT)""")
                c.execute("INSERT INTO steam_price_history VALUES(5,date('now'),20,'CNY')")
                c.execute("INSERT INTO key_price_history VALUES(5,date('now'),13,'SteamPY','reference')")
            result=history.generate(db,out)
            items=result["games"]["5"]
            self.assertEqual({x["source"] for x in items},{"Steam","SteamPY"})
            self.assertTrue(out.exists())

if __name__=="__main__":
    unittest.main()
