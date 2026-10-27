"""Shared key-reference collector for every Game Radar tab.

Deduplicates by Steam AppID across recommendation and hot lists.
Persists one SQLite retry state and propagates valid observations to both files.
A reference quote expires after 72 hours; historical listing data is never
represented as current stock.
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path
from market import steampy, steamcici, clean_offers

MAX_REFERENCE_AGE_HOURS=72
SOURCES=("SteamPY","SteamCiCi")

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def parse_date(value):
    if not value:return None
    try:
        date=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return date if date.tzinfo else date.replace(tzinfo=dt.timezone.utc)
    except (ValueError,TypeError):return None

def valid_display_offers(offers,steam_price=None,now=None):
    now=now or now_utc()
    result=[]
    for item in clean_offers(offers,steam_price):
        date=parse_date(item.get("checked_at"))
        if date and dt.timedelta(0)<=now-date<=dt.timedelta(hours=MAX_REFERENCE_AGE_HOURS):
            result.append(item)
    return result

def setup(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS enrichment_state(
        appid INTEGER NOT NULL, task TEXT NOT NULL, status TEXT NOT NULL,
        last_attempt TEXT NOT NULL, next_attempt TEXT NOT NULL, details TEXT,
        PRIMARY KEY(appid,task))""")
    # Legacy hot-key cooldowns are preserved where no unified entry exists.
    tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "hot_key_checks" in tables:
        conn.execute("""INSERT OR IGNORE INTO enrichment_state
            (appid,task,status,last_attempt,next_attempt,details)
            SELECT appid,'keys',status,checked_at,retry_after,'migrated from hot_key_checks'
            FROM hot_key_checks""")
    conn.commit()

def due(conn,appid,now):
    row=conn.execute("SELECT next_attempt FROM enrichment_state WHERE appid=? AND task='keys'",(appid,)).fetchone()
    end=parse_date(row[0]) if row else None
    return not end or end<=now

def result_state(conn,appid,status,now,details):
    hours={"success":72,"no_quote":24,"unverified":24,"failed":6}.get(status,12)
    future=now+dt.timedelta(hours=hours)
    conn.execute("""INSERT INTO enrichment_state(appid,task,status,last_attempt,next_attempt,details)
        VALUES(?,'keys',?,?,?,?) ON CONFLICT(appid,task) DO UPDATE SET
        status=excluded.status,last_attempt=excluded.last_attempt,
        next_attempt=excluded.next_attempt,details=excluded.details""",
        (appid,status,now.isoformat(),future.isoformat(),str(details)[:250]))
    return {"status":status,"checked_at":now.isoformat(),
            "next_retry_at":future.isoformat()}

def get_packages(game,details_lookup=None):
    ids=[int(i) for i in (game.get("steam_subids") or []) if str(i).isdigit()][:8]
    if not ids and details_lookup:
        info=details_lookup(game["appid"]) or {}
        ids=[int(i) for i in (info.get("packages") or []) if str(i).isdigit()][:8]
    return ids

def query(appid,subids,price,old,now,lookups=(steampy,steamcici)):
    previous=valid_display_offers(old,price,now)
    if not subids:return previous,"unverified","missing Steam package IDs"
    fresh=[]
    for lookup in lookups:
        candidate=lookup(appid,subids)
        if candidate:
            candidate=dict(candidate)
            candidate["checked_at"]=now.isoformat()
            fresh.extend(clean_offers([candidate],price))
    merged={x["platform"]:x for x in previous}
    merged.update({x["platform"]:x for x in fresh})
    result=list(merged.values())
    return result,("success" if fresh else "no_quote"),f"{len(fresh)} validated reference sources"

def load_doc(path):
    try:
        obj=json.loads(Path(path).read_text("utf-8"))
        return obj if isinstance(obj.get("games"),list) else {"games":[]}
    except (OSError,ValueError,AttributeError):return {"games":[]}

def run(paths,db_path,limit=5,now=None,lookups=(steampy,steamcici),details_lookup=None):
    now=now or now_utc()
    paths=[Path(p) for p in paths]
    documents={p:load_doc(p) for p in paths}
    mapping={}
    for path,doc in documents.items():
        for game in doc["games"]:
            if not isinstance(game,dict) or not isinstance(game.get("appid"),int):continue
            mapping.setdefault(game["appid"],[]).append((path,game))
    db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    report={"checked":0,"changed_files":0,"candidates":len(mapping),"statuses":{}}
    changed=set()
    with sqlite3.connect(db_path) as db:
        setup(db)
        # Prefer entries with no previous attempt, then oldest due timestamp.
        order=list(mapping)
        order.sort(key=lambda aid:(db.execute(
            "SELECT last_attempt FROM enrichment_state WHERE appid=? AND task='keys'",(aid,)).fetchone() or ("",))[0])
        for appid in order:
            if report["checked"]>=limit:break
            if not due(db,appid,now):continue
            games=[g for _,g in mapping[appid]]
            game=max(games,key=lambda g:len(g.get("steam_subids") or []))
            packages=get_packages(game,details_lookup)
            prior=[]
            for g in games:prior.extend(g.get("key_offers") or [])
            try:
                offers,status,reason=query(appid,packages,game.get("price"),prior,now,lookups)
            except Exception as exc:
                offers=valid_display_offers(prior,game.get("price"),now)
                status,reason="failed",str(exc)[:180]
            state=result_state(db,appid,status,now,reason)
            for path,g in mapping[appid]:
                # Keep only price-valid offers on each card.
                valid=valid_display_offers(offers,g.get("price"),now)
                updates={"steam_subids":packages or (g.get("steam_subids") or []),
                         "key_offers":valid,
                         "key_reference_min":min((x["price"] for x in valid),default=None),
                         "key_status":"参考报价，不代表实时库存" if valid else "暂无有效散 Key 参考价",
                         "enrichment_status":{**(g.get("enrichment_status") or {}),"keys":state}}
                if any(g.get(k)!=v for k,v in updates.items()):
                    g.update(updates);changed.add(path)
            report["checked"]+=1
            report["statuses"][status]=report["statuses"].get(status,0)+1
        db.commit()
    for path in changed:
        documents[path].setdefault("meta",{})["last_key_enrichment_utc"]=now.isoformat()
        path.write_text(json.dumps(documents[path],ensure_ascii=False,indent=2)+"\n","utf-8")
    report["changed_files"]=len(changed)
    print("Unified key enrichment",report)
    return report

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--limit",type=int,default=5)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    run([root/"data/games.json",root/"data/hot_low.json"],
        root/"data/game_radar.db",limit=max(1,min(args.limit,20)))
