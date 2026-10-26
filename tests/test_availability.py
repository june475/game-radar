import sys, unittest, datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from availability import metadata, normalized, MOBILE
class AvailabilityTests(unittest.TestCase):
    def test_epic_confirmed_exclusion(self):
        epic={normalized("Known Game"):{"title":"Known Game","date":"2026-01-01"}}
        result=metadata(123,["Known Game"],epic)
        self.assertTrue(result["epic_exclude"])
        self.assertEqual(result["epic_status"],"曾免费赠送")
    def test_missing_is_not_never_free(self):
        result=metadata(123,["Unknown Game"],{})
        self.assertFalse(result["epic_exclude"])
        self.assertIn("未核实",result["epic_status"])
    def test_mobile_verified_port(self):
        result=metadata(1282730,["Loop Hero"],{})
        self.assertEqual(result["mobile"]["android"],"已上线")
if __name__=="__main__":unittest.main()
