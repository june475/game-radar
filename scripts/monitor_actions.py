"""Check GitHub Actions health and open/close one deduplicated incident issue."""
import datetime as dt
import json
import os
import urllib.error
import urllib.request

REQUIRED={"Collect and Repair Game Radar Data":30,
          "Enrich Missing Game Fields":5,
          "Refresh Popular Discount Games":30}
ISSUE_TITLE="[Game Radar] 自动更新任务异常"

def analyze(runs,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    latest={}
    for run in runs:
        name=run.get("name")
        if name in REQUIRED and name not in latest:
            latest[name]=run
    problems=[]
    for name,max_hours in REQUIRED.items():
        run=latest.get(name)
        if not run:
            problems.append(name+": 无运行记录")
            continue
        try:
            start=dt.datetime.fromisoformat(run["created_at"].replace("Z","+00:00"))
            elapsed=(now-start).total_seconds()/3600
        except (KeyError,TypeError,ValueError):
            problems.append(name+": 无有效运行时间")
            continue
        if run.get("conclusion")=="failure":
            problems.append(name+": 最新运行失败 "+str(run.get("html_url") or ""))
        elif run.get("status")=="completed" and run.get("conclusion") not in ("success","skipped"):
            problems.append(name+": 最新运行状态 "+str(run.get("conclusion")))
        elif elapsed>max_hours:
            problems.append(name+f": 超过 {max_hours} 小时没有新运行")
    return problems

def api(repo,token,path,method="GET",payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request("https://api.github.com/repos/"+repo+path,data=data,method=method,
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28","User-Agent":"GameRadar-monitor",
                 **({"Content-Type":"application/json"} if data else {})})
    with urllib.request.urlopen(req,timeout=25) as response:
        body=response.read()
        return json.loads(body) if body else {}

def main():
    repo=os.environ.get("GITHUB_REPOSITORY")
    token=os.environ.get("GH_TOKEN")
    if not repo or not token:raise RuntimeError("GITHUB_REPOSITORY and GH_TOKEN are required")
    runs=api(repo,token,"/actions/runs?per_page=80").get("workflow_runs",[])
    problems=analyze(runs)
    issues=api(repo,token,"/issues?state=open&per_page=100")
    existing=next((issue for issue in issues if issue.get("title")==ISSUE_TITLE and
                    "pull_request" not in issue),None)
    if problems:
        message="每日巡检发现以下问题（UTC）：\n\n"+ "\n".join("- "+p for p in problems)
        message+="\n\n请检查对应 GitHub Actions 运行日志。监控不会自动修改业务数据。"
        if existing:
            api(repo,token,f"/issues/{existing['number']}/comments","POST",{"body":message})
        else:
            api(repo,token,"/issues","POST",{"title":ISSUE_TITLE,"body":message})
        print("Health warning:",problems)
    elif existing:
        api(repo,token,f"/issues/{existing['number']}","PATCH",{"state":"closed"})
        print("Healthy; resolved monitoring issue")
    else:
        print("Healthy: all essential workflows have recent successful runs")

if __name__=="__main__":
    main()
