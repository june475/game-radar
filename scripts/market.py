"""Optional market data enrichment. Unverified quotes never become live prices."""
import json, urllib.request, urllib.parse
from datetime import datetime, timezone

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as r:
        if "json" not in r.headers.get("Content-Type","").lower():return None
        return json.load(r)

def num(value):
    try:
        v=float(value)
        return v if 0 < v < 100000 else None
    except (TypeError,ValueError):return None

def enrich(game, history):
    appid=game["appid"]
    game["key_offers"]=[]
    game["key_price"]=None
    game["key_source"]=None
    game["key_status"]="未核实实时在售"
    game["steam_historical_low"]=None
    game["steam_historical_low_source"]=None
    game["tracked_low"]=history.get(str(appid),{}).get("low")
    # SteamPY returns several types of offers. A keyPrice alone does not prove
    # an active, available, CN-activatable CD key, so keep it as a reference.
    try:
        u="https://steampy.com/xboot/common/plugIn/getGame?"+urllib.parse.urlencode({"appId":appid,"subId":0,"type":0})
        raw=fetch(u)
        payload=raw.get("data",{}) if isinstance(raw,dict) else {}
        if isinstance(payload,dict):
            p=num(payload.get("keyPrice"))
            if p is not None:
                game["key_offers"].append({"platform":"SteamPY","price":p,"status":"接口参考报价（库存/国区激活未核实）","url":"https://steampy.com/","checked_at":datetime.now(timezone.utc).isoformat()})
    except Exception:pass
    try:
        u="https://steamcici.com/prod-api/user/system/shopGame/list?"+urllib.parse.urlencode({"parentId":appid})
        raw=fetch(u)
        payload=raw.get("data",{}) if isinstance(raw,dict) else {}
        # lastLowSellPrice is historical, NOT a live listing
        if isinstance(payload,dict):
            p=num(payload.get("lastLowSellPrice"))
            if p is not None:
                game["key_offers"].append({"platform":"SteamCiCi","price":p,"status":"历史挂售参考价（非实时）","url":"https://steamcici.com/","checked_at":datetime.now(timezone.utc).isoformat()})
    except Exception:pass
    return game
