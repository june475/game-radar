#!/usr/bin/env python3
import json, urllib.request, urllib.parse, datetime, time, urllib.error, os
from pathlib import Path
from market import enrich, clean_offers
from availability import epic_history, metadata
from storage import save as save_database, statistics as db_statistics
from discovery import discover, classify, discovery_score
from review_analysis import fetch_negative_reviews, reason_adjustment
from backlog import load_pending, save_pending, drop_processed
from check_recommendations import missing_categories

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; DATA.mkdir(exist_ok=True)
cfg=json.loads((ROOT/"config.json").read_text("utf-8"))
owned={x.lower() for x in cfg["owned"]}
START=time.monotonic()
MODE=os.environ.get("RADAR_MODE","daily").strip().lower()
PENDING_PATH=DATA/"pending.json"
PROCESSED=set()
# Bound total external work; a rate-limited Steam must not block deployment.
FETCH_BUDGET_SECONDS=165
REVIEWS_MAX_CALLS=65
REVIEWS_CALLS=0
REVIEWS_BLOCKED=False
cache_file=DATA/"reviews_cache.json"
try: reviews_cache=json.loads(cache_file.read_text("utf-8"))
except (OSError,ValueError): reviews_cache={}
try:
    previous_games=json.loads((DATA/"games.json").read_text("utf-8")).get("games",[])
except (OSError,ValueError): previous_games=[]
for previous in previous_games:
    aid=str(previous.get("appid") or "")
    if aid and previous.get("review_pct") is not None and aid not in reviews_cache:
        reviews_cache[aid]={"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "value":{"total":previous.get("review_count") or 0,
                     "pct":previous.get("review_pct"),"scope":previous.get("review_scope") or "历史缓存",
                     "positive":0,"desc":None}}

hp=DATA/"history.json"
try: hist=json.loads(hp.read_text("utf-8"))
except: hist={}

# 手工核实后可持续扩充；未核实的内容不自动猜测
mobile_verified=cfg.get("mobile_verified",{})
epic_free=cfg.get("epic_free_exclude",[])
epic_records=epic_history()

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GameRadar/1.1"})
    with urllib.request.urlopen(req,timeout=9) as r:return json.load(r)

