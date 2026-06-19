const cryptoState={items:[],sort:"market_cap",order:"desc",query:"",category:"all"};
const cryptoFavorites=new Set(loadStored("hengjing-crypto-watchlist",[]));
const stableCoins=new Set(["tether","usd-coin"]);
const $=id=>document.getElementById(id);
const compact=new Intl.NumberFormat("zh-CN",{notation:"compact",maximumFractionDigits:2});
const money=n=>n==null?"—":Number(n).toLocaleString("en-US",{style:"currency",currency:"USD",minimumFractionDigits:n<1?4:2,maximumFractionDigits:n<1?6:2});
const pct=n=>n==null?"—":`${n>=0?'+':''}${Number(n).toFixed(2)}%`;

async function loadCrypto(){
  $("refreshCrypto").disabled=true;
  try{
    const response=await fetch("/api/crypto-markets",{cache:"no-store"}),data=await response.json();
    if(!response.ok)throw new Error(data.error||"行情请求失败");
    cryptoState.items=data.items;renderSummary(data);renderCrypto();checkAlerts();
  }catch(error){$("cryptoRows").innerHTML=`<tr><td colspan="10" class="crypto-loading">${escapeHtml(error.message)}</td></tr>`}
  finally{$("refreshCrypto").disabled=false}
}

function renderSummary(data){
  $("cryptoMarketCap").textContent="$"+compact.format(data.summary.market_cap);$("cryptoVolume").textContent="$"+compact.format(data.summary.volume_24h);
  $("cryptoUp").textContent=data.summary.advancers;$("cryptoDown").textContent=data.summary.decliners;$("cryptoUpdatedAt").textContent=new Date(data.updated_at).toLocaleTimeString("zh-CN",{hour12:false});
  $("cryptoSource").textContent=data.data_mode==="live"?`实时源：${data.source}`:"演示行情（实时源不可用）";$("cryptoMode").textContent=data.data_mode==="live"?"实时行情已连接":"演示行情 · 实时源不可用";
  document.querySelector(".crypto-live").className=`crypto-live ${data.data_mode}`;
}

function visibleItems(){
  const q=cryptoState.query.toLowerCase();
  return cryptoState.items.filter(coin=>{
    const matches=coin.name.toLowerCase().includes(q)||coin.symbol.toLowerCase().includes(q);
    if(!matches)return false;if(cryptoState.category==="major")return coin.market_cap_rank<=8&&!stableCoins.has(coin.id);
    if(cryptoState.category==="stable")return stableCoins.has(coin.id);if(cryptoState.category==="favorite")return cryptoFavorites.has(coin.id);return true;
  }).sort((a,b)=>{const av=a[cryptoState.sort]??-Infinity,bv=b[cryptoState.sort]??-Infinity,d=typeof av==="string"?av.localeCompare(bv):av-bv;return cryptoState.order==="asc"?d:-d});
}

function renderCrypto(){
  const items=visibleItems();$("cryptoCount").textContent=`${items.length} 个币种`;$("allCoinCount").textContent=cryptoState.items.length;$("favoriteCoinCount").textContent=cryptoFavorites.size;
  $("cryptoLeaders").innerHTML=cryptoState.items.slice(0,3).map(coin=>`<article class="crypto-leader" data-open-coin="${coin.id}"><span class="coin-icon">${coin.symbol.slice(0,2)}</span><div><strong>${coin.name}</strong><small>${coin.symbol} · 市值 #${coin.market_cap_rank}</small></div><aside><b>${money(coin.price)}</b><span class="${coin.change_24h>=0?'up':'down'}">${pct(coin.change_24h)}</span></aside></article>`).join("");
  $("cryptoRows").innerHTML=items.length?items.map((coin,index)=>`<tr data-open-coin="${coin.id}" tabindex="0"><td>${index+1}</td><td><div class="crypto-coin"><span class="coin-icon">${coin.symbol.slice(0,2)}</span><strong>${coin.name}</strong><small>${coin.symbol}</small></div></td><td><strong>${money(coin.price)}</strong></td><td class="${coin.change_1h>=0?'up':'down'}">${pct(coin.change_1h)}</td><td class="${coin.change_24h>=0?'up':'down'}">${pct(coin.change_24h)}</td><td class="${coin.change_7d>=0?'up':'down'}">${pct(coin.change_7d)}</td><td>$${compact.format(coin.market_cap)}</td><td>$${compact.format(coin.volume_24h)}</td><td>${sparkline(coin.sparkline,coin.change_7d>=0)}</td><td><div class="coin-actions"><button data-favorite-coin="${coin.id}" title="收藏">${cryptoFavorites.has(coin.id)?'★':'☆'}</button><a href="/crypto-detail.html?id=${encodeURIComponent(coin.id)}">行情</a></div></td></tr>`).join(""):'<tr><td colspan="10" class="crypto-loading">当前分类暂无币种</td></tr>';
  renderMovers();
}

