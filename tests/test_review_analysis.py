import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from review_analysis import classify_texts,reason_adjustment

class ReviewAnalysisTests(unittest.TestCase):
    def test_operational_only_does_not_mean_high_quality(self):
        r=classify_texts(["官方运营声明很差","开发商涨价失信","运营和公关不负责"]*4)
        self.assertEqual(r["main_issue"],"运营/商业争议")
        self.assertLessEqual(reason_adjustment(r),0.2)
    def test_gameplay_technical_complaints_lower_rank(self):
        r=classify_texts(["卡顿掉帧频繁","闪退导致存档丢失","优化很差"]*5)
        self.assertEqual(r["main_issue"],"性能/技术问题")
        self.assertLess(reason_adjustment(r),0)
    def test_insufficient_samples_not_over_interpreted(self):
        r=classify_texts(["游戏卡顿"])
        self.assertIsNone(r["main_issue"])
        self.assertEqual(reason_adjustment(r),0)

if __name__=="__main__":unittest.main()