def details(appid):
    try:
        d=get(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn&l=schinese")
        return d.get(str(appid),{}).get("data") or {}
    except Exception:return {}

def reviews(appid):
    """Cache previous results; stop querying Steam globally after HTTP 429."""
    global REVIEWS_CALLS,REVIEWS_BLOCKED
    key=str(appid)
    record=reviews_cache.get(key) or {}
    try:
        age=(datetime.datetime.now(datetime.timezone.utc)-
            datetime.datetime.fromisoformat(record["updated"])).total_seconds()
    except (ValueError,TypeError,KeyError):age=10**9
    if record.get("value") and age<7*86400:
        return record["value"]
    empty={"total":0,"positive":0,"pct":None,"scope":"不可用","desc":None}
    if REVIEWS_BLOCKED or REVIEWS_CALLS>=REVIEWS_MAX_CALLS or time.monotonic()-START>FETCH_BUDGET_SECONDS:
        return record.get("value") or empty
    # One request per app, not a second fallback immediately on a 429.
    for language,scope in (("schinese","简中"),("all","全球")):
        if REVIEWS_CALLS>=REVIEWS_MAX_CALLS or REVIEWS_BLOCKED:break
        REVIEWS_CALLS+=1
        try:
            query=urllib.parse.urlencode({"json":1,"filter":"all","language":language,
                "purchase_type":"all","num_per_page":1})
            r=get(f"https://store.steampowered.com/appreviews/{appid}?{query}")
            summary=r.get("query_summary") or {}
            total=int(summary.get("total_reviews") or 0)
            pos=int(summary.get("total_positive") or 0)
            if total>0:
                result={"total":total,"positive":pos,"pct":round(pos*100/total,1),
                        "scope":scope,"desc":summary.get("review_score_desc")}
                reviews_cache[key]={"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    "value":result}
                return result
        except urllib.error.HTTPError as exc:
            if exc.code==429:
                REVIEWS_BLOCKED=True
                print("Steam review HTTP 429: circuit breaker activated; using cache, skipping remaining review requests")
                break
            print("Steam review HTTP error",appid,exc.code)
            break
        except Exception as exc:
            print("Steam review error",appid,str(exc)[:110])
            break
    return record.get("value") or empty

# 权重核心：符合口味 > 游戏质量 > 价格
PREF={
 "RPG":2.5,"角色扮演":2.5,"策略":2.3,"Strategy":2.3,
 "解谜":3.0,"Puzzle":3.0,"Roguelike":3.0,"Roguelite":3.0,
 "卡牌":2.5,"Deckbuilding":2.7,"回合制":2.3,"Turn-Based":2.3,
 "剧情丰富":2.0,"Story Rich":2.0,"单人":1.8,"Single-player":1.8,
 "冒险":1.0,"Adventure":1.0
}
NEG={"大型多人在线":-1.8,"Massively Multiplayer":-1.8,"PvP":-1.0}

existing_pending=load_pending(PENDING_PATH)
if MODE=="compensate":
    missing_kinds=set(missing_categories(DATA/"games.json"))
    print("Empty recommendation categories:",sorted(missing_kinds))
    if not missing_kinds:
        print("All categories have recommendations; no remote scraping needed")
        raise SystemExit(0)
    # Only empty tabs require compensation. Previously recommended tabs are untouched.
    raw=[x for x in existing_pending if x.get("_flag") in missing_kinds]
    for kind in sorted(missing_kinds):
        if not any(x.get("_flag")==kind for x in raw):
            print("No backlog for",kind,"-- discovering candidates for this category")
            raw.extend(discover(kind,pages=1,count=50,max_items=60))
    if "explore" in missing_kinds:
        # Priority recommendation explicitly requested by the user.
        known={x.get("id") for x in raw if x.get("_flag")=="explore"}
        raw=[{"id":aid,"_flag":"explore","_watchlisted":True}
             for aid in cfg.get("explore_watchlist",[])
             if isinstance(aid,int) and aid not in known]+raw
    print("Missing-category compensation candidates:",len(raw))
else:
    src=get("https://store.steampowered.com/api/featuredcategories?cc=cn&l=schinese")
    buckets={"deal":[],"new":[],"explore":[]}
    for key, flag in (("specials","deal"),("new_releases","new")):
        for x in (src.get(key) or {}).get("items",[]):
            buckets[flag].append(dict(x,_flag=flag))
    for kind in ("deal","new","explore"):
        buckets[kind].extend(discover(kind,pages=1,count=50,max_items=90))
    for watch_id in cfg.get("explore_watchlist",[]):
        if isinstance(watch_id,int) and watch_id>0:
            buckets["explore"].insert(0,{"id":watch_id,"_flag":"explore","_watchlisted":True})
    watch_ids={x for x in cfg.get("explore_watchlist",[]) if isinstance(x,int)}
    watch=[x for x in buckets["explore"] if x.get("id") in watch_ids]
    pools={kind:[x for x in buckets[kind] if x.get("id") not in watch_ids]
           for kind in ("deal","new","explore")}
    ordered=watch[:]
    for i in range(max(map(len,pools.values()),default=0)):
        for kind in ("explore","deal","new"):
            if i<len(pools[kind]):ordered.append(pools[kind][i])
    # Resume prior unfinished items before today's fresh candidates.
    raw=existing_pending+ordered
    print("Discovered candidates:",len(ordered),"backlog:",len(existing_pending))
# Persist queue before any remote app/review queries.
save_pending(PENDING_PATH,raw)
raw=load_pending(PENDING_PATH)
if MODE=="compensate":
    # The persistent file retains all categories, but this run must only
    # spend API requests on categories with zero published recommendations.
    raw=[item for item in raw if item.get("_flag") in missing_kinds]
print("pending queue size for this run",len(raw))

seen=set(); games=[]; today=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)).date()
for x in raw:
    if time.monotonic()-START>FETCH_BUDGET_SECONDS:
        print("External fetch time budget reached; publishing partial results")
        break
    appid=x.get("id"); name=x.get("name","")
    if isinstance(appid,int) and x.get("_flag") in ("deal","new","explore"):
        PROCESSED.add((x["_flag"],appid))
    if not appid or (x["_flag"],appid) in seen or name.lower() in owned or name in epic_free:continue

    d=details(appid)
    if not d:
        # Remote failure: retain the work item for the next compensation run.
        PROCESSED.discard((x["_flag"],appid))
        continue
    rv=reviews(appid)
    name=d.get("name") or name or str(appid)
    if name.lower() in owned or name in epic_free:continue
    price_data=d.get("price_overview") or {}
    cents=x.get("final_price") if x.get("final_price") is not None else price_data.get("final")
    original_cents=x.get("original_price") if x.get("original_price") is not None else price_data.get("initial")
    price=(cents or 0)/100
    original=(original_cents or cents or 0)/100
    if (price<=0 and not x.get("_watchlisted")) or (x["_flag"]=="deal" and price>80):continue
    if x["_flag"]=="deal" and not (x.get("discount_percent") or price_data.get("discount_percent")):
        continue
    # Capture actual candidate prices in SQLite, including search-discovered titles.
    x["final_price"]=cents
    x["original_price"]=original_cents or cents
    x["discount_percent"]=x.get("discount_percent") or price_data.get("discount_percent") or 0
    release_info=d.get("release_date") or {}
    release_date=release_info.get("date") or None
    coming_soon=bool(release_info.get("coming_soon",False))
    category=classify(x["_flag"],release_date,coming_soon,today)
    if category is None:continue
    # An app may appear in both lists; the release date controls its category.
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

    old=hist.get(str(appid),{}).get("low"); newlow=price>0 and (old is None or price<old)
    if price>0:
        hist[str(appid)]={"name":name,"low":min(price,old) if old is not None else price,"last":price}
    if newlow and price>0: price_score=min(10,round(price_score+.3,1))

    # 45%口味 + 35%质量 + 20%价格；新游评价不足时用中性质量分
    q_for_rank=quality if rv["pct"] is not None else 6.5
    final=round(taste*.45+q_for_rank*.35+price_score*.20,1)
    # 完全不匹配口味的折扣游戏不进入推荐；新游允许较低门槛进入观察
    if category=="deal" and taste<2.0:continue
    if category!="explore" and rv["pct"] is not None and rv["pct"]<65:continue

    info=metadata(appid,[name,d.get("name","")],epic_records,mobile_verified)
    if info["epic_exclude"]: continue
    m=info["mobile"]
    steam_subids=[int(s) for s in d.get("packages",[]) if str(s).isdigit()][:8]
    flags=[category]+(["mobile"] if m else [])
    tags=(["站内新低"] if newlow else [])+([f"-{disc}%"] if disc else [])+genres[:3]
    why=("匹配你的偏好："+ " / ".join(dict.fromkeys(reasons[:4]))) if reasons else "新游观察候选"
    if category=="explore":
        why="跳出个人口味：综合价格、评价规模及差评原因，关注玩法本身"
        if x.get("_watchlisted"): why="你已关注：不因好评率或价格被排除，重点查看差评原因"
    seen.add((x["_flag"],appid))
    games.append({
      "appid":appid,"name":(d.get("name") or ({"1371980":"恶意不息 / No Rest for the Wicked"}.get(str(appid))) or name),"name_en":name if name!=(d.get("name") or name) else None,"steam_subids":steam_subids,"release_date":release_date,"coming_soon":coming_soon,"price":price,"original_price":original,"discount":disc,
      "image":d.get("header_image") or x.get("large_capsule_image") or x.get("small_capsule_image"),
      "url":f"https://store.steampowered.com/app/{appid}/?cc=cn&l=schinese",
      "review":(f"{rv['scope']}好评 {rv['pct']}% · {rv['total']} 条" if rv["pct"] is not None else "Steam 评价数据暂不可用"),
      "review_pct":rv["pct"],"review_count":rv["total"],"review_scope":rv["scope"],
      "recommend_score":final,"taste_score":taste,"quality_score":quality,"price_score":price_score,
      "genres":genres,"tags":tags,"flags":flags,"category":category,"discovery_score":discovery_score({"review_pct":rv["pct"],"review_count":rv["total"],"price":price}) if category=="explore" else None,
      "watchlisted":bool(x.get("_watchlisted")),"why":why,
      "mobile":m,"epic_status":info["epic_status"],"epic_giveaway":info["epic_giveaway"],"epic_source":info["epic_source"],"dlc_status":"未自动核实",
      "key_price":None,"key_source":None,"steam_historical_low":None,"steam_historical_low_source":None,
      "steam_deck":None
    })

