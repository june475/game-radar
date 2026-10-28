/* Client-only preferences: localStorage is browser-local, not account sync. */
const RadarExtras=(()=>{
  const KEY="game-radar-wishlist-v1";
  const state={wish:{},history:{},historyLoaded:false};
  const read=()=>{try{const x=JSON.parse(localStorage.getItem(KEY)||"{}");return x&&typeof x==="object"&&!Array.isArray(x)?x:{}}catch{return {}}};
  state.wish=read();
  const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify(state.wish))}catch(e){console.warn("Wishlist storage disabled",e)}};
  const allGames=()=>[...(DATA.games||[]),...(DATA.hotGames||[])];
  const find=id=>allGames().find(g=>g.appid===Number(id));
  const minRef=g=>{
    const values=(g.key_offers||[]).filter(o=>recentQuote(o)&&o.kind!=="historical_listing"&&Number(o.price)>0 &&
      !(o.platform==="SteamPY"&&Number(o.price)<=0.10) &&
      !(Number(g.price)>0&&Number(o.price)<Math.max(.5,Number(g.price)*.03)))
      .map(o=>Number(o.price));
    return values.length?Math.min(...values):null;
  };
  const filters=()=>{
    const max=Number(document.querySelector("#max-price")?.value);
    const maxGiven=document.querySelector("#max-price")?.value.trim()!=="";
    const rating=Number(document.querySelector("#min-rating")?.value||0);
    const genre=(document.querySelector("#genre-filter")?.value||"").toLowerCase();
    const wishlist=document.querySelector("#wishlist-filter")?.classList.contains("active");
    return {max,maxGiven,rating,genre,wishlist,sort:document.querySelector("#sort-mode")?.value||"default"};
  };
  function select(items){
    const f=filters();
    const filtered=items.filter(g=>
      (!f.maxGiven||(Number(g.price)>0&&Number(g.price)<=f.max))&&
      (!f.rating||(Number(g.review_pct)>=f.rating))&&
      (!f.genre||(g.genres||[]).some(s=>String(s).toLowerCase()===f.genre))&&
      (!f.wishlist||Boolean(state.wish[g.appid]))
    );
    const methods={
      price_asc:(a,b)=>(a.price||Infinity)-(b.price||Infinity),
      price_desc:(a,b)=>(b.price||0)-(a.price||0),
      discount:(a,b)=>(b.discount||0)-(a.discount||0),
      reviews:(a,b)=>(b.review_count||0)-(a.review_count||0),
      rating:(a,b)=>(b.review_pct??-1)-(a.review_pct??-1)
    };
    return methods[f.sort]?[...filtered].sort(methods[f.sort]):filtered;
  }
  function refreshGenres(){
    const select=document.querySelector("#genre-filter");
    if(!select)return;
    const old=select.value;
    const values=[...new Set(allGames().flatMap(g=>g.genres||[]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"zh-CN"));
    select.replaceChildren(new Option("全部类型",""),...values.map(v=>new Option(v,v.toLowerCase())));
    select.value=old;
  }
  function cardActions(g){
    const wished=Boolean(state.wish[g.appid]);
    const target=state.wish[g.appid]?.target;
    return '<div class="radar-actions">'+
      '<button type="button" class="radar-wish" data-id="'+Number(g.appid)+'" aria-pressed="'+wished+'">'+(wished?"★ 已收藏":"☆ 加愿望单")+'</button>'+
      '<button type="button" class="radar-target" data-id="'+Number(g.appid)+'">目标价'+(target!=null?" ¥"+target:"")+'</button>'+
      '<button type="button" class="radar-history" data-id="'+Number(g.appid)+'">价格走势</button>'+
      '</div>';
  }
  function modify(id){
    if(state.wish[id])delete state.wish[id];
    else state.wish[id]={name:find(id)?.name||String(id),target:null, saved_at:new Date().toISOString()};
    persist();render();checkAlerts();
  }
  function setTarget(id){
    const entry=state.wish[id]||{name:find(id)?.name||String(id),target:null};
    const answer=prompt("设置 Steam 国区目标价（人民币；留空可清除）",entry.target??"");
    if(answer===null)return;
    const txt=answer.trim();
    if(txt===""){entry.target=null}
    else {
      const n=Number(txt);
      if(!Number.isFinite(n)||n<=0||n>100000){alert("请输入有效的人民币价格");return}
      entry.target=Math.round(n*100)/100;
    }
    state.wish[id]=entry;persist();render();checkAlerts();
  }
  function renderOfflist(){
    const node=document.querySelector("#saved-outside");
    if(!node)return;
    const enabled=document.querySelector("#wishlist-filter")?.classList.contains("active");
    const current=new Set(allGames().map(g=>String(g.appid)));
    const missing=Object.entries(state.wish).filter(([id])=>!current.has(id));
    node.hidden=!enabled||!missing.length;
    node.replaceChildren();
    if(node.hidden)return;
    const title=document.createElement("h3");title.textContent="已收藏但不在本期推荐中的游戏";
    const description=document.createElement("p");description.className="note";
    description.textContent="这些游戏仍保存在本机愿望单中；当前价格未知，暂不触发价格提醒。";
    node.append(title,description);
    for(const [id,item] of missing){
      const entry=document.createElement("div");entry.className="saved-entry";
      const link=document.createElement("a");
      link.href="https://store.steampowered.com/app/"+Number(id)+"/?cc=cn&l=schinese";
      link.target="_blank";link.rel="noopener noreferrer";
      link.textContent=item.name||"Steam AppID "+id;
      const value=document.createElement("span");
      value.textContent=item.target==null?"未设目标价":"目标价 ¥"+item.target;
      const remove=document.createElement("button");remove.type="button";
      remove.className="radar-wish";remove.dataset.id=id;remove.textContent="移除";
      const target=document.createElement("button");target.type="button";
      target.className="radar-target";target.dataset.id=id;target.textContent="调整目标价";
      entry.append(link,value,target,remove);node.append(entry);
    }
  }
  function importWishlist(file){
    if(!file)return;
    if(file.size>200000){alert("愿望单文件过大");return}
    file.text().then(raw=>{
      const obj=JSON.parse(raw);
      const rows=Array.isArray(obj.games)?obj.games:[];
      if(rows.length>500)throw Error("数量超出上限");
      for(const row of rows){
        const id=Number(row.appid),p=row.target==null?null:Number(row.target);
        if(!Number.isSafeInteger(id)||id<=0||!Number.isFinite(p??0)||p!=null&&(p<=0||p>100000))continue;
        state.wish[id]={name:String(row.name||id).slice(0,180),target:p};
      }
      persist();render();checkAlerts();
    }).catch(()=>alert("导入失败：请选择正确的愿望单 JSON 文件"));
  }
  function datasetFresh(g){
    const stamp=(g.category==="hot"?DATA.hotMeta?.updated_at_cn:DATA.meta?.updated_at_cn)||"";
    const parsed=Date.parse(stamp.replace(" ","T")+":00+08:00");
    return Number.isFinite(parsed)&&parsed<=Date.now()+300000&&Date.now()-parsed<=48*3600000;
  }
  function checkAlerts(){
    const panel=document.querySelector("#radar-alerts");
    if(!panel)return;
    const matches=[];
    for(const [id,item] of Object.entries(state.wish)){
      const g=find(id),target=Number(item?.target);
      if(!g||!item||item.target==null||!Number.isFinite(target)||!datasetFresh(g))continue;
      const steam=Number(g.price)>0&&Number(g.price)<=target;
      if(steam)matches.push({g,kind:"Steam",value:g.price});
      const k=minRef(g);
      if(k!=null&&k<=target)matches.push({g,kind:"散 Key 参考",value:k});
    }
    panel.replaceChildren();
    panel.hidden=matches.length===0;
    if(matches.length){
      const title=document.createElement("strong");title.textContent="目标价已达到（仅在打开页面时检查）";
      panel.append(title);
      for(const x of matches.slice(0,12)){
        const p=document.createElement("div");
        p.textContent=x.g.name+" · "+x.kind+" ¥"+Number(x.value).toFixed(2);
        panel.append(p);
      }
    }
  }
  function exportWishlist(){
    const rows=Object.entries(state.wish).map(([appid,entry])=>({appid:Number(appid),name:entry.name,target:entry.target}));
    const blob=new Blob([JSON.stringify({saved_at:new Date().toISOString(),games:rows},null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="game-radar-wishlist.json";a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function openHistory(id){
    const dialog=document.querySelector("#price-history-dialog");
    const g=find(id);
    document.querySelector("#history-title").textContent=(g?.name||id)+" · 价格走势";
    const node=document.querySelector("#history-chart");
    node.replaceChildren();
    const rows=(state.history[String(id)]||[]).filter(x=>x&&typeof x.price==="number"&&x.price>0);
    const note=document.querySelector("#history-note");
    if(!rows.length){note.textContent="暂无已保存的价格记录。仅展示 Game Radar 实际采集的价格，不代表 Steam 全历史最低。";dialog.showModal();return}
    note.textContent="价格来自 Game Radar 已采集的 Steam 国区/散 Key 参考记录；散 Key 非实时库存，历史数据可能不连续。";
    const width=720,height=230,pad=34;
    const values=rows.map(x=>x.price),min=Math.min(...values),max=Math.max(...values);
    const minY=Math.max(0,min-(max-min||1)*.1),maxY=max+(max-min||1)*.1;
    const dates=[...new Set(rows.map(r=>r.date))].sort();
    const x=date=>pad+dates.indexOf(date)*(width-2*pad)/Math.max(1,dates.length-1);
    const y=v=>height-pad-(v-minY)*(height-2*pad)/(maxY-minY);
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    svg.setAttribute("viewBox","0 0 "+width+" "+height);
    svg.setAttribute("role","img");svg.setAttribute("aria-label","按来源分别绘制的站内价格观察走势图");
    const sources=[...new Set(rows.map(r=>r.source||"未知来源"))];
    const palette=["#74f0b8","#f2c56c","#85b6ff","#d6a6ef","#f38f95"];
    sources.forEach((source,index)=>{
      const values=rows.filter(r=>(r.source||"未知来源")===source);
      if(!values.length)return;
      const line=document.createElementNS("http://www.w3.org/2000/svg","polyline");
      line.setAttribute("points",values.map(r=>x(r.date)+","+y(r.price)).join(" "));
      line.setAttribute("stroke",palette[index%palette.length]);
      line.setAttribute("fill","none");line.setAttribute("stroke-width","3");
      svg.appendChild(line);
      if(values.length===1){
        const circle=document.createElementNS("http://www.w3.org/2000/svg","circle");
        circle.setAttribute("cx",x(values[0].date));circle.setAttribute("cy",y(values[0].price));
        circle.setAttribute("r","5");circle.setAttribute("fill",palette[index%palette.length]);
        svg.appendChild(circle);
      }
    });
    node.appendChild(svg);
    const legend=document.createElement("div");legend.className="chart-legend";
    sources.forEach((source,index)=>{
      const tag=document.createElement("span");
      tag.style.color=palette[index%palette.length];tag.textContent="● "+source;
      legend.appendChild(tag);
    });
    node.appendChild(legend);
    const lower=document.createElement("p");lower.className="note";lower.textContent=
      "记录 "+rows.length+" 条 · 观测最低 ¥"+min.toFixed(2)+" · 最高 ¥"+max.toFixed(2)+
      " · 最近 "+rows.at(-1).date+" · 来源独立绘制，数据不连续";
    node.appendChild(lower);
    dialog.showModal();
  }
  function init(){
    const alerts=document.createElement("section");
    alerts.id="radar-alerts";alerts.className="radar-alerts wrap";alerts.hidden=true;
    document.querySelector("main")?.prepend(alerts);
    for(const id of ["sort-mode","max-price","min-rating","genre-filter"])
      document.getElementById(id)?.addEventListener("input",render);
    document.querySelector("#wishlist-filter")?.addEventListener("click",e=>{
      e.currentTarget.classList.toggle("active");render();
    });
    document.querySelector("#export-wishlist")?.addEventListener("click",exportWishlist);
    document.querySelector("#import-wishlist")?.addEventListener("click",()=>document.querySelector("#import-wishlist-file")?.click());
    document.querySelector("#import-wishlist-file")?.addEventListener("change",e=>{
      importWishlist(e.target.files?.[0]);e.target.value="";
    });
    document.querySelector("#close-history")?.addEventListener("click",()=>document.querySelector("#price-history-dialog").close());
    document.addEventListener("click",e=>{
      const b=e.target.closest("button[data-id]");
      if(!b)return;
      e.preventDefault();e.stopPropagation();
      const id=Number(b.dataset.id);
      if(b.classList.contains("radar-wish"))modify(id);
      else if(b.classList.contains("radar-target"))setTarget(id);
      else if(b.classList.contains("radar-history"))openHistory(id);
    });
    fetch("data/price_history.json?"+Date.now()).then(r=>r.ok?r.json():{}).then(v=>{state.history=v.games||{};state.historyLoaded=true}).catch(()=>{});
  }
  return {select,refreshGenres,cardActions,checkAlerts,renderOfflist,init};
})();
RadarExtras.init();

window.RadarExtras=RadarExtras;
