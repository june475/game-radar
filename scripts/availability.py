"""Verified mobile ports and conservative third-party Epic giveaway history."""
import json, re, urllib.request, datetime

EPIC_HISTORY_URL="https://raw.githubusercontent.com/renshuki/efgtracker/master/data/free_games.json"
EPIC_HISTORY_SOURCE="https://github.com/renshuki/efgtracker"
MOBILE={
 "1282730":{"android":"已上线","ios":"已上线","source":"https://view.news.eu.nasdaq.com/view?id=bc3adf83be32f923a5cddbc872fea18cf&lang=en&src=micro","status":"官方移植"},
 "413150":{"android":"已上线","ios":"已上线","source":"https://www.stardewvalley.net/faq/","status":"官方移植"}
}
# Never equate missing data with verified absence.
def normalized(s):
    s=str(s or "").lower().strip()
    s=re.sub(r"(?i)\\b(tm|remastered|definitive edition)\\b","",s)
    s=re.sub(r"[^a-z0-9\\u4e00-\\u9fff]+","",s)
    return s

def epic_history():
    req=urllib.request.Request(EPIC_HISTORY_URL,headers={"User-Agent":"GameRadar/1.3"})
    try:
        with urllib.request.urlopen(req,timeout=18) as r:
            data=json.load(r)
        games=data.get("games",{})
        iterable=games.values() if isinstance(games,dict) else games
        today=datetime.datetime.now(datetime.timezone.utc)
        found={}
        for item in iterable:
            if not isinstance(item,dict):continue
            title=item.get("title","");key=normalized(title)
            if not key:continue
            start=item.get("start_date")
            try:
                start_time=datetime.datetime.fromisoformat(start.replace("Z","+00:00")) if start else today
            except (ValueError,AttributeError):continue
            if start_time>today:continue
            found[key]={"title":title,"date":start[:10] if start else None,"url":item.get("store_url"),"source":EPIC_HISTORY_SOURCE}
        return found
    except Exception as exc:
        print("Epic history unavailable:",str(exc)[:160])
        return {}

def metadata(appid, names, epic, manual_mobile=None):
    m=(manual_mobile or {}).get(str(appid)) or MOBILE.get(str(appid))
    entry=None
    for name in names:
        if normalized(name) in epic:
            entry=epic[normalized(name)];break
    return {"mobile":m or None,
            "epic_status":"曾免费赠送" if entry else "未核实（历史库未匹配）",
            "epic_giveaway":entry,
            "epic_source":EPIC_HISTORY_SOURCE,
            "epic_exclude":bool(entry)}
