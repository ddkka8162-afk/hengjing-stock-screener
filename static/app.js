const state={page:1,pageSize:20,sort:"score",order:"desc",total:0,lastQuery:""};
let screenTimer;
let screenController;
const watchlist=new Set(loadWatchlist());
const fields=["keyword","min_market_cap","max_market_cap","min_pe","max_pe","min_roe","max_debt_ratio","min_revenue_growth","min_profit_growth","min_turnover_rate","min_score"];
const $=id=>document.getElementById(id);
const fmt=(n,d=2)=>Number(n).toLocaleString("zh-CN",{minimumFractionDigits:d,maximumFractionDigits:d});
const templates={
  hotStocks:{min_turnover_rate:1},
  growth:{min_roe:12,min_revenue_growth:15,min_profit_growth:15,max_debt_ratio:65},
  momentum:{min_turnover_rate:1,min_score:50},
  balanced:{min_roe:10,max_pe:35,max_debt_ratio:70,min_score:60}
};

async function init(){
  const meta=await fetch("/api/meta").then(r=>r.json());
  $("universeCount").textContent=meta.count;
  $("industryList").innerHTML=meta.sectors.map((sector,index)=>`<label title="20日 ${sector.momentum_20d}% · 120日 ${sector.momentum_120d}%">
    <input type="checkbox" value="${sector.name}"><span><strong>${index+1}. ${sector.name}</strong>${sector.is_hot?'<em>热</em>':''}<small>${sector.heat>=0?'+':''}${sector.heat}</small></span>
  </label>`).join("");
  $("sectorMethod").textContent=meta.sector_ranking_basis;
  restore();$("topKeyword").value=$("keyword").value;bind();await Promise.all([screen(),refreshMarket(),refreshSectors(),refreshWatchlist()]);
  setInterval(refreshMarket,5000);
  setInterval(refreshSectors,30000);
}

async function refreshSectors(){
  try{
    const data=await fetch("/api/sector-rankings",{cache:"no-store"}).then(r=>r.json());
    $("conceptRanking").innerHTML=renderSectorRanking(data.concepts);
    $("industryRanking").innerHTML=renderSectorRanking(data.industries);
    $("sectorUpdatedAt").textContent=new Date(data.updated_at).toLocaleTimeString("zh-CN",{hour12:false});
  }catch(e){console.warn("板块排行刷新失败",e)}
}

function renderSectorRanking(items){
  return items.map((sector,index)=>`<li>
    <b>${index+1}</b><div><strong>${sector.name}</strong><small>${sector.stock_count}只 · 领涨 ${sector.leader_name}</small></div>
    <span class="${sector.change_pct>=0?'up':'down'}">${sector.change_pct>=0?'+':''}${fmt(sector.change_pct)}%</span>
  </li>`).join("");
}

async function refreshMarket(){
  try{
    const data=await fetch("/api/market-overview",{cache:"no-store"}).then(r=>r.json());
    $("indexGrid").innerHTML=data.items.map(renderIndexCard).join("");
    $("marketUpdatedAt").textContent=new Date(data.updated_at).toLocaleTimeString("zh-CN",{hour12:false});
    $("tickerUpdatedAt").textContent=new Date(data.updated_at).toLocaleTimeString("zh-CN",{hour12:false});
    $("marketTicker").innerHTML=data.items.map(index=>`<div class="ticker-item"><strong>${index.name}</strong><div><b>${fmt(index.value,2)}</b><span class="${index.change_pct>=0?'up':'down'}">${index.change_pct>=0?'+':''}${fmt(index.change_pct)}%</span></div></div>`).join("");
  }catch(e){console.warn("大盘行情刷新失败",e)}
}

function renderIndexCard(index){
  const values=index.points.map(p=>p.value),min=Math.min(...values),max=Math.max(...values),range=max-min||1;
  const coords=values.map((v,i)=>`${(i/(values.length-1)*340).toFixed(1)},${(82-(v-min)/range*68).toFixed(1)}`);
  const line=coords.join(" "),area=`0,88 ${line} 340,88`,direction=index.change_pct>=0?"up":"down",color=index.change_pct>=0?"#d96d63":"#59a98b";
  return `<article class="index-card">
    <div class="index-top"><div class="index-name"><strong>${index.name}</strong><small>${index.code}</small></div>
    <div class="index-value"><b>${fmt(index.value,2)}</b><span class="${direction}">${index.change>=0?'+':''}${fmt(index.change)} &nbsp; ${index.change_pct>=0?'+':''}${fmt(index.change_pct)}%</span></div></div>
    <svg class="index-chart" viewBox="0 0 340 92" preserveAspectRatio="none" aria-label="${index.name}最近60分钟走势">
      <line class="grid-line" x1="0" y1="48" x2="340" y2="48"></line><polygon class="area" points="${area}" fill="${color}"></polygon><polyline class="trend" points="${line}" stroke="${color}"></polyline>
    </svg><div class="chart-foot"><span>${index.points[0].time}</span><span>近 60 分钟</span><span>${index.points.at(-1).time}</span></div>
  </article>`;
}

