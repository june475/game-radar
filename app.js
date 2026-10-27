let DATA={games:[],meta:{}};let filter="all";
const fmt=n=>n==null?"—":"¥"+Number(n).toFixed(n%1?2:0);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function card(g){
const offers=(g.key_offers||[]).map(o=>esc(o.platform)+" "+fmt(o.price)+"（"+esc(o.status)+"）").join(" / ")||"待核实";
const genres=(g.genres||[]).filter(Boolean);
return `<article class="card"><a href="${esc(g.url)}" target="_blank" rel="noopener noreferrer">
<div class="cover" style="background-image:url('${esc(g.image||"")}')"></div>
<div class="body"><div class="top"><div><div class="title">${esc(g.name)}</div>${g.name_en?`<div class="meta">${esc(g.name_en)}</div>`:""}</div><div class="score">${g.recommend_score??"—"}</div></div>
<div class="meta"><strong>游戏类型：</strong>${genres.length?esc(genres.join(" / ")):"未分类"}</div>
<div class="meta">发行日期：${esc(g.release_date||"未知")}${g.coming_soon?"（尚未发售）":""} · ${esc(g.review||"Steam")}</div>
<span class="price">${fmt(g.price)}</span>${g.original_price!==g.price?`<span class="old">${fmt(g.original_price)}</span>`:""}${g.discount?`<span class="discount">-${g.discount}%</span>`:""}
<div class="tags">${(g.tags||[]).map(t=>`<span class="tag ${t==="站内新低"?"hot":""}">${esc(t)}</span>`).join("")}</div>
<div class="why">${esc(g.why||"")}</div>
<div class="meta" style="margin-top:8px">📱 手机版：${g.mobile?`Android ${esc(g.mobile.android||"待核实")} / iOS ${esc(g.mobile.ios||"待核实")}`:"未核实"} · 🎁 Epic：${esc(g.epic_status||"未核实")}</div>
<div class="meta">散Key：${offers}</div>
<div class="meta">Steam全历史最低：${g.steam_historical_low!=null?fmt(g.steam_historical_low):"暂不可核实"} · SteamRaw覆盖期最低：${g.region_history_low?.price!=null?fmt(g.region_history_low.price):"待核实"} · 站内最低：${fmt(g.tracked_low)} · Steam Deck：${esc(g.steam_deck||"待核实")}</div>
<div class="meta">口味 ${g.taste_score??"—"} · 质量 ${g.quality_score??"—"} · 价格 ${g.price_score??"—"}</div>
</div></a></article>`;
}
function render(){
const q=(document.querySelector("#search")?.value||"").trim().toLowerCase();
const all=DATA.games||[];
const search=g=>!q||[g.name,g.name_en,...(g.genres||[])].some(v=>String(v||"").toLowerCase().includes(q));
for(const category of ["deal","new"]){
const section=document.querySelector("#"+category+"-section");
const elem=document.querySelector("#"+category+"-games");
const items=all.filter(g=>(g.category||((g.flags||[]).includes("new")?"new":"deal"))===category).filter(search).filter(g=>filter!=="mobile"||(g.flags||[]).includes("mobile"));
const visible=filter==="all"||filter==="mobile"||filter===category;
section.hidden=!visible;
elem.innerHTML=items.length?items.map(card).join(""):`<div class="note">本期暂无符合条件的${category==="deal"?"老游戏折扣":"近期新游戏"}。</div>`;
document.querySelector("#"+category+"-count").textContent="（"+items.length+"/30）";
}
}
function boot(d){
DATA={games:d.games||[],meta:d.meta||{}};
document.querySelector("#updated").textContent="更新："+(DATA.meta.updated_at_cn||"—");
const gs=DATA.games;
document.querySelector("#stats").innerHTML=[
["今日候选",gs.length],["老游戏折扣",gs.filter(x=>x.category==="deal"||(!x.category&&x.flags?.includes("deal"))).length],
["近期新游",gs.filter(x=>x.category==="new"||(!x.category&&x.flags?.includes("new"))).length],
["手机移植",gs.filter(x=>x.flags?.includes("mobile")).length]
].map(x=>`<div class="stat"><b>${x[1]}</b><span>${x[0]}</span></div>`).join("");
render();
}
document.querySelectorAll("[data-filter]").forEach(b=>b.onclick=()=>{
document.querySelectorAll("[data-filter]").forEach(x=>x.classList.remove("active"));
b.classList.add("active");filter=b.dataset.filter;render();
});
document.querySelector("#search").oninput=render;
fetch("data/games.json?"+Date.now()).then(r=>{if(!r.ok)throw Error("data fetch failed");return r.json()}).then(boot).catch(()=>boot({meta:{updated_at_cn:"暂无数据"},games:[]}));
