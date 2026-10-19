#!/usr/bin/env python3
import json, urllib.request, urllib.parse, datetime, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; DATA.mkdir(exist_ok=True)
cfg=json.loads((ROOT/"config.json").read_text("utf-8"))
owned={x.lower() for x in cfg["owned"]}
hp=DATA/"history.json"
try: hist=json.loads(hp.read_text("utf-8"))
except: hist={}

# 手工核实后可持续扩充；未核实的内容不自动猜测
mobile_verified=cfg.get("mobile_verified",{})
epic_free=cfg.get("epic_free_exclude",[])

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GameRadar/1.1"})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def details(appid):
    try:
        d=get(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn&l=schinese")
        return d.get(str(appid),{}).get("data") or {}
    except Exception:return {}

def reviews(appid):
    try:
        r=get(f"https://store.steampowered.com/appreviews/{appid}?json=1&language=schinese&purchase_type=all&num_per_page=0")
        s=r.get("query_summary") or {}
        total=s.get("total_reviews",0); pos=s.get("total_positive",0)
        return {"total":total,"positive":pos,"pct":round(pos*100/total,1) if total else None,
                "desc":s.get("review_score_desc")}
    except Exception:return {"total":0,"positive":0,"pct":None,"desc":None}

# 权重核心：符合口味 > 游戏质量 > 价格
PREF={
 "RPG":2.5,"角色扮演":2.5,"策略":2.3,"Strategy":2.3,
 "解谜":3.0,"Puzzle":3.0,"Roguelike":3.0,"Roguelite":3.0,
 "卡牌":2.5,"Deckbuilding":2.7,"回合制":2.3,"Turn-Based":2.3,
 "剧情丰富":2.0,"Story Rich":2.0,"单人":1.8,"Single-player":1.8,
 "冒险":1.0,"Adventure":1.0
}
NEG={"大型多人在线":-1.8,"Massively Multiplayer":-1.8,"PvP":-1.0}

src=get("https://store.steampowered.com/api/featuredcategories?cc=cn&l=schinese")
raw=[]
for bucket,flag in [("specials","deal"),("new_releases","new")]:
    for x in (src.get(bucket) or {}).get("items",[]):
        y=dict(x);y["_flag"]=flag;raw.append(y)

seen=set(); games=[]
for x in raw:
    appid=x.get("id"); name=x.get("name","")
    if not appid or appid in seen or name.lower() in owned or name in epic_free:continue
    seen.add(appid)
    price=(x.get("final_price") or 0)/100; original=(x.get("original_price") or x.get("final_price") or 0)/100
    if price<=0 or (x["_flag"]=="deal" and price>80):continue

    d=details(appid); time.sleep(.12)
    rv=reviews(appid); time.sleep(.12)
    genres=[g.get("description","") for g in d.get("genres",[])]
    cats=[c.get("description","") for c in d.get("categories",[])]
    features=genres+cats

    taste=0.0; reasons=[]
    for f in features:
        if f in PREF: taste+=PREF[f]; reasons.append(f)
        if f in NEG: taste+=NEG[f]
    # Steam接口没有社区Tag时，用类型/功能做保守匹配
    taste=min(10,round(taste,1))

    quality=0.0
    if rv["pct"] is not None:
        quality=5.0
        if rv["pct"]>=95: quality=9.5
        elif rv["pct"]>=90: quality=8.8
        elif rv["pct"]>=85: quality=8.0
        elif rv["pct"]>=80: quality=7.2
        elif rv["pct"]>=70: quality=6.0
        else: quality=4.5
        if rv["total"]>=10000: quality+=.3
        elif rv["total"]>=1000: quality+=.15
    quality=min(10,round(quality,1))

    disc=x.get("discount_percent") or 0
    price_score=4.0+(2 if price<=10 else 1.4 if price<=30 else .8 if price<=60 else .2)+(1.5 if disc>=75 else 1 if disc>=50 else .4 if disc>=25 else 0)
    price_score=min(10,round(price_score,1))

    old=hist.get(str(appid),{}).get("low"); newlow=old is None or price<old
    hist[str(appid)]={"name":name,"low":min(price,old) if old is not None else price,"last":price}
    if newlow: price_score=min(10,round(price_score+.3,1))

    # 45%口味 + 35%质量 + 20%价格；新游评价不足时用中性质量分
    q_for_rank=quality if rv["pct"] is not None else 6.5
    final=round(taste*.45+q_for_rank*.35+price_score*.20,1)
    # 完全不匹配口味的折扣游戏不进入推荐；新游允许较低门槛进入观察
    if x["_flag"]=="deal" and taste<2.0:continue
    if rv["pct"] is not None and rv["pct"]<65:continue

    m=mobile_verified.get(str(appid))
    flags=[x["_flag"]]+(["mobile"] if m else [])
    tags=(["站内新低"] if newlow else [])+([f"-{disc}%"] if disc else [])+genres[:3]
    why=("匹配你的偏好："+ " / ".join(dict.fromkeys(reasons[:4]))) if reasons else "新游观察候选"
    games.append({
      "appid":appid,"name":name,"price":price,"original_price":original,"discount":disc,
      "image":d.get("header_image") or x.get("large_capsule_image") or x.get("small_capsule_image"),
      "url":f"https://store.steampowered.com/app/{appid}/?cc=cn&l=schinese",
      "review":(f"简中好评 {rv['pct']}% · {rv['total']} 条" if rv["pct"] is not None else "简中评价样本不足"),
      "review_pct":rv["pct"],"review_count":rv["total"],
      "recommend_score":final,"taste_score":taste,"quality_score":quality,"price_score":price_score,
      "genres":genres,"tags":tags,"flags":flags,"why":why,
      "mobile":m,"epic_status":"未自动核实","dlc_status":"未自动核实"
    })

games.sort(key=lambda g:(-g["recommend_score"],-g["taste_score"],g["price"]))
games=games[:24]
cn=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)
out={"meta":{"updated_at_cn":cn.strftime("%Y-%m-%d %H:%M"),"version":"V1 personalized","note":"推荐分=45%口味匹配+35%简中口碑+20%价格；站内新低不是SteamDB全历史史低。"},"games":games}
(DATA/"games.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
hp.write_text(json.dumps(hist,ensure_ascii=False,indent=2),"utf-8")
print("updated",len(games))
