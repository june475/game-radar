"""Price enrichment. Never present a quote as available stock without proof."""
import json, os, logging, urllib.request, urllib.parse, datetime
from urllib.error import HTTPError, URLError

LOG=logging.getLogger("game-radar.market")
UA="Mozilla/5.0 (compatible; GameRadar/1.2; price research)"

def fetch(url, method="GET", payload=None, headers=None):
    h={"User-Agent":UA,"Accept":"application/json",**(headers or {})}
    data=None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:h["Content-Type"]="application/json"
    req=urllib.request.Request(url,headers=h,data=data,method=method)
    try:
        with urllib.request.urlopen(req,timeout=16) as response:
            body=response.read(500000)
            return json.loads(body)
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        LOG.warning("%s %s: %s",method,url.split("?")[0],str(exc)[:160])
        return None

def price(value):
    """Only accept explicit yuan amounts; never guess cents / other currencies."""
    try:
        if isinstance(value,bool):return None
        if isinstance(value,str):value=value.strip().replace("¥","").replace("￥","").replace(",","")
        v=float(value)
        return round(v,2) if 0<v<100000 else None
    except (ValueError,TypeError):return None

def objects(payload, limit=100):
    """Walk common nested envelopes, lists, and data/rows/results structures."""
    queue=[payload]; count=0
    while queue and count<limit:
        item=queue.pop(0);count+=1
        if isinstance(item,dict):
            yield item
            for key in ("data","result","rows","records","list","items","game","info","obj"):
                v=item.get(key)
                if isinstance(v,(dict,list)):queue.append(v)
        elif isinstance(item,list):queue.extend(item[:limit])

def parse_key_reference(raw, field_names):
    vals=[]
    for obj in objects(raw):
        for key in field_names:
            if key in obj:
                v=price(obj[key])
                if v is not None:vals.append(v)
    return min(vals) if vals else None

def steampy(appid):
    # Plugin endpoint requires a matching package subId/type for some products.
    # appId-only search is an unverified lead, never a guaranteed purchasable key.
    url="https://steampy.com/xboot/common/plugIn/getGame?"+urllib.parse.urlencode(
        {"appId":appid,"subId":0,"type":0}
    )
    result=fetch(url)
    if not isinstance(result,(dict,list)):return None
    p=parse_key_reference(result,("keyPrice",))
    if p is None:return None
    return {"platform":"SteamPY","price":p,"status":"接口参考价｜库存、版本、国区激活未核实",
            "url":"https://steampy.com/","kind":"reference",
            "checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}

def steamcici(appid):
    url="https://steamcici.com/prod-api/user/system/shopGame/list?"+urllib.parse.urlencode({"parentId":appid})
    result=fetch(url)
    if not isinstance(result,(dict,list)):return None
    p=parse_key_reference(result,("lastLowSellPrice",))
    if p is None:return None
    return {"platform":"SteamCiCi","price":p,"status":"历史挂售参考价｜非当前在售",
            "url":"https://steamcici.com/","kind":"historical_listing",
            "checked_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}

def steamraw(appid):
    # SteamRaw region prices are not necessarily a complete lifetime history.
    # Parse only explicit CN/CNY low records, with no cross-currency conversions.
    result=fetch(f"https://steamraw.com/api/app/{appid}/regions")
    if result is None:return None
    nodes=[]
    for obj in objects(result):
        code=str(obj.get("country") or obj.get("country_code") or obj.get("region") or obj.get("cc") or "").upper()
        currency=str(obj.get("currency") or obj.get("currency_code") or "").upper()
        if code in ("CN","CHINA") or currency=="CNY":nodes.append(obj)
        for key in ("CN","cn","CNY"):
            if isinstance(obj.get(key),dict):nodes.append(obj[key])
    for node in nodes:
        currency=str(node.get("currency") or node.get("currency_code") or "CNY").upper()
        if currency!="CNY":continue
        for k in ("historical_low","historicalLow","lowest_price","lowestPrice","lowest_recorded_price"):
            v=node.get(k)
            if isinstance(v,dict):
                v=v.get("amount") or v.get("value") or v.get("price")
            p=price(v)
            if p is not None:
                return {"price":p,"source":"SteamRaw","status":"SteamRaw 覆盖期内最低（非完整SteamDB史低）",
                        "url":f"https://steamraw.com/app/{appid}"}
    return None

def enrich(game, history):
    appid=game["appid"];offers=[]
    for fn in (steampy,steamcici):
        item=fn(appid)
        if item:offers.append(item)
    game["key_offers"]=offers
    # key_price deliberately empty: no source confirms currently available stock
    game["key_price"]=None;game["key_source"]=None
    game["key_status"]="未核实实时在售"
    game["key_reference_min"]=min((x["price"] for x in offers),default=None)
    game["tracked_low"]=history.get(str(appid),{}).get("low")
    game["steam_historical_low"]=None
    game["steam_historical_low_source"]=None
    game["region_history_low"]=steamraw(appid)
    game["steam_deck"]=game.get("steam_deck")
    return game
