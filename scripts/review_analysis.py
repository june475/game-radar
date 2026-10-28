"""Conservative keyword-assisted review diagnostics, not sentiment-model inference."""
import urllib.parse
import urllib.request
import json
import re

CATEGORIES = {
    "运营/商业争议": ("运营","官方","开发商","制作组","发行商","公关","声明","涨价","定价","背刺","收费","氪金","内购","dlc","割韭菜","骗钱","退款","画饼","承诺"),
    "性能/技术问题": ("卡顿","掉帧","优化","闪退","崩溃","bug","报错","帧数","内存","加载","掉线","服务器","联机问题","存档丢失","卡死"),
    "玩法/难度/操作": ("手感","战斗","操作","平衡","难度","数值","重复","刷刷刷","战斗系统","打击感","引导","地图","关卡","敌人"),
    "内容/完成度": ("内容少","未完成","烂尾","剧情","更新慢","没内容","缺少内容","任务","时长","抢先体验","半成品","未实装","更新频率"),
    "本地化/语言": ("翻译","中文","汉化","字体","字幕","本地化","机翻")
}
# A keyword match denotes a mentioned topic, NOT proof the criticism is valid.
def classify_texts(texts):
    counts={k:0 for k in CATEGORIES}
    for text in texts:
        s=str(text or "").lower()
        for label,terms in CATEGORIES.items():
            found=False
            for term in terms:
                for match in re.finditer(re.escape(term),s):
                    before=s[max(0,match.start()-6):match.start()]
                    if any(before.endswith(x) for x in ("没有","并无","不存在","毫无","不觉得","没遇到")):
                        continue
                    found=True
                    break
                if found:break
            if found:counts[label]+=1
    ranked=sorted(((label,n) for label,n in counts.items() if n),key=lambda v:-v[1])
    total=len(texts)
    primary=ranked[0][0] if ranked and ranked[0][1]>=2 else None
    return {"sample_size":total,"categories":[{"name":k,"mentions":v} for k,v in ranked[:4]],
            "main_issue":primary,"confidence":"样本有限" if total<15 else "仅关键词归类",
            "method":"关键词+明显否定短语过滤",
            "topic_share":{k:round(v/total,3) for k,v in ranked[:4]} if total else {},
            "note":"关键词仅表示话题被提及，无法完全理解语境；运营争议不自动视为无效。"}
def fetch_negative_reviews(appid,limit=30):
    query=urllib.parse.urlencode({"json":1,"filter":"recent","language":"schinese",
        "review_type":"negative","purchase_type":"all","num_per_page":limit,"cursor":"*"})
    url=f"https://store.steampowered.com/appreviews/{appid}?{query}"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GameRadar/2.4","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=12) as r: result=json.load(r)
        if not isinstance(result,dict) or result.get("success") != 1:
            return {"sample_size":0,"categories":[],"main_issue":None,"confidence":"无法核实","note":"Steam差评接口未提供有效样本"}
        texts=[x.get("review","") for x in result.get("reviews",[]) if isinstance(x,dict) and x.get("review")]
        return classify_texts(texts)
    except Exception as exc:
        print("Negative review analysis unavailable",appid,str(exc)[:110])
        return {"sample_size":0,"categories":[],"main_issue":None,"confidence":"无法核实","note":"无法获取差评样本"}
def reason_adjustment(info):
    """Small adjustments; no automatic disregard of operational complaints."""
    if not info or info.get("sample_size",0)<8:return 0
    topics={x["name"]:x["mentions"] for x in info.get("categories",[])}
    n=info["sample_size"]
    technical=topics.get("性能/技术问题",0)
    gameplay=topics.get("玩法/难度/操作",0)
    completion=topics.get("内容/完成度",0)
    ops=topics.get("运营/商业争议",0)
    if max(technical,gameplay,completion)>=max(4,n//3):
        return -1.2
    if ops>=max(4,n//3) and ops>max(technical,gameplay,completion):
        return 0.2 # only slightly increases consideration; not a blanket pardon
    return 0
