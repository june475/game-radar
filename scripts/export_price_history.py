"""Export actual observed Steam and marketplace price records for static charts."""
import datetime as dt
import json
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data/game_radar.db"
OUT=ROOT/"data/price_history.json"
STEAMDB=ROOT/"data/steamdb_history.json"

def generate(db_path=DB,out_path=OUT,days=120):
    db_path,out_path=Path(db_path),Path(out_path)
    border=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=days)).date().isoformat()
    data={}
    if db_path.exists():
        with sqlite3.connect(db_path) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "steam_price_history" in tables:
                for appid,date,price in db.execute("""SELECT appid,observed_date,price
                    FROM steam_price_history WHERE currency='CNY' AND observed_date>=?
                    ORDER BY appid,observed_date""",(border,)):
                    if price is not None and price>0:
                        data.setdefault(str(appid),[]).append({"date":date,"price":round(price,2),"source":"Steam"})
            if "key_price_history" in tables:
                for appid,date,price,platform,kind in db.execute("""SELECT appid,observed_date,price,platform,kind
                    FROM key_price_history WHERE observed_date>=? ORDER BY appid,observed_date""",(border,)):
                    if price is not None and price>0 and not(platform=="SteamPY" and price<=0.10):
                        data.setdefault(str(appid),[]).append({"date":date,"price":round(price,2),
                            "source":str(platform),"kind":kind})
    # SteamDB is optional manual, sourced data; there is no SteamDB crawler.
    if STEAMDB.exists():
        try:
            imported=json.loads(STEAMDB.read_text("utf-8"))
            for aid,points in (imported.get("games") or {}).items():
                if not str(aid).isdigit() or not isinstance(points,list):continue
                for entry in points:
                    if not isinstance(entry,dict) or entry.get("source")!="SteamDB" or entry.get("currency")!="CNY":continue
                    try:
                        date=dt.date.fromisoformat(entry["date"])
                        amount=float(entry["price"])
                    except (KeyError,ValueError,TypeError):continue
                    if date.isoformat()<border or not 0<amount<100000:continue
                    url=entry.get("source_url")
                    if url!=f"https://steamdb.info/app/{int(aid)}/":continue
                    data.setdefault(str(int(aid)),[]).append({
                        "date":date.isoformat(),"price":round(amount,2),
                        "source":"SteamDB","source_url":url,
                        "kind":"manual_authorized_import"})
        except (OSError,ValueError,TypeError,AttributeError) as exc:
            print("SteamDB import unavailable:",str(exc)[:150])
    for appid,points in data.items():
        points.sort(key=lambda x:(x["date"],x["source"]))
        data[appid]=points[-300:]
    output={"meta":{"days":days,"note":"本站实际观测记录及可选的手动授权 SteamDB 来源记录；不代表完整史低或散 Key 实时库存"},
            "games":data}
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n","utf-8")
    print("Exported price history:",len(data),"games")
    return output

if __name__=="__main__":
    generate()
