import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from backlog import save_pending,load_pending,drop_processed

class BacklogTests(unittest.TestCase):
    def test_unique_resume_and_drop(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"pending.json"
            save_pending(path,[{"id":1,"_flag":"explore"},{"id":2,"_flag":"deal"}])
            save_pending(path,[{"id":1,"_flag":"explore","_watchlisted":True},
                               {"id":1,"_flag":"new"}])
            self.assertEqual(len(load_pending(path)),3)
            self.assertTrue(next(g for g in load_pending(path) if
                         g["_flag"]=="explore")["_watchlisted"])
            self.assertEqual(drop_processed(path,{("explore",1)}),2)
            self.assertEqual({(g["_flag"],g["id"]) for g in load_pending(path)},
                             {("new",1),("deal",2)})
    def test_empty_queue_is_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"pending.json"
            self.assertEqual(load_pending(path),[])
            self.assertEqual(drop_processed(path,set()),0)

if __name__=="__main__":unittest.main()