# Evaluate negative-review themes for the strongest exploration candidates.
# Deliberately bounded to avoid several hundred extra requests per day.
explore_candidates=sorted((g for g in games if g["category"]=="explore"),
    key=lambda g:(not g.get("watchlisted"),-(g["discovery_score"] or 0)))[:14]
for candidate in explore_candidates:
    if REVIEWS_BLOCKED or time.monotonic()-START>FETCH_BUDGET_SECONDS:
        info={"sample_size":0,"categories":[],"main_issue":None,"confidence":"限流或预算不足","note":"未获取新差评"}
    else:
        info=fetch_negative_reviews(candidate["appid"])
    if info.get("sample_size",0)==0 and candidate.get("negative_review_analysis",{}).get("sample_size",0)>0:
        info=candidate["negative_review_analysis"]
    candidate["negative_review_analysis"]=info
    candidate["discovery_score"]=round((candidate["discovery_score"] or 0)+reason_adjustment(info),2)
    if info.get("main_issue"):
        candidate["why"]="近期简中差评常提及："+info["main_issue"]+"（关键词样本，非定论）"
    elif candidate.get("watchlisted"):
        candidate["why"]="你关注的游戏；差评样本不足或原因尚未确认"
    else:
        candidate["why"]="跨类型发现：结合价格、玩家评价及差评样本综合考虑"

