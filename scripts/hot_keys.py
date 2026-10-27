"""Gradually complete marketplace key references for the popular discounts tab.

Independent of recommendation discovery and personal taste. Each run checks
only a small number of games and persists retry windows in SQLite.
"""
import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from market import steampy,steamcici,clean_offers
from hot_low import details

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
HOT_FILE=DATA/"hot_low.json"
DB_FILE=DATA/"game_radar.db"

def load(path):
    try:return json.loads(Path(path).read_text("utf-8"))
    except (OSError,ValueError):return {"games":[]}

def enrich_one(game):
    appid=game["appid"]
    subids=[int(i) for i in game.get("steam_subids",[]) if str(i).isdigit()][:8]
    if not subids:
        d=details(appid)
        subids=[int(i) for i in (d or {}).get("packages",[]) if str(i).isdigit()][:8]
        game["steam_subids"]=subids
    if not subids:
        return "unverified","Steam package IDs unavailable"
    old=clean_offers(game.get("key_offers"),game.get("price"))
    offers=[]
    for lookup in (steampy,steamcici):
        result=lookup(appid,subids)
        if result:offers.append(result)
    offers=clean_offers(offers,game.get("price"))
    merged={x["platform"]:x for x in old}
    merged.update({x["platform"]:x for x in offers})
    game["key_offers"]=list(merged.values())
    game["key_reference_min"]=min((x["price"] for x in merged.values()),default=None)
    game["key_status"]="接口参考价，需核实库存、版本和地区" if merged else "暂未获得可靠报价"
    return ("success" if offers else "no_quote"),f"{len(offers)} new source quotes"

def run(limit=5,hot_path=HOT_FILE,db_path=DB_FILE):
    hot_path,db_path=Path(hot_path),Path(db_path)
    obj=load(hot_path)
    games=[g for g in obj.get("games",[]) if isinstance(g,dict) and isinstance(g.get("appid"),int)]
    if not games:return {"checked":0,"updated":0}
    db_path.parent.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    processed=0
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS hot_key_checks(
            appid INTEGER PRIMARY KEY, status TEXT NOT NULL,
            checked_at TEXT NOT NULL, retry_after TEXT NOT NULL)""")
        due=[]
        for g in games:
            record=db.execute("SELECT retry_after FROM hot_key_checks WHERE appid=?",(g["appid"],)).fetchone()
            try:ready=(not record or dt.datetime.fromisoformat(record[0])<=now)
            except (ValueError,TypeError):ready=True
            if ready:due.append(g)
        for g in due[:limit]:
            appid=g["appid"]
            try:
                status,description=enrich_one(g)
            except Exception as exc:
                status,description="failed",str(exc)[:150]
                print("Hot key enrichment failed",appid,description)
            delay={"success":72,"no_quote":24,"unverified":24,"failed":6}.get(status,24)
            retry_after=now+dt.timedelta(hours=delay)
            db.execute("""INSERT INTO hot_key_checks(appid,status,checked_at,retry_after)
              VALUES(?,?,?,?) ON CONFLICT(appid) DO UPDATE SET
              status=excluded.status,checked_at=excluded.checked_at,retry_after=excluded.retry_after""",
              (appid,status,now.isoformat(),retry_after.isoformat()))
            g.setdefault("enrichment_status",{})["keys"]={
                "status":status,"checked_at":now.isoformat(),
                "next_retry_at":retry_after.isoformat()}
            print("Hot keys",appid,status,description)
            processed+=1
        db.commit()
    if processed:
        obj["games"]=games
        obj.setdefault("meta",{})["last_hot_keys_utc"]=now.isoformat()
        hot_path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("Hot key summary",{"checked":processed,"total":len(games),"eligible":len(due)})
    return {"checked":processed,"updated":processed}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--limit",type=int,default=5)
    args=ap.parse_args()
    run(max(1,min(args.limit,10)))
