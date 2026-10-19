#!/usr/bin/env python3
import json, urllib.request, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; DATA.mkdir(exist_ok=True)
cfg=json.loads((ROOT/"config.json").read_text("utf-8")); owned={x.lower() for x in cfg["owned"]}
hp=DATA/"history.json"
try: hist=json.loads(hp.read_text("utf-8"))
except: hist={}
def get(url):
 r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GameRadar/1.0"})
 with urllib.request.urlopen(r,timeout=30) as x:return json.load(x)
src=get("https://store.steampowered.com/api/featuredcategories?cc=cn&l=schinese")
items=[]
for bucket,flag in [("specials","deal"),("new_releases","new")]:
 for x in (src.get(bucket) or {}).get("items",[]): x=dict(x);x["_flag"]=flag;items.append(x)
seen=set(); games=[]
for x in items:
 appid=x.get("id");name=x.get("name","")
 if not appid or appid in seen or name.lower() in owned:continue
 seen.add(appid);price=(x.get("final_price") or 0)/100;original=(x.get("original_price") or x.get("final_price") or 0)/100
 if price<=0 or (x["_flag"]=="deal" and price>60):continue
 disc=x.get("discount_percent") or 0;old=hist.get(str(appid),{}).get("low");newlow=old is None or price<old
 hist[str(appid)]={"name":name,"low":min(price,old) if old is not None else price,"last":price}
 score=7+(1.2 if price<=10 else .7 if price<=30 else .2)+(0.8 if disc>=75 else .4 if disc>=50 else 0)+(0.3 if newlow else 0)
 games.append({"appid":appid,"name":name,"price":price,"original_price":original,"discount":disc,"image":x.get("large_capsule_image") or x.get("small_capsule_image"),"url":f"https://store.steampowered.com/app/{appid}/?cc=cn&l=schinese","review":"价格数据来自 Steam","recommend_score":min(9.9,round(score,1)),"tags":(["站内新低"] if newlow else [])+([f"-{disc}%"] if disc else [])+["Steam国区"],"flags":[x["_flag"]],"why":"自动候选：低价/高折扣优先。Epic赠送史、Key、DLC、中文差评和手机移植需额外核验。"})
games.sort(key=lambda g:(-g["recommend_score"],g["price"]));games=games[:30]
cn=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)
(DATA/"games.json").write_text(json.dumps({"meta":{"updated_at_cn":cn.strftime("%Y-%m-%d %H:%M"),"note":"站内新低=本项目开始追踪后的最低价，并非SteamDB全历史史低。"},"games":games},ensure_ascii=False,indent=2),"utf-8")
hp.write_text(json.dumps(hist,ensure_ascii=False,indent=2),"utf-8")
print("updated",len(games))
