"""Export actual observed Steam and marketplace price records for static charts."""
import datetime as dt
import json
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/"data/game_radar.db"
OUT=ROOT/"data/price_history.json"

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
    for appid,points in data.items():
        points.sort(key=lambda x:(x["date"],x["source"]))
        data[appid]=points[-300:]
    output={"meta":{"days":days,"note":"仅为站内实际观察记录；不代表完整史低或散 Key 实时库存"},
            "games":data}
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":"))+"\n","utf-8")
    print("Exported price history:",len(data),"games")
    return output

if __name__=="__main__":
    generate()
