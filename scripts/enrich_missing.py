"""Small, independently scheduled field-level enrichment jobs.

Only existing recommendations are enriched; these jobs do not discover games,
re-score recommendations, or overwrite other categories. All results are
source-labeled, with cooldowns persisted in SQLite.
"""
import argparse
import datetime as dt
import json
import logging
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
DB=DATA/"game_radar.db"
GAMES=DATA/"games.json"
sys.path.insert(0,str(Path(__file__).resolve().parent))
from market import clean_offers,steampy,steamcici,steamraw
from review_analysis import fetch_negative_reviews
from availability import MOBILE,epic_history,metadata
from storage import setup as setup_storage

# Retry intervals (hours): failures have shorter retries than unavailable data.
SUCCESS_HOURS={"keys":72,"reviews":24*7,"deck":24*14,
               "history":24*7,"epic":24*3,"mobile":24*30,"dlc":24*14}
RETRY_HOURS={"no_quote":24,"unverified":24,"failed":6,"no_data":48}
DECK_CATEGORIES={1:"未知",2:"不支持",3:"可玩",4:"已验证"}

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def load():
    try:
        obj=json.loads(GAMES.read_text("utf-8"))
        if isinstance(obj.get("games"),list):return obj
    except (OSError,ValueError,AttributeError):pass
    return {"meta":{},"games":[]}

