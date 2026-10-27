"""Steam store candidate discovery, including personalized genres and experiments."""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request

SEARCH = "https://store.steampowered.com/search/results/"
# Steam user tag IDs; remote listings are only candidate discovery.
TAGS = {
    "puzzle":1664, "roguelike":1716, "roguelite":3959,
    "deckbuilder":32322, "rpg":122, "strategy":9,
    "simulation":599, "platformer":1625, "racing":699,
    "horror":1667, "visual_novel":3799, "city_builder":4328
}
SEARCH_PLANS = {
    "deal":[
        {"specials":1,"sort_by":"Reviews_DESC"},
        {"specials":1,"sort_by":"Price_ASC"},
        *({"specials":1,"tags":tag,"sort_by":"Reviews_DESC"} for tag in [1664,1716,3959,122,9,32322])
    ],
    "new":[
        {"sort_by":"Released_DESC"},
        *({"tags":tag,"sort_by":"Released_DESC"} for tag in [1664,1716,3959,122,9,32322])
    ],
    "explore":[
        {"sort_by":"Reviews_DESC","specials":1},
        {"sort_by":"Price_ASC","specials":1},
        *({"tags":tag,"sort_by":"Reviews_DESC","specials":1} for tag in [599,1625,699,1667,3799,4328])
    ]
}

def parse_ids(body):
    try:
        payload=json.loads(body)
        markup=payload.get("results_html") or ""
    except (ValueError,AttributeError):
        markup=body
    ids=re.findall(r"""data-ds-appid=["'](\d+)["']""",markup)
    if not ids:ids=re.findall(r"/app/(\d+)/",markup)
    return [int(s) for s in ids]

def discover(kind,pages=1,count=50,max_items=130):
    """Bound search traffic and blend genres so popular genres cannot dominate."""
    plans=SEARCH_PLANS[kind]
    batches=[]
    for plan in plans:
        hits=[]
        for page in range(pages):
            query={"query":"","start":page*count,"count":count,"infinite":1,
                   "cc":"cn","l":"schinese","hidef2p":1,"category1":998,**plan}
            url=SEARCH+"?"+urllib.parse.urlencode(query)
            try:
                req=urllib.request.Request(url,headers={
                    "User-Agent":"Mozilla/5.0 (compatible; GameRadar/2.2)",
                    "Accept":"application/json,text/html"})
                with urllib.request.urlopen(req,timeout=14) as r:
                    body=r.read(1200000).decode("utf-8","replace")
                hits.extend(parse_ids(body))
            except Exception as exc:
                print("Steam discovery failed",kind,plan,str(exc)[:120])
                break
        batches.append(hits)
    out=[];seen=set()
    for i in range(max((len(x) for x in batches),default=0)):
        for batch in batches:
            if i>=len(batch):continue
            appid=batch[i]
            if appid in seen:continue
            seen.add(appid)
            out.append({"id":appid,"_flag":kind,"_search":True})
            if len(out)>=max_items:
                print("Steam discovery",kind,"unique",len(out))
                return out
    print("Steam discovery",kind,"unique",len(out))
    return out

def parse_release(value):
    value=re.sub(r"\s+"," ",str(value or "").strip())
    m=re.search(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?",value)
    if m:
        try:return dt.date(*map(int,m.groups()))
        except ValueError:return None
    for pattern in ("%d %b, %Y","%d %B, %Y","%b %d, %Y",
                    "%B %d, %Y","%d %b %Y","%d %B %Y","%Y-%m-%d"):
        try:return dt.datetime.strptime(value,pattern).date()
        except ValueError:pass
    return None

def classify(flag,release_date,coming_soon,today,recent_days=120):
    if coming_soon:return None
    date=parse_release(release_date)
    if flag=="new":
        if date is not None and dt.timedelta(0)<=(today-date)<=dt.timedelta(days=recent_days):
            return "new"
        return None
    if flag=="explore":return "explore"
    if date is not None and dt.timedelta(0)<=(today-date)<=dt.timedelta(days=recent_days):
        return None
    return "deal"

def discovery_score(game):
    """Independent of taste_score: quality and low CN price drive experimentation."""
    pct=game.get("review_pct")
    count=game.get("review_count") or 0
    price=game.get("price") or 999999
    if pct is None or pct<85 or count<100 or price<=0 or price>40:
        return None
    quality=min(10,(pct-80)*.3+5)
    confidence=min(1,count/1000)
    affordability=10 if price<=10 else 9 if price<=20 else 8 if price<=30 else 7
    return round(quality*.65+affordability*.30+confidence*.5,2)
