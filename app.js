let DATA={games:[],meta:{}};let filter="all";
const fmt=n=>n==null?"—":"¥"+Number(n).toFixed(n%1?2:0);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function card(g){
const cleanOffers=(g.key_offers||[]).filter(o=>o&&Number(o.price)>0&&!(o.platform==="SteamPY"&&Number(o.price)<=0.1)&&!(g.price>0&&Number(o.price)<Math.max(.5,g.price*.03)));
const offers=cleanOffers.length?cleanOffers.map(o=>`<div class="key-offer"><div class="key-source">${esc(o.platform)} <span class="key-type">${o.kind==="historical_listing"?"历史挂售":"接口参考"}</span></div><div class="key-price">${fmt(o.price)}</div><div class="key-caution">${esc(o.kind==="historical_listing"?"非当前在售价格":"库存、激活区和版本需核实")}</div></div>`).join(""):`<div class="key-unavailable">暂无可靠散 Key 报价</div>`;
const genres=(g.genres||[]).filter(Boolean);
const negative=g.negative_review_analysis;
const topics=negative?.categories||[];
const insight=`<div class="review-reasons"><div class="detail-label">差评主要原因</div><div class="review-summary">${negative?.sample_size>=3&&topics.length?topics.slice(0,3).map(x=>`<span class="review-topic">${esc(x.name)} <b>${Number(x.mentions)||0}</b>条提及</span>`).join(""):`<span class="review-unknown">暂无足够评论样本，尚不能判断主要差评原因</span>`}</div><div class="review-caution">简中近期差评样本：${negative?.sample_size??0} 条 · 关键词归类仅供参考，不代表全部玩家</div></div>`;
return `<article class="card"><a href="${esc(g.url)}" target="_blank" rel="noopener noreferrer">
<div class="cover" style="background-image:url('${esc(g.image||"")}')"></div>
<div class="body"><div class="top"><div><div class="title">${esc(g.name)}</div>${g.name_en?`<div class="meta">${esc(g.name_en)}</div>`:""}</div><div class="score">${g.category==="explore"?(g.discovery_score??"—"):(g.recommend_score??"—")}</div></div>
<div class="meta"><strong>游戏类型：</strong>${genres.length?esc(genres.join(" / ")):"未分类"}</div>
<div class="meta">发行日期：${esc(g.release_date||"未知")}${g.coming_soon?"（尚未发售）":""} · ${esc(g.review||"Steam")}</div>
<span class="price">${g.price>0?fmt(g.price):"价格待核实"}</span>${g.original_price!==g.price?`<span class="old">${fmt(g.original_price)}</span>`:""}${g.discount?`<span class="discount">-${g.discount}%</span>`:""}
<div class="tags">${(g.tags||[]).map(t=>`<span class="tag ${t==="站内新低"?"hot":""}">${esc(t)}</span>`).join("")}</div>
<div class="why">${esc(g.why||"")}${g.watchlisted?" · ★ 关注游戏":""}</div>${insight}
<div class="meta" style="margin-top:8px">📱 手机版：${g.mobile?`Android ${esc(g.mobile.android||"待核实")} / iOS ${esc(g.mobile.ios||"待核实")}`:"未核实"} · 🎁 Epic：${esc(g.epic_status||"未核实")}</div>
<div class="key-panel"><div class="detail-label">散 Key 价格 <span class="key-info">影响购买决策 · 报价需核实</span></div><div class="key-offers">${offers}</div></div>
<div class="meta">Steam全历史最低：${g.steam_historical_low!=null?fmt(g.steam_historical_low):"暂不可核实"} · SteamRaw覆盖期最低：${g.region_history_low?.price!=null?fmt(g.region_history_low.price):"待核实"} · 站内最低：${fmt(g.tracked_low)} · Steam Deck：${esc(g.steam_deck||"待核实")}</div>
<div class="meta">${g.category==="explore"?"尝鲜分 "+(g.discovery_score??"—")+" · 不计算个人口味":"口味 "+(g.taste_score??"—")+" · 质量 "+(g.quality_score??"—")+" · 价格 "+(g.price_score??"—")}</div>
</div></a></article>`;
}
function render(){
const q=(document.querySelector("#search")?.value||"").trim().toLowerCase();
const all=DATA.games||[];
const search=g=>!q||[g.name,g.name_en,...(g.genres||[])].some(v=>String(v||"").toLowerCase().includes(q));
for(const category of ["deal","new","explore"]){
const section=document.querySelector("#"+category+"-section");
const elem=document.querySelector("#"+category+"-games");
const items=all.filter(g=>(g.category||((g.flags||[]).includes("new")?"new":"deal"))===category).filter(search).filter(g=>filter!=="mobile"||(g.flags||[]).includes("mobile"));
const visible=filter==="all"||filter==="mobile"||filter===category;
section.hidden=!visible;
elem.innerHTML=items.length?items.map(card).join(""):`<div class="note">本期暂无符合条件的${category==="deal"?"老游戏折扣":category==="new"?"近期新游戏":"低价高评游戏"}。</div>`;
document.querySelector("#"+category+"-count").textContent="（"+items.length+"/"+(category==="explore"?20:30)+"）";
}
}
function boot(d){
DATA={games:d.games||[],meta:d.meta||{}};
document.querySelector("#updated").textContent="更新："+(DATA.meta.updated_at_cn||"—");
const gs=DATA.games;
document.querySelector("#stats").innerHTML=[
["今日候选",gs.length],["老游戏折扣",gs.filter(x=>x.category==="deal"||(!x.category&&x.flags?.includes("deal"))).length],
["近期新游",gs.filter(x=>x.category==="new"||(!x.category&&x.flags?.includes("new"))).length],
["尝鲜发现",gs.filter(x=>x.category==="explore").length]
].map(x=>`<div class="stat"><b>${x[1]}</b><span>${x[0]}</span></div>`).join("");
render();
}
document.querySelectorAll("[data-filter]").forEach(b=>b.onclick=()=>{
document.querySelectorAll("[data-filter]").forEach(x=>x.classList.remove("active"));
b.classList.add("active");filter=b.dataset.filter;render();
});
document.querySelector("#search").oninput=render;
fetch("data/games.json?"+Date.now()).then(r=>{if(!r.ok)throw Error("data fetch failed");return r.json()}).then(boot).catch(()=>boot({meta:{updated_at_cn:"暂无数据"},games:[]}));
