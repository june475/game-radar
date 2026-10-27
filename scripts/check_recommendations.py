"""Gate compensation by existing published recommendation categories."""
import json
import os
import sys
from pathlib import Path

CATEGORIES=("deal","new","explore")

def counts(path):
    try:
        data=json.loads(Path(path).read_text("utf-8"))
        items=data.get("games") or []
        if not isinstance(items,list):return {kind:0 for kind in CATEGORIES}
    except (OSError,ValueError,AttributeError):
        items=[]
    out={kind:0 for kind in CATEGORIES}
    for item in items:
        if not isinstance(item,dict):continue
        category=item.get("category")
        if category not in out:
            flags=item.get("flags") or []
            category="new" if "new" in flags else "deal" if "deal" in flags else None
        if category in out and isinstance(item.get("appid"),int):
            out[category]+=1
    return out

def missing_categories(path):
    found=counts(path)
    return [key for key in CATEGORIES if not found[key]]

def decision(path,mode):
    missing=missing_categories(path)
    return {
        "run": mode in ("daily","all") or bool(missing),
        "missing":missing,
        "counts":counts(path)
    }

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "compensate"
    path=Path(sys.argv[2]) if len(sys.argv)>2 else Path("data/games.json")
    result=decision(path,mode)
    print("Recommendation check:",result)
    output=os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as f:
            f.write("run="+str(result["run"]).lower()+"\n")
            f.write("missing="+",".join(result["missing"])+"\n")
