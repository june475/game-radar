"""Import manually supplied, authorized SteamDB CN historical observations.
No automated HTTP requests to SteamDB are made.

CSV columns: appid,date,price_cny,source_url
Dates ISO YYYY-MM-DD. Prices represent CNY amounts, never cents.
The URL is checked for the matching SteamDB game page; this validates
format/provenance labeling, not the factual accuracy of user input.
"""
import argparse
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/steamdb_import.csv"
OUT=ROOT/"data/steamdb_history.json"
FIELDS={"appid","date","price_cny","source_url"}

def parse_row(row):
    aid=int(row["appid"])
    if aid<=0 or aid>9999999999:raise ValueError("invalid appid")
    date=dt.date.fromisoformat(str(row["date"]).strip())
    if date>dt.datetime.now(dt.timezone.utc).date()+dt.timedelta(days=1):
        raise ValueError("future observation")
    amount=float(row["price_cny"])
    if not math.isfinite(amount) or not 0<amount<100000:
        raise ValueError("invalid CNY amount")
    url=str(row["source_url"]).strip()
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.hostname!="steamdb.info" or not re.fullmatch(
        rf"/app/{aid}/?",parts.path):
        raise ValueError("source_url must match the SteamDB AppID")
    return str(aid),{"date":date.isoformat(),"price":round(amount,2),
          "source":"SteamDB","source_url":url,"currency":"CNY",
          "region":"CN","kind":"manual_authorized_import"}

def convert(source=SOURCE,out=OUT):
    source,out=Path(source),Path(out)
    rows={}
    if source.exists():
        with source.open("r",newline="",encoding="utf-8-sig") as fp:
            reader=csv.DictReader(fp)
            if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
                raise ValueError("CSV columns required: "+",".join(sorted(FIELDS)))
            for line,row in enumerate(reader,2):
                if not any(str(v or "").strip() for v in row.values()):continue
                try:aid,item=parse_row(row)
                except (KeyError,ValueError,TypeError) as exc:
                    raise ValueError(f"CSV line {line}: {exc}") from exc
                rows.setdefault(aid,{})[(item["date"],item["source_url"])]=item
    data={"meta":{"source":"SteamDB","mode":"manually supplied authorized records",
         "note":"无 SteamDB 自动抓取。仅显示明确输入的国区价格记录，真实性由提供者确认。"},
         "games":{aid:sorted(values.values(),key=lambda r:r["date"])
                 for aid,values in rows.items()}}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return data

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=SOURCE)
    parser.add_argument("--output",type=Path,default=OUT)
    options=parser.parse_args()
    data=convert(options.source,options.output)
    print("SteamDB imported observations",sum(map(len,data["games"].values())))