def connect(path=DB):
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path)
    setup_storage(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS enrichment_state(
        appid INTEGER NOT NULL,task TEXT NOT NULL,status TEXT NOT NULL,
        last_attempt TEXT NOT NULL,next_attempt TEXT NOT NULL,
        details TEXT,PRIMARY KEY(appid,task))""")
    conn.commit()
    return conn

def record(conn,appid,task,status,details="",now=None):
    now=now or utcnow()
    hours=SUCCESS_HOURS[task] if status=="success" else RETRY_HOURS.get(status,12)
    due=now+dt.timedelta(hours=hours)
    conn.execute("""INSERT INTO enrichment_state
        (appid,task,status,last_attempt,next_attempt,details) VALUES(?,?,?,?,?,?)
        ON CONFLICT(appid,task) DO UPDATE SET
        status=excluded.status,last_attempt=excluded.last_attempt,
        next_attempt=excluded.next_attempt,details=excluded.details
    """,(appid,task,status,now.isoformat(),due.isoformat(),str(details)[:250]))
    return {"status":status,"checked_at":now.isoformat(),
            "next_retry_at":due.isoformat(),"details":str(details)[:250]}

def eligible(conn,game,task,now,force=False):
    aid=game.get("appid")
    if not isinstance(aid,int):return False
    if not force:
        old=conn.execute("SELECT next_attempt FROM enrichment_state WHERE appid=? AND task=?",
                         (aid,task)).fetchone()
        if old:
            try:
                if dt.datetime.fromisoformat(old[0])>now:return False
            except (ValueError,TypeError):pass
    if task=="keys":
        # Revisit existing reference quotes after their own interval, not hourly.
        return True
    if task=="reviews":
        return not (game.get("negative_review_analysis") or {}).get("sample_size")
    if task=="deck":
        return not game.get("steam_deck") or game.get("steam_deck")=="待核实"
    if task=="history":
        return not game.get("region_history_low")
    if task=="epic":
        # A missing historical match is not a verified negative.
        return not game.get("epic_giveaway")
    if task=="mobile":
        return not game.get("mobile")
    if task=="dlc":
        return game.get("dlc_count") is None
    return False

def request_json(url,timeout=9):
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0 (GameRadar scheduled metadata enrichment)",
        "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        return json.load(response)

def deck_lookup(appid):
    # Unofficial public Steam Store endpoint. Only explicitly mapped numeric
    # Valve compatibility grades qualify; other shapes remain unverified.
    url=("https://store.steampowered.com/saleaction/ajaxgetdeckappcompatibilityreport?"
         + urllib.parse.urlencode({"appid":appid}))
    raw=request_json(url)
    report=raw.get("results") if isinstance(raw,dict) else None
    if not isinstance(report,dict):return None
    value=report.get("resolved_category")
    if value in DECK_CATEGORIES:
        return {"compatibility":DECK_CATEGORIES[value],
                "source":"Steam","source_url":url}
    return None

def app_details(appid):
    url="https://store.steampowered.com/api/appdetails?"+urllib.parse.urlencode(
        {"appids":appid,"cc":"cn","l":"schinese"})
    obj=request_json(url)
    entry=obj.get(str(appid),{}) if isinstance(obj,dict) else {}
    return entry.get("data") if entry.get("success") else None

def update_one(game,task,epic=None):
    """Return (status, explanation); changes are applied to game in-place."""
    appid=game["appid"]
    if task=="keys":
        subids=[int(x) for x in game.get("steam_subids",[]) if str(x).isdigit()]
        if not subids:return "unverified","missing Steam package IDs"
        old=clean_offers(game.get("key_offers"),game.get("price"))
        candidates=[]
        # These endpoints contain references and historical listings, not verified stock.
        for source in (steampy,steamcici):
            item=source(appid,subids)
            if item:candidates.append(item)
        new=clean_offers(candidates,game.get("price"))
        if new:
            # Preserve old platform quote only if current lookup did not provide
            # a replacement; it must be clearly marked as a previous observation.
            by_platform={x["platform"]:x for x in old}
            by_platform.update({x["platform"]:x for x in new})
            game["key_offers"]=list(by_platform.values())
            game["key_reference_min"]=min(x["price"] for x in game["key_offers"])
            game["key_status"]="接口参考报价（非已验证现货）"
            return "success",",".join(x["platform"] for x in new)
        game["key_offers"]=old
        game["key_reference_min"]=min((x["price"] for x in old),default=None)
        game["key_status"]="已有参考价（本次未获得新报价）" if old else "未获得可靠报价（非确认无货）"
        return "no_quote","no reliable public offer"
    if task=="reviews":
        result=fetch_negative_reviews(appid,limit=20)
        if result.get("sample_size",0):
            game["negative_review_analysis"]=result
            return "success",f'{result["sample_size"]} recent Chinese negative reviews'
        return "no_data","negative reviews unavailable"
    if task=="deck":
        info=deck_lookup(appid)
        if info:
            game["steam_deck"]=info["compatibility"]
            game["steam_deck_source"]=info["source_url"]
            return "success",info["compatibility"]
        return "unverified","official grade unavailable"
    if task=="history":
        info=steamraw(appid)
        if info:
            game["region_history_low"]=info
            return "success","regional coverage low (not lifetime low)"
        return "unverified","no verified CNY historical record"
    if task=="epic":
        info=metadata(appid,[game.get("name"),game.get("name_en")],
                      epic or {},None)
        if info.get("epic_giveaway"):
            game["epic_status"]="曾免费赠送"
            game["epic_giveaway"]=info["epic_giveaway"]
            return "success","confirmed giveaway record"
        game["epic_status"]="历史库未匹配（未核实）"
        return "unverified","incomplete third-party archive"
    if task=="mobile":
        info=MOBILE.get(str(appid))
        if info:
            game["mobile"]=info
            flags=set(game.get("flags") or [])
            game["flags"]=sorted(flags|{"mobile"})
            return "success","verified mobile port catalog"
        return "unverified","no verified official port record"
    if task=="dlc":
        d=app_details(appid)
        if not d:return "failed","appdetails unavailable"
        ids=[i for i in (d.get("dlc") or []) if isinstance(i,int)]
        game["dlc_count"]=len(ids)
        game["dlc_appids"]=ids[:30]
        game["dlc_status"]="Steam 商店关联 DLC 数量；不代表值得购买"
        return "success",f"{len(ids)} DLC IDs"
    return "failed","unsupported task"

def persist_enrichment(conn,game,task,observed):
    """Keep the existing SQLite reporting tables in sync with JSON metadata."""
    aid=game["appid"]
    stamp=observed.isoformat()
    if task=="reviews" and game.get("negative_review_analysis"):
        conn.execute("UPDATE game_info SET review_analysis_json=? WHERE appid=?",
                     (json.dumps(game["negative_review_analysis"],ensure_ascii=False),aid))
    elif task=="deck" and game.get("steam_deck"):
        conn.execute("""INSERT INTO steam_deck_info(appid,compatibility,source_url,checked_at)
                        VALUES(?,?,?,?)
                        ON CONFLICT(appid) DO UPDATE SET
                        compatibility=excluded.compatibility,
                        source_url=excluded.source_url,checked_at=excluded.checked_at""",
                     (aid,game["steam_deck"],game.get("steam_deck_source"),stamp))
    elif task=="mobile" and isinstance(game.get("mobile"),dict):
        m=game["mobile"]
        conn.execute("""INSERT INTO mobile_platform
                     (appid,android,ios,status,source_url,verified_at) VALUES(?,?,?,?,?,?)
                     ON CONFLICT(appid) DO UPDATE SET
                     android=excluded.android,ios=excluded.ios,status=excluded.status,
                     source_url=excluded.source_url,verified_at=excluded.verified_at""",
                     (aid,m.get("android"),m.get("ios"),m.get("status"),m.get("source"),stamp))
    elif task=="dlc":
        for dlc in game.get("dlc_appids") or []:
            conn.execute("""INSERT OR IGNORE INTO game_dlc
                     (appid,dlc_appid,checked_at) VALUES(?,?,?)""",(aid,dlc,stamp))
    elif task=="keys":
        for item in game.get("key_offers") or []:
            p=item.get("price")
            if p is None:continue
            cn_date=observed.astimezone(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
            conn.execute("""INSERT INTO key_price_history
                (appid,observed_date,platform,package_id,price,kind,status,source_url,checked_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(appid,observed_date,platform,package_id,kind)
                DO UPDATE SET price=excluded.price,status=excluded.status,
                source_url=excluded.source_url,checked_at=excluded.checked_at""",
                (aid,cn_date,item.get("platform",""),
                 str(item.get("subid") or ""),p,item.get("kind") or "reference",
                 item.get("status") or "",item.get("url"),item.get("checked_at") or stamp))

def run(task,limit=5,force=False,db_path=DB,games_path=GAMES):
    global GAMES
    GAMES=Path(games_path)
    doc=load()
    all_games=doc.get("games",[])
    now=utcnow()
    results={"task":task,"checked":0,"updated":0,"status":{}}
    with connect(Path(db_path)) as db:
        due=[g for g in all_games if eligible(db,g,task,now,force)]
        # Rotate through the set across runs by earliest next retry; first runs
        # prioritize games with no previous attempt.
        due.sort(key=lambda g:(0 if not db.execute(
            "SELECT 1 FROM enrichment_state WHERE appid=? AND task=?",
            (g["appid"],task)).fetchone() else 1,
            not g.get("watchlisted"),g.get("appid")))
        epic=epic_history() if task=="epic" and due else {}
        for game in due[:limit]:
            aid=game["appid"]
            before=json.dumps(game,ensure_ascii=False,sort_keys=True)
            try:
                status,reason=update_one(game,task,epic)
            except (Exception,) as exc:
                status,reason="failed",str(exc)[:150]
                print("Enrichment failed",task,aid,reason)
            result=record(db,aid,task,status,reason,now)
            if status=="success":persist_enrichment(db,game,task,now)
            game.setdefault("enrichment_status",{})[task]=result
            results["checked"]+=1
            results["status"][status]=results["status"].get(status,0)+1
            if json.dumps(game,ensure_ascii=False,sort_keys=True)!=before:
                results["updated"]+=1
            # Avoid bursts across separate domains / runs.
            time.sleep(0.25)
        db.commit()
    if results["updated"]:
        doc.setdefault("meta",{})["last_enrichment_utc"]=now.isoformat()
        GAMES.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("Enrichment summary",json.dumps(results,ensure_ascii=False))
    return results

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--task",required=True,choices=tuple(SUCCESS_HOURS))
    parser.add_argument("--limit",type=int,default=5)
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    run(args.task,max(1,min(args.limit,12)),args.force)

if __name__=="__main__":
    main()