function renderMovers(){
  const sorted=[...cryptoState.items].sort((a,b)=>b.change_24h-a.change_24h);
  $("cryptoGainers").innerHTML=sorted.slice(0,5).map(moverRow).join("");$("cryptoLosers").innerHTML=sorted.slice(-5).reverse().map(moverRow).join("");
}
function moverRow(coin){return `<li data-open-coin="${coin.id}"><span>${coin.symbol}</span><strong>${money(coin.price)}</strong><b class="${coin.change_24h>=0?'up':'down'}">${pct(coin.change_24h)}</b></li>`}
function sparkline(values,positive){if(!values?.length)return "—";const step=Math.max(1,Math.floor(values.length/48)),sample=values.filter((_,i)=>i%step===0),min=Math.min(...sample),max=Math.max(...sample),range=max-min||1,points=sample.map((v,i)=>`${(i/(sample.length-1)*130).toFixed(1)},${(31-(v-min)/range*27).toFixed(1)}`).join(" ");return `<svg class="spark" viewBox="0 0 130 34" preserveAspectRatio="none"><polyline points="${points}" stroke="${positive?'#2fc58d':'#f0645d'}"></polyline></svg>`}

function toggleFavorite(id){cryptoFavorites.has(id)?cryptoFavorites.delete(id):cryptoFavorites.add(id);localStorage.setItem("hengjing-crypto-watchlist",JSON.stringify([...cryptoFavorites]));renderCrypto();toast(cryptoFavorites.has(id)?"已加入虚拟币收藏":"已取消收藏")}
function openCoin(id){location.href=`/crypto-detail.html?id=${encodeURIComponent(id)}`}
function loadStored(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback))}catch{return fallback}}
function checkAlerts(){const alerts=loadStored("hengjing-crypto-alerts",{});for(const coin of cryptoState.items){const target=Number(alerts[coin.id]);if(target&&coin.price>=target&&!sessionStorage.getItem(`alerted-${coin.id}`)){sessionStorage.setItem(`alerted-${coin.id}`,"1");toast(`${coin.symbol} 已达到提醒价 ${money(target)}`)}}}
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2200)}
function escapeHtml(value){return String(value).replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]))}

$("refreshCrypto").onclick=loadCrypto;$("cryptoSearch").oninput=e=>{cryptoState.query=e.target.value;renderCrypto()};
document.querySelectorAll("[data-crypto-sort]").forEach(th=>th.onclick=()=>{const key=th.dataset.cryptoSort;cryptoState.order=cryptoState.sort===key&&cryptoState.order==="desc"?"asc":"desc";cryptoState.sort=key;renderCrypto()});
document.querySelectorAll("[data-crypto-category]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-crypto-category]").forEach(x=>x.classList.toggle("active",x===button));cryptoState.category=button.dataset.cryptoCategory;renderCrypto()});
document.body.addEventListener("click",event=>{const favorite=event.target.closest("[data-favorite-coin]");if(favorite){event.preventDefault();event.stopPropagation();toggleFavorite(favorite.dataset.favoriteCoin);return}const open=event.target.closest("[data-open-coin]");if(open&&!event.target.closest("a,button"))openCoin(open.dataset.openCoin)});
document.body.addEventListener("keydown",event=>{const row=event.target.closest("tr[data-open-coin]");if(row&&(event.key==="Enter"||event.key===" ")){event.preventDefault();openCoin(row.dataset.openCoin)}});
loadCrypto();setInterval(loadCrypto,15000);

