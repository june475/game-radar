import datetime as dt
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import import_steamdb
import export_price_history

class SteamDBIntegrationTests(unittest.TestCase):
    def test_valid_manual_observation_is_importable(self):
        today=dt.datetime.now(dt.timezone.utc).date().isoformat()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);source=folder/"records.csv";target=folder/"steamdb.json"
            source.write_text("appid,date,price_cny,source_url\n101,"+today+",29.9,https://steamdb.info/app/101/\n",encoding="utf-8")
            result=import_steamdb.convert(source,target)
            self.assertEqual(result["games"]["101"][0]["price"],29.9)
            self.assertEqual(result["games"]["101"][0]["source"],"SteamDB")

    def test_bad_domain_or_appid_is_rejected(self):
        today=dt.datetime.now(dt.timezone.utc).date().isoformat()
        for link in ("https://fake-steamdb.info/app/101/","https://steamdb.info/app/999/"):
            with self.assertRaises(ValueError):
                import_steamdb.parse_row({"appid":"101","date":today,
                    "price_cny":"29.9","source_url":link})

    def test_export_merges_only_real_imports(self):
        today=dt.datetime.now(dt.timezone.utc).date().isoformat()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); db=folder/"prices.db"
            imported=folder/"steamdb_history.json";output=folder/"history.json"
            imported.write_text(json.dumps({"games":{"101":[{
                "date":today,"price":29.9,"source":"SteamDB","currency":"CNY",
                "source_url":"https://steamdb.info/app/101/"}]}}),encoding="utf-8")
            with patch.object(export_price_history,"STEAMDB",imported):
                result=export_price_history.generate(db,output)
            self.assertEqual(result["games"]["101"][0]["source"],"SteamDB")
            self.assertEqual(len(result["games"]["101"]),1)

    def test_export_has_no_invented_steamdb_line(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            with patch.object(export_price_history,"STEAMDB",folder/"missing.json"):
                result=export_price_history.generate(folder/"missing.db",folder/"output.json")
            self.assertEqual(result["games"],{})

if __name__=="__main__":
    unittest.main()
