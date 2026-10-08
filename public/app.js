const state = { notices: [], board: 'active', group: 'all', query: '', period: 'all', sort: 'deadline' };
const labels = { all: '전체기관', ulsan_all: '울산 기관', ulsan_city: '울산시', ulsan_districts: '5개 구·군', ulsan_education: '교육청', nationwide: '전국' };
const $ = s => document.querySelector(s);
const dateFormat = new Intl.DateTimeFormat('sv-SE', {timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'});
function parseDate(value) {
  if (!value) return null;
  let s=String(value).trim().replace(' ','T');
  if (/^\d{4}-\d\d-\d\d$/.test(s)) s+='T00:00:00';
  if (!/(Z|[+-]\d\d:\d\d)$/.test(s)) s+='+09:00';
  const d=new Date(s); return Number.isNaN(+d)?null:d;
}
function due(value, now=new Date()) {
  const end=parseDate(value); if(!end)return {text:'미정',days:Infinity,expired:false};
  if(end<=now)return {text:'마감',days:-1,expired:true};
  const days=Math.round((Date.parse(dateFormat.format(end))-Date.parse(dateFormat.format(now)))/86400000);
  return {text:days===0?'D-DAY':`D-${days}`,days,expired:false};
}
function isToday(value){const d=parseDate(value);return d&&dateFormat.format(d)===dateFormat.format(new Date());}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function safeUrl(value){try{const u=new URL(value);return ['http:','https:'].includes(u.protocol)?u.href:'https://www.g2b.go.kr/';}catch{return 'https://www.g2b.go.kr/';}}
function dateText(value,time=false){const d=parseDate(value);if(!d)return '미정';return new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',...(time?{hour:'2-digit',minute:'2-digit',hour12:false}:{})}).format(d);}
function groupMatch(n,g){if(g==='all')return true;if(g==='ulsan_all')return n.matches?.groupIds?.some(x=>x.startsWith('ulsan_'))||/울산/.test(`${n.noticeInstitution||''} ${n.demandInstitution||''}`);return n.matches?.groupIds?.includes(g);}
function filtered(){
 return state.notices.filter(n=>{
  const d=due(n.closedAt);
  if(d.expired!==(state.board==='closed')||!groupMatch(n,state.group))return false;
  if(state.query&&!`${n.title||''} ${n.demandInstitution||''} ${n.noticeInstitution||''}`.toLocaleLowerCase().includes(state.query.toLocaleLowerCase()))return false;
  if(state.board==='active'){
   if(state.period==='today'&&!isToday(n.publishedAt))return false;
   if(state.period==='urgent'&&d.days>5)return false;
   if(state.period==='soon'&&d.days>10)return false;
  }
  return true;
 }).sort((a,b)=>{
  if(state.sort==='newest')return (+parseDate(b.publishedAt)||0)-(+parseDate(a.publishedAt)||0);
  const x=+(parseDate(a.closedAt))||Number.MAX_SAFE_INTEGER,y=+(parseDate(b.closedAt))||Number.MAX_SAFE_INTEGER;
  return state.board==='closed'?y-x:x-y;
 });
}
function render(){
 const closed=state.board==='closed',rows=filtered();
 $('#boardTitle').textContent=closed?'마감된 공고 조회':'입찰공고 조회';
 $('#currentLabel').textContent=labels[state.group]+(closed?' · 마감':'');
 $('#visibleCount').textContent=rows.length; $('#emptyState').hidden=rows.length>0;
 $('#period').disabled=closed;
 $('#boardNote').textContent=closed?'보관된 마감 공고입니다. 정정·취소 여부와 참가 자격은 원문에서 확인하세요.':'마감된 공고는 ‘마감된 공고’ 게시판에서 확인할 수 있습니다.';
 document.querySelectorAll('[data-group]').forEach(b=>{const active=b.dataset.group===state.group;b.classList.toggle('active',active);b.setAttribute('aria-pressed',active);});
 document.querySelectorAll('.main-nav [data-board]').forEach(b=>{const active=b.dataset.board===state.board;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',active);});
 $('#noticeList').innerHTML=rows.map(n=>{
  const d=due(n.closedAt),tone=d.expired?'closed':d.days<=5?'urgent':d.days<=10?'soon':'';
  const url=esc(safeUrl(n.detailUrl)),amount=Number(n.estimatedPrice);
  return `<tr><td><span class="badge ${tone}">${d.text}</span></td><td class="title-cell">${isToday(n.publishedAt)?'<span class="new-tag">오늘 신규</span>':''}<a href="${url}" target="_blank" rel="noopener noreferrer">${esc(n.title||'제목 없는 공고')}</a><span class="institution">${esc(n.demandInstitution||n.noticeInstitution||'기관 미확인')}</span><small class="eligibility-note">참가 자격·지역 제한 원문 확인 필요</small></td><td class="price">${amount>0?amount.toLocaleString('ko-KR')+'원':'금액 미정'}</td><td class="date" data-label="공고일">${dateText(n.publishedAt)}</td><td class="date" data-label="마감일">${dateText(n.closedAt,true)}</td><td><a class="original" href="${url}" target="_blank" rel="noopener noreferrer" aria-label="${esc(n.title)} 원문 보기">원문 ↗</a></td></tr>`;
 }).join('');
 const active=state.notices.filter(n=>!due(n.closedAt).expired);
 $('#stat-all').textContent=active.length;$('#stat-today').textContent=active.filter(n=>isToday(n.publishedAt)).length;
 $('#stat-urgent').textContent=active.filter(n=>due(n.closedAt).days<=5).length;$('#stat-closed').textContent=state.notices.length-active.length;
}
async function load(){
 const button=$('#refreshButton');button.disabled=true;button.textContent='↻ 확인 중';$('#errorState').hidden=true;
 try{
  const r=await fetch('data/bids.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(`HTTP ${r.status}`);
  const data=await r.json();if(!Array.isArray(data.notices))throw Error('Invalid notices');state.notices=data.notices;
  $('#syncText').textContent=data.meta?.generatedAt?'최근 수집 '+dateText(data.meta.generatedAt,true):'수집 시간 미확인';
  $('#sourceBadge').textContent=data.meta?.source==='mock'?'모의 데이터':'나라장터 공개정보';render();
  const age=Date.now()-new Date(data.meta?.generatedAt).getTime();
  let message=(!Number.isFinite(age)||age>18*3600000)?'최근 수집 후 시간이 지났습니다. 최신 공고 여부를 원문에서 확인하세요.':'';
  try {
   const sr=await fetch('data/status.json?t='+Date.now(),{cache:'no-store'});
   if(!sr.ok)throw Error('status unavailable');
   const status=await sr.json();
   if(status.state==='error')message='최근 수집 실패 — 마지막 성공 자료를 표시합니다. 관리자 재수집을 확인하세요.';
  } catch { message=message||'수집 상태를 확인할 수 없습니다. 표시된 최근 수집 시각을 확인하세요.'; }
  $('#errorState').textContent=message;$('#errorState').hidden=!message;
 }catch(e){$('#errorState').textContent='자료 연결 실패 — 표시된 자료는 이전에 불러온 내용입니다. 자료 새로고침으로 재시도하세요.';$('#errorState').hidden=false;$('#syncText').textContent='불러오기 실패 · 재시도 필요';$('#sourceBadge').textContent='연결 확인 필요';}
 finally{button.disabled=false;button.textContent='↻ 자료 새로고침';}
}
function moveBoard(){render();$('#boardTitle').scrollIntoView({behavior:'smooth',block:'start'});}
document.querySelectorAll('[data-board]').forEach(b=>b.addEventListener('click',()=>{state.board=b.dataset.board;moveBoard();}));
document.querySelectorAll('[data-quick]').forEach(b=>b.addEventListener('click',()=>{state.board='active';state.group='all';state.query='';$('#query').value='';state.period=b.dataset.quick;$('#period').value=state.period;moveBoard();}));
document.querySelectorAll('[data-group]').forEach(b=>b.addEventListener('click',()=>{state.group=b.dataset.group;render();}));
$('#searchForm').addEventListener('submit',e=>{e.preventDefault();state.query=$('#query').value.trim();render();});
$('#period').addEventListener('change',e=>{state.period=e.target.value;render();});
$('#sort').addEventListener('change',e=>{state.sort=e.target.value;render();});
$('#resetButton').addEventListener('click',()=>{state.group='all';state.query='';state.period='all';state.sort='deadline';$('#query').value='';$('#period').value='all';$('#sort').value='deadline';render();});
$('#refreshButton').addEventListener('click',load);
function updateClock(){$('#todayText').textContent=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'long',day:'numeric',weekday:'short'}).format(new Date());}
setInterval(()=>{if(!document.hidden)load();},300000);
updateClock();load();setInterval(()=>{updateClock();render();},60000);