# Preserve previous published entries on compensation; do not blank other tabs.
previous_by_id={(g.get("category"),g.get("appid")):g for g in previous_games
               if isinstance(g,dict) and g.get("appid") and g.get("category") in ("deal","new","explore")}
for game in games:
    key=(game.get("category"),game.get("appid"))
    old=previous_by_id.get(key)
    if old:
        if game.get("review_pct") is None and old.get("review_pct") is not None:
            for field in ("review_pct","review_count","review_scope","review","quality_score"):
                game[field]=old.get(field)
        for field in ("negative_review_analysis","key_offers","region_history_low"):
            if not game.get(field) and old.get(field):
                game[field]=old[field]
    # Cached third-party quotes may contain sentinel prices (e.g. CNY 0.10).
    game["key_offers"]=clean_offers(game.get("key_offers"),game.get("price"))
    game["key_reference_min"]=min((o["price"] for o in game["key_offers"]),default=None)
    previous_by_id[key]=game
games=list(previous_by_id.values())
deals=sorted((g for g in games if g["category"]=="deal"),key=lambda g:(-g["recommend_score"],-g["taste_score"],g["price"]))[:30]
new_games=sorted((g for g in games if g["category"]=="new"),key=lambda g:(-g["recommend_score"],-g["taste_score"],g["price"]))[:30]
# Dedicated exploration pool, ranked by quality and affordability only.
personalized_ids={g["appid"] for g in deals+new_games}
explore_games=sorted((g for g in explore_candidates if g["appid"] not in personalized_ids),
    key=lambda g:(not g.get("watchlisted"),-(g["discovery_score"] or 0),g["price"]))[:20]
games=deals+new_games+explore_games
# Gradually enrich criticism reasons for older and newly released games too,
# without turning every publish into dozens of Steam review requests.
if not REVIEWS_BLOCKED and time.monotonic()-START<FETCH_BUDGET_SECONDS-35:
    targets=[g for g in games if g.get("category")!="explore" and
             not (g.get("negative_review_analysis") or {}).get("sample_size")]
    offset=today.toordinal()%max(len(targets),1)
    targets=(targets[offset:]+targets[:offset])[:5]
    for g in targets:
        if time.monotonic()-START>FETCH_BUDGET_SECONDS-12:break
        analysis=fetch_negative_reviews(g["appid"],limit=20)
        if analysis.get("sample_size",0)>0:
            g["negative_review_analysis"]=analysis
for game in games:
    game["key_offers"]=clean_offers(game.get("key_offers"),game.get("price"))
    game["key_reference_min"]=min((o["price"] for o in game["key_offers"]),default=None)
print("selected separately",{"deals":len(deals),"new":len(new_games),"explore":len(explore_games)})
for g in games:
    try:
        if time.monotonic()-START>FETCH_BUDGET_SECONDS:
            g["key_offers"]=[]
            g["tracked_low"]=hist.get(str(g["appid"]),{}).get("low")
            continue
        enrich(g,hist)
    except Exception as exc:
        print("Market enrichment error",g["appid"],str(exc)[:140])
        g["key_offers"]=[];g["tracked_low"]=hist.get(str(g["appid"]),{}).get("low")
# Persist incomplete items for later compensation runs.
remaining=drop_processed(PENDING_PATH,PROCESSED)
print("Compensation state",{"mode":MODE,"processed":len(PROCESSED),"remaining":remaining})
cn=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)
db_path=DATA/"game_radar.db"
db_result=save_database(db_path,games,raw,cfg,hist,epic_records,cn)
print("SQLite saved:",db_result,db_statistics(db_path))
out={"meta":{"updated_at_cn":cn.strftime("%Y-%m-%d %H:%M"),"version":"V4 review-context discovery","note":"尝鲜榜不设价格或好评率硬门槛；查看近期简中差评关键词，区别争议类型。分析是辅助证据，不代表玩家差评全部属实或无效。"},"counts":{"deal":len(deals),"new":len(new_games),"explore":len(explore_games)},"games":games}
(DATA/"games.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
cache_file.write_text(json.dumps(reviews_cache,ensure_ascii=False,indent=2),"utf-8")
print("Steam review diagnostics",{"calls":REVIEWS_CALLS,"rate_limited":REVIEWS_BLOCKED,
      "cached":len(reviews_cache),"elapsed_seconds":round(time.monotonic()-START,1)})
hp.write_text(json.dumps(hist,ensure_ascii=False,indent=2),"utf-8")
print("updated",len(games))
