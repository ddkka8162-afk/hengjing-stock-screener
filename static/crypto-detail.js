const $=id=>document.getElementById(id),coinId=new URLSearchParams(location.search).get("id")||"bitcoin";
const favorites=new Set(loadStored("hengjing-crypto-watchlist",[]));let allCoins=[],coin=null,interval="1h",historyPoints=[],historyRequest=0,historyController;
const compact=new Intl.NumberFormat("zh-CN",{notation:"compact",maximumFractionDigits:2});
const money=n=>n==null?"—":Number(n).toLocaleString("en-US",{style:"currency",currency:"USD",minimumFractionDigits:n<1?4:2,maximumFractionDigits:n<1?6:2});
const pct=n=>n==null?"—":`${n>=0?'+':''}${Number(n).toFixed(2)}%`;

async function loadDetail(){
  try{const response=await fetch("/api/crypto-markets",{cache:"no-store"}),data=await response.json();if(!response.ok)throw new Error(data.error||"行情加载失败");allCoins=data.items;coin=allCoins.find(x=>x.id===coinId);if(!coin)throw new Error("未找到该币种");renderList();renderDetail(data);}
  catch(error){$("detailName").textContent=error.message}
}
function renderList(){const q=$("detailSearch").value.toLowerCase();$("detailCoinList").innerHTML=allCoins.filter(x=>x.name.toLowerCase().includes(q)||x.symbol.toLowerCase().includes(q)).map(x=>`<a class="${x.id===coinId?'active':''}" href="/crypto-detail.html?id=${encodeURIComponent(x.id)}"><span class="coin-icon">${x.symbol.slice(0,2)}</span><div><strong>${x.symbol}</strong><small>${money(x.price)}</small></div><b class="${x.change_24h>=0?'up':'down'}">${pct(x.change_24h)}</b></a>`).join("")}
function renderDetail(data){
  document.title=`${coin.name} (${coin.symbol}) 行情 · 衡镜`;$("detailIcon").textContent=coin.symbol.slice(0,2);$("detailName").textContent=coin.name;$("detailSymbol").textContent=coin.symbol;$("detailRank").textContent=`市值排名 #${coin.market_cap_rank}`;$("detailPrice").textContent=money(coin.price);
  setPerformance("detailChange",coin.change_24h);$("detailHigh").textContent=money(coin.high_24h);$("detailLow").textContent=money(coin.low_24h);$("detailVolume").textContent="$"+compact.format(coin.volume_24h);$("detailCap").textContent="$"+compact.format(coin.market_cap);setPerformance("detail1h",coin.change_1h);setPerformance("detail7d",coin.change_7d);setPerformance("side1h",coin.change_1h);setPerformance("side24h",coin.change_24h);setPerformance("side7d",coin.change_7d);
  $("detailRangeLow").textContent=money(coin.low_24h);$("detailRangeHigh").textContent=money(coin.high_24h);const pos=Math.max(0,Math.min(100,(coin.price-coin.low_24h)/(coin.high_24h-coin.low_24h||1)*100));$("detailRangeBar").style.width=`${pos}%`;
  $("detailMode").textContent=data.data_mode==="live"?"实时行情已连接":"演示行情";$("detailSource").textContent=data.data_mode==="live"?`数据源：${data.source}`:"演示行情 · 实时源不可用";document.querySelector(".crypto-live").className=`crypto-live ${data.data_mode}`;renderFavorite();loadHistory();checkDetailAlert();
}
async function loadHistory(){
  const request=++historyRequest;if(historyController)historyController.abort();historyController=new AbortController();$("detailChartSource").textContent="加载中";
  try{const query=new URLSearchParams({id:coinId,interval}),response=await fetch("/api/crypto-history?"+query,{cache:"no-store",signal:historyController.signal}),data=await response.json();if(!response.ok)throw new Error(data.error||"K线加载失败");if(request!==historyRequest)return;historyPoints=data.points;$("detailChartSource").textContent=data.data_mode==="live"?`${data.source} 实时K线`:"演示K线";renderChart();}
  catch(error){if(error.name!=="AbortError"&&request===historyRequest)$("detailChartSource").textContent=error.message}
}
function renderChart(){if(!historyPoints.length)return;const values=historyPoints.map(point=>point.value),min=Math.min(...values),max=Math.max(...values),gap=max-min||1,points=values.map((v,i)=>`${(i/(values.length-1)*900).toFixed(1)},${(345-(v-min)/gap*310).toFixed(1)}`);$("detailChartLine").setAttribute("points",points.join(" "));$("detailChartArea").setAttribute("points",`0,370 ${points.join(" ")} 900,370`);$("detailChartLine").setAttribute("stroke",values.at(-1)>=values[0]?"#2fc58d":"#f0645d");$("detailChartHigh").textContent=`高 ${money(max)}`;$("detailChartLow").textContent=`低 ${money(min)}`;$("detailRangeLabel").textContent=({"5m":"5分钟K线","15m":"15分钟K线","1h":"1小时K线","4h":"4小时K线","1d":"日K线","1w":"周K线"})[interval];const formatTime=timestamp=>new Date(timestamp).toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});$("chartStart").textContent=formatTime(historyPoints[0].time);$("chartMiddle").textContent=formatTime(historyPoints[Math.floor(historyPoints.length/2)].time);$("chartEnd").textContent=formatTime(historyPoints.at(-1).time);$("chartGrid").innerHTML=[80,160,240,320].map(y=>`<line x1="0" y1="${y}" x2="900" y2="${y}" stroke="#25323d" stroke-width="1"/>`).join("")}
function setPerformance(id,value){const el=$(id);el.textContent=pct(value);el.className=value>=0?"up":"down"}
function renderFavorite(){$("detailFavorite").textContent=favorites.has(coinId)?"★ 已收藏":"☆ 加入收藏";$("detailFavorite").classList.toggle("selected",favorites.has(coinId))}
function toggleFavorite(){favorites.has(coinId)?favorites.delete(coinId):favorites.add(coinId);localStorage.setItem("hengjing-crypto-watchlist",JSON.stringify([...favorites]));renderFavorite();toast(favorites.has(coinId)?"已加入收藏":"已取消收藏")}
function setAlert(){if(!coin)return;const current=loadStored("hengjing-crypto-alerts",{}),value=prompt(`当 ${coin.symbol} 价格达到或超过多少美元时提醒？`,current[coinId]||coin.price);if(value===null)return;const target=Number(value);if(!Number.isFinite(target)||target<=0)return toast("请输入有效价格");current[coinId]=target;localStorage.setItem("hengjing-crypto-alerts",JSON.stringify(current));sessionStorage.removeItem(`alerted-${coinId}`);toast(`提醒价已设置为 ${money(target)}`)}
function checkDetailAlert(){const target=Number(loadStored("hengjing-crypto-alerts",{})[coinId]);if(target&&coin.price>=target&&!sessionStorage.getItem(`alerted-${coinId}`)){sessionStorage.setItem(`alerted-${coinId}`,"1");toast(`${coin.symbol} 已达到提醒价 ${money(target)}`)}}
function loadStored(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback))}catch{return fallback}}
function toast(message){const el=$("toast");el.textContent=message;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2200)}
$("detailSearch").oninput=renderList;$("detailFavorite").onclick=toggleFavorite;$("detailAlert").onclick=setAlert;$("detailCopy").onclick=async()=>{try{await navigator.clipboard.writeText(location.href);toast("页面链接已复制")}catch{toast("复制失败，请手动复制地址")}};
document.querySelectorAll("[data-interval]").forEach(button=>button.onclick=()=>{interval=button.dataset.interval;document.querySelectorAll("[data-interval]").forEach(x=>x.classList.toggle("active",x===button));loadHistory()});
loadDetail();setInterval(loadDetail,15000);