function bind(){
  $("resetFilters").onclick=()=>{fields.forEach(x=>$(x).value="");$("topKeyword").value="";document.querySelectorAll("#industryList input").forEach(x=>x.checked=false);$("exclude_st").checked=$("exclude_suspended").checked=true;document.querySelectorAll(".templates button").forEach(x=>x.classList.remove("active"));state.page=1;screen()};
  $("prevPage").onclick=()=>{if(state.page>1){state.page--;screen()}};
  $("nextPage").onclick=()=>{if(state.page*state.pageSize<state.total){state.page++;screen()}};
  $("exportCsv").onclick=()=>{const q=new URLSearchParams(state.lastQuery);q.set("page","1");q.set("page_size","5000");location.href="/api/export.csv?"+q};
  $("saveStrategy").onclick=()=>{localStorage.setItem("hengjing-strategy",JSON.stringify(readForm()));toast("筛选条件已保存在此浏览器")};
  document.querySelectorAll("[data-template]").forEach(btn=>btn.onclick=()=>applyTemplate(btn));
  document.querySelectorAll("th[data-sort]").forEach(th=>th.onclick=()=>{const key=th.dataset.sort;state.order=state.sort===key&&state.order==="desc"?"asc":"desc";state.sort=key;state.page=1;screen()});
  document.querySelector(".filters").addEventListener("input",event=>{
    if(!(event.target instanceof HTMLInputElement))return;
    if(event.target.id==="keyword")$("topKeyword").value=event.target.value;
    state.page=1;
    scheduleScreen(event.target.type==="checkbox"?0:350);
  });
  $("topKeyword").addEventListener("input",event=>{
    $("keyword").value=event.target.value;
    state.page=1;
    scheduleScreen(350);
  });
  $("topKeyword").addEventListener("keydown",event=>{if(event.key==="Enter"){event.preventDefault();scheduleScreen(0)}});
  document.querySelectorAll("[data-scroll]").forEach(button=>button.addEventListener("click",()=>$(button.dataset.scroll).scrollIntoView({behavior:"smooth",block:"start"})));
  $("stockRows").addEventListener("click",event=>{const button=event.target.closest("[data-favorite]");if(button)toggleFavorite(button.dataset.favorite)});
  $("watchlistRows").addEventListener("click",event=>{const button=event.target.closest("[data-remove]");if(button)toggleFavorite(button.dataset.remove)});
  $("keyword").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();scheduleScreen(0)}});
}

function scheduleScreen(delay=350){
  clearTimeout(screenTimer);
  screenTimer=setTimeout(screen,delay);
}

function readForm(){
  const data={}; fields.forEach(id=>{if($(id).value.trim())data[id]=$(id).value.trim()});
  data.industries=[...document.querySelectorAll("#industryList input:checked")].map(x=>x.value);
  data.exclude_st=$("exclude_st").checked;data.exclude_suspended=$("exclude_suspended").checked;
  return data;
}

function queryString(){
  const data=readForm(),q=new URLSearchParams();
  Object.entries(data).forEach(([k,v])=>{if(Array.isArray(v)){if(v.length)q.set(k,v.join(","))}else q.set(k,v)});
  q.set("page",state.page);q.set("page_size",state.pageSize);q.set("sort",state.sort);q.set("order",state.order);
  return q.toString();
}

async function screen(){
  if(screenController)screenController.abort();
  screenController=new AbortController();
  const body=$("stockRows");body.innerHTML='<tr><td colspan="11" class="loading">正在计算筛选结果…</td></tr>';
  state.lastQuery=queryString();renderChips();
  try{
    const res=await fetch("/api/screen?"+state.lastQuery,{signal:screenController.signal}),data=await res.json();
    if(!res.ok)throw new Error(data.error||"筛选失败");
    state.total=data.total;renderRows(data.items);$("resultCount").textContent=data.total;$("updatedAt").textContent=new Date(data.updated_at).toLocaleString("zh-CN");
    const pages=Math.max(1,Math.ceil(data.total/state.pageSize));$("pageInfo").textContent=`第 ${state.page} / ${pages} 页`;
    $("prevPage").disabled=state.page===1;$("nextPage").disabled=state.page>=pages;updateConditionCount();
  }catch(e){if(e.name!=="AbortError")body.innerHTML=`<tr><td colspan="11" class="loading">${escapeHtml(e.message)}</td></tr>`}
}

