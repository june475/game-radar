"""Daily Steam CN popular discounted games, ranked independently of user preferences."""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from discovery import parse_ids

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUTPUT=DATA/"hot_low.json"
UA="Mozilla/5.0 (compatible; GameRadar/3.0; Steam CN deals)"

def request_json(url,timeout=12):
    req=urllib.request.Request(url,headers={"User-Agent":UA,
        "Accept":"application/json,text/html"})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read(1200000).decode("utf-8"))

def popular_deals(pages=3):
    """Steam best-selling specials ordering; independent of preferences."""
    found=[];seen=set()
    for page in range(pages):
        args={"query":"","start":page*50,"count":50,"infinite":1,
              "cc":"cn","l":"schinese","specials":1,
              "hidef2p":1,"ignore_preferences":1,"filter":"topsellers","category1":998}
        url="https://store.steampowered.com/search/results/?"+urllib.parse.urlencode(args)
        try:
            response=request_json(url)
            ids=parse_ids(json.dumps(response))
        except Exception as exc:
            print("Popular specials search error",str(exc)[:140])
            continue
        for appid in ids:
            if appid not in seen:
                found.append(appid);seen.add(appid)
    return found

def details(appid):
    args=urllib.parse.urlencode({"appids":appid,"cc":"cn","l":"schinese"})
    result=request_json("https://store.steampowered.com/api/appdetails?"+args)
    entry=result.get(str(appid),{}) if isinstance(result,dict) else {}
    return entry.get("data") if entry.get("success") else None

def load(path,default):
    try:return json.loads(path.read_text("utf-8"))
    except (ValueError,OSError):return default

def collect(max_checked=100):
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    old=load(OUTPUT,{})
    try: ids=popular_deals()
    except Exception as exc:
        print("Steam specials unavailable",str(exc)[:160]);ids=[]
    if not ids:
        print("No updated popularity ranking; preserving existing file unchanged")
        return old.get("games",[])
    ranked=[];checked=0
    for rank,appid in enumerate(ids,1):
        if checked>=max_checked:break
        # Do not keep an old price as if it were today's offer.
        try:
            d=details(appid)
            checked+=1
            if not d or d.get("is_free"):continue
            offer=d.get("price_overview") or {}
            final=offer.get("final")
            discount=offer.get("discount_percent") or 0
            if not isinstance(final,int) or final<=0 or not discount:continue
            price=round(final/100,2)
            ranked.append({
                "appid":appid,"name":d.get("name") or str(appid),
                "image":d.get("header_image"),"url":f"https://store.steampowered.com/app/{appid}/?cc=cn&l=schinese",
                "category":"hot","price":price,
                "original_price":round((offer.get("initial") or final)/100,2),
                "discount":discount,"release_date":(d.get("release_date") or {}).get("date"),
                "genres":[x.get("description") for x in d.get("genres",[]) if x.get("description")],
                "tags":["Steam 热门特惠"],
                "why":"来自 Steam 热销特惠列表，不按个人喜好筛选",
                "popularity_rank":rank,
                "review":"Steam 评价未在本榜单单独核实",
                "key_offers":[],"negative_review_analysis":None,
            })
        except Exception as exc:
            print("Hot low candidate error",appid,str(exc)[:110])
        if len(ranked)>=30:break
        time.sleep(.2)
    # Do not carry over stale 'hot' results: popularity and price change daily.
    ranked.sort(key=lambda g:g["popularity_rank"])
    out={"meta":{"updated_at_cn":(now+dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
                "rank_source":"Steam 商店热销特惠筛选（热度代理，不是实时销量榜）",
                "checked":checked},"games":ranked[:30]}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("Hot low games",len(ranked),"checked",checked,"candidates",len(ids))
    return ranked

if __name__=="__main__":
    collect(max_checked=int(os.environ.get("HOT_MAX_CHECKED","100")))
