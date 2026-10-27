"""Daily Steam CN popular discounted games at a source-verifiable price low.

Steam's specials search supplies popularity order (not user taste).
SteamRaw may provide a CNY coverage-period low, NOT a complete lifetime low.
Only show a title if current CN price <= a trusted recorded CNY low.
Never substitute the project's own short history for an all-time low.
"""
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
from market import steamraw

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUTPUT=DATA/"hot_low.json"
CACHE=DATA/"hot_low_cache.json"
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

def valid_low(price,info):
    """The low only certifies its stated observation window, never lifetime."""
    if not isinstance(info,dict) or info.get("source")!="SteamRaw":return False
    try:return float(price)>0 and float(info["price"])>0 and float(price)<=float(info["price"])+0.011
    except (ValueError,TypeError,KeyError):return False

def load(path,default):
    try:return json.loads(path.read_text("utf-8"))
    except (ValueError,OSError):return default

def collect(max_checked=36):
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    old=load(OUTPUT,{})
    cached=load(CACHE,{})
    old_by_id={g["appid"]:g for g in old.get("games",[]) if isinstance(g,dict) and isinstance(g.get("appid"),int)}
    try: ids=popular_deals()
    except Exception as exc:
        print("Steam specials unavailable",str(exc)[:160]);ids=[]
    if not ids:
        print("No updated popularity ranking; preserving existing file unchanged")
        return old.get("games",[])
    ranked=[];checked=0
    for rank,appid in enumerate(ids,1):
        if checked>=max_checked:break
        prev=cached.get(str(appid),{})
        updated=None
        try:updated=dt.datetime.fromisoformat(prev.get("checked_at",""))
        except (TypeError,ValueError):pass
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
            low=prev.get("low")
            if (not updated or (now-updated).total_seconds()>7*86400 or not low):
                low=steamraw(appid)
            cached[str(appid)]={"checked_at":now.isoformat(),"low":low}
            verified=valid_low(price,low)
            ranked.append({
                "appid":appid,"name":d.get("name") or str(appid),
                "image":d.get("header_image"),"url":f"https://store.steampowered.com/app/{appid}/?cc=cn&l=schinese",
                "category":"hot","price":price,
                "original_price":round((offer.get("initial") or final)/100,2),
                "discount":discount,"release_date":(d.get("release_date") or {}).get("date"),
                "genres":[x.get("description") for x in d.get("genres",[]) if x.get("description")],
                "tags":["Steam 热门特惠"]+(["已核实覆盖期低价"] if verified else ["史低待核实"]),
                "why":"来自 Steam 热销特惠排序；"+("现价达到 SteamRaw 已记录覆盖期低价" if verified else "当前有折扣，尚未核实是否为史低"),
                "popularity_rank":rank,"price_low_verified":low["price"] if verified else None,
                "low_verified":verified,
                "price_low_source":low.get("source") if verified else None,"price_low_url":low.get("url") if verified else None,
                "price_low_scope":"SteamRaw 覆盖期低价（不是全历史史低）" if verified else "史低待核实",
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
                "low_scope":"SteamRaw 覆盖期低点，非 Steam 全历史史低",
                "checked":checked},"games":ranked[:30]}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n","utf-8")
    CACHE.write_text(json.dumps(cached,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("Hot low games",len(ranked),"checked",checked,"candidates",len(ids))
    return ranked

if __name__=="__main__":
    collect(max_checked=int(os.environ.get("HOT_MAX_CHECKED","36")))
