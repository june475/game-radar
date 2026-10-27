import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from check_recommendations import decision,counts,missing_categories

class RecommendationCheckTests(unittest.TestCase):
    def file(self, directory, games):
        path=Path(directory)/"games.json"
        path.write_text(json.dumps({"games":games}),"utf-8")
        return path

    def test_skip_when_all_categories_exist(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.file(d,[{"appid":1,"category":"deal"},
                            {"appid":2,"category":"new"},
                            {"appid":3,"category":"explore"}])
            self.assertFalse(decision(p,"compensate")["run"])
            self.assertTrue(decision(p,"daily")["run"])

    def test_compensate_only_empty_categories(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.file(d,[{"appid":1,"category":"deal"},
                            {"appid":2,"category":"new"}])
            self.assertEqual(missing_categories(p),["explore"])
            self.assertTrue(decision(p,"compensate")["run"])

    def test_empty_or_missing_file_runs_compensation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"not-found.json"
            self.assertEqual(set(missing_categories(p)),{"deal","new","explore"})
            self.assertTrue(decision(p,"compensate")["run"])

if __name__=="__main__":
    unittest.main()
