"""Steam store search candidate discovery (best effort, no third-party keys)."""
import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request

SEARCH="https://store.steampowered.com/search/results/"

def discover(kind, pages=2, count=50):
    """Return app ID candidates; appdetails verifies type, dates and prices later."""
    found=[]; seen=set()
    for page in range(pages):
        query={"query":"","start":page*count,"count":count,"infinite":1,
               "cc":"cn","l":"schinese","hidef2p":1}
        if kind=="new":
            query["sort_by"]="Released_DESC"
        else:
            query.update({"specials":1,"sort_by":"Reviews_DESC"})
        url=SEARCH+"?"+urllib.parse.urlencode(query)
        try:
            request=urllib.request.Request(url,headers={
                "User-Agent":"Mozilla/5.0 (compatible; GameRadar/2.0)",
                "Accept":"application/json,text/html"})
            with urllib.request.urlopen(request,timeout=18) as response:
                body=response.read(1200000).decode("utf-8","replace")
            try:
                payload=json.loads(body)
                markup=payload.get("results_html") or ""
            except (ValueError,AttributeError):
                markup=body
            ids=re.findall(r'data-ds-appid=["\\\'](\\d+)["\\\']',markup)
            if not ids:
                ids=re.findall(r'/app/(\\d+)/',markup)
            for x in ids:
                appid=int(x)
                if appid not in seen:
                    seen.add(appid)
                    found.append({"id":appid,"_flag":"new" if kind=="new" else "deal",
                                  "_search":True})
        except Exception as exc:
            print("Steam search unavailable",kind,page,str(exc)[:130])
            break
    return found

def parse_release(value):
    """Conservative parser for common Steam release date formats."""
    value=str(value or "").strip()
    value=re.sub(r"\\s+"," ",value)
    match=re.search(r"(20\\d{2})\\s*[年./-]\\s*(\\d{1,2})\\s*[月./-]\\s*(\\d{1,2})\\s*日?",value)
    if match:
        try:return dt.date(*map(int,match.groups()))
        except ValueError:return None
    for pattern in ("%d %b, %Y","%d %B, %Y","%b %d, %Y","%B %d, %Y",
                    "%d %b %Y","%d %B %Y","%Y-%m-%d"):
        try:return dt.datetime.strptime(value,pattern).date()
        except ValueError:pass
    return None

def classify(flag, release_date, coming_soon, today, recent_days=120):
    """Never take a new-release slot with an old verified release date."""
    if coming_soon:return None
    date=parse_release(release_date)
    if flag=="new":
        if date is None:return None # Do not label unknown-release-date games as recent
        if dt.timedelta(0) <= (today-date) <= dt.timedelta(days=recent_days):return "new"
        return None
    if date is not None and dt.timedelta(0) <= (today-date) <= dt.timedelta(days=recent_days):
        return None # recent games belong to the separate new-game pool
    return "deal"