function renderRows(rows){
  $("stockRows").innerHTML=rows.length?rows.map(s=>`<tr>
    <td><div class="stock"><i>${s.name.slice(0,1)}</i><strong>${s.name}</strong><small>${s.code} · ${s.industry}</small></div></td>
    <td>${fmt(s.price)}</td><td class="${s.change_pct>=0?'up':'down'}">${s.change_pct>=0?'+':''}${fmt(s.change_pct)}%</td>
    <td>${fmt(s.market_cap,0)}亿</td><td>${fmt(s.pe_ttm)}</td><td>${fmt(s.roe_ttm)}%</td>
    <td class="${s.revenue_growth>=0?'up':'down'}">${fmt(s.revenue_growth)}%</td><td>${fmt(s.debt_ratio)}%</td><td><span class="heat-score">${fmt(s.heat_score,1)}</span></td><td><span class="score">${fmt(s.score,1)}</span></td>
    <td><button class="favorite-button ${watchlist.has(s.code)?'selected':''}" data-favorite="${s.code}" title="${watchlist.has(s.code)?'移出自选':'加入自选'}">${watchlist.has(s.code)?'★':'☆'}</button></td>
  </tr>`).join(""):'<tr><td colspan="11" class="loading">没有符合当前条件的股票。试着放宽一点，市场有时也需要喘口气。</td></tr>';
}

function loadWatchlist(){
  try{const value=JSON.parse(localStorage.getItem("hengjing-watchlist")||"[]");return Array.isArray(value)?value.filter(code=>/^\d{6}$/.test(code)):[]}catch{return []}
}

function toggleFavorite(code){
  if(watchlist.has(code)){watchlist.delete(code);toast("已移出自选")}else{watchlist.add(code);toast("已加入自选")}
  localStorage.setItem("hengjing-watchlist",JSON.stringify([...watchlist]));
  document.querySelectorAll(`[data-favorite="${code}"]`).forEach(button=>{const selected=watchlist.has(code);button.classList.toggle("selected",selected);button.textContent=selected?'★':'☆';button.title=selected?'移出自选':'加入自选'});
  refreshWatchlist();
}

async function refreshWatchlist(){
  $("watchlistCount").textContent=watchlist.size;
  if(!watchlist.size){$("watchlistRows").innerHTML='<div class="watchlist-empty">点击股票后的星标，将股票加入自选</div>';return}
  try{
    const query=new URLSearchParams({codes:[...watchlist].join(",")});
    const data=await fetch("/api/watchlist?"+query,{cache:"no-store"}).then(r=>r.json());
    $("watchlistRows").innerHTML=data.items.map((stock,index)=>`<div class="watchlist-row">
      <b>${index+1}</b><div><strong>${stock.name}</strong><small>${stock.code} · ${fmt(stock.price)}</small></div>
      <span class="${stock.change_pct>=0?'up':'down'}">${stock.change_pct>=0?'+':''}${fmt(stock.change_pct)}%</span>
      <button data-remove="${stock.code}" title="移出自选">×</button>
    </div>`).join("");
  }catch(e){$("watchlistRows").innerHTML='<div class="watchlist-empty">自选数据加载失败</div>'}
}

function renderChips(){
  const d=readForm(),labels={min_market_cap:"市值 ≥",max_market_cap:"市值 ≤",min_pe:"PE ≥",max_pe:"PE ≤",min_roe:"ROE ≥",max_debt_ratio:"负债率 ≤",min_revenue_growth:"营收增长 ≥",min_profit_growth:"利润增长 ≥",min_turnover_rate:"换手率 ≥",min_score:"综合分 ≥"};
  const chips=[];if(d.keyword)chips.push(`搜索：${d.keyword}`);if(d.industries.length)chips.push(d.industries.join(" · "));
  Object.entries(labels).forEach(([k,v])=>{if(d[k])chips.push(`${v} ${d[k]}`)});if(d.exclude_st)chips.push("剔除 ST");if(d.exclude_suspended)chips.push("剔除停牌");
  $("activeChips").innerHTML=chips.map(x=>`<span>${escapeHtml(x)}</span>`).join("");
}

function applyTemplate(btn){
  fields.filter(x=>x!=="keyword").forEach(x=>$(x).value="");const values=templates[btn.dataset.template];Object.entries(values).forEach(([k,v])=>{if($(k))$(k).value=v});
  state.sort=btn.dataset.template==="hotStocks"?"heat_score":"score";state.order="desc";
  document.querySelectorAll(".templates button").forEach(x=>x.classList.toggle("active",x===btn));state.page=1;screen();
}

function restore(){
  try{const d=JSON.parse(localStorage.getItem("hengjing-strategy"));if(!d)return;fields.forEach(x=>{if(d[x]!==undefined)$(x).value=d[x]});$("exclude_st").checked=d.exclude_st!==false;$("exclude_suspended").checked=d.exclude_suspended!==false;setTimeout(()=>document.querySelectorAll("#industryList input").forEach(x=>x.checked=(d.industries||[]).includes(x.value)))}catch{}
}
function updateConditionCount(){const d=readForm();const n=Object.entries(d).filter(([k,v])=>Array.isArray(v)?v.length:(k.startsWith("exclude_")?v:String(v||"").length)).length;$("conditionCount").textContent=`${n} 个条件已启用`}
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2200)}
function escapeHtml(s){return String(s).replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]))}
init().catch(e=>toast(e.message));

