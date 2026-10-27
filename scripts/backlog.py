"""Idempotent cross-run backlog of unprocessed Steam candidates."""
import json
from pathlib import Path

def save_pending(path, candidates):
    path=Path(path)
    prior=load_pending(path)
    by_key={}
    # Prefer old backlog and maintain updated metadata where possible.
    for item in prior+candidates:
        kind=item.get("_flag")
        appid=item.get("id")
        if kind not in ("deal","new","explore") or not isinstance(appid,int):continue
        key=f"{kind}:{appid}"
        by_key[key]={**by_key.get(key,{}),**item}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(list(by_key.values()),ensure_ascii=False,indent=2),"utf-8")
    return len(by_key)

def load_pending(path):
    try:
        value=json.loads(Path(path).read_text("utf-8"))
        return value if isinstance(value,list) else []
    except (OSError,ValueError):
        return []

def drop_processed(path, processed):
    path=Path(path)
    keep=[x for x in load_pending(path) if (x.get("_flag"),x.get("id")) not in processed]
    path.write_text(json.dumps(keep,ensure_ascii=False,indent=2),"utf-8")
    return len(keep)
