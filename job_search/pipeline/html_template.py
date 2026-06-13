"""Self-contained HTML template for the interactive job report."""

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Report</title>
<style>
:root{--bg:#f5f5f5;--card:#ffffff;--border:#e0e0e0;--text:#1a1a1a;--sub:#666;--accent:#0070f3;--green:#16a34a;--danger:#dc2626;--orange:#d97706;--dim:#e8f0fe}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:15px;line-height:1.5}
a{color:inherit;text-decoration:none}

#hdr{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--border);padding:12px 20px;z-index:100;box-shadow:0 1px 4px rgba(0,0,0,.06)}
#hdr h1{font-size:17px;font-weight:600;margin-bottom:4px;color:var(--text)}
#summary{color:var(--sub);font-size:12px;margin-bottom:10px}
#filters{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.fl{display:flex;align-items:center;gap:5px}
.fl-label{color:var(--sub);font-size:12px;white-space:nowrap}
#score-slider{width:70px;accent-color:var(--accent)}
#score-val{color:var(--accent);font-size:12px;min-width:24px;font-weight:600}
.mbtn{padding:3px 9px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--sub);font-size:12px;cursor:pointer;transition:all .15s}
.mbtn.on{border-color:var(--accent);color:var(--accent);background:#eff6ff}
#search{background:#fff;border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;font-size:12px;width:150px}
#search:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px rgba(0,112,243,.1)}
#show-hidden{padding:3px 9px;border:1px solid var(--border);border-radius:10px;background:#fff;color:var(--sub);font-size:12px;cursor:pointer}
#show-hidden.on{border-color:var(--orange);color:var(--orange);background:#fffbeb}

#main{padding:14px 20px;max-width:880px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:18px;margin-bottom:12px;transition:opacity .2s;box-shadow:0 1px 3px rgba(0,0,0,.04);overflow-wrap:break-word;word-break:break-word}
.card.applied{border-left:3px solid var(--green)}
.card.skipped{opacity:.4}
.card[hidden]{display:none}

.ch{display:flex;align-items:flex-start;gap:12px;margin-bottom:12px}
.score-col{min-width:42px;text-align:center}
.snum{font-size:22px;font-weight:700;color:var(--accent);line-height:1}
.sbar-wrap{width:42px;height:4px;background:var(--dim);border-radius:2px;margin-top:5px}
.sbar{height:4px;border-radius:2px;background:var(--accent)}
.ctitle{flex:1;min-width:0}
.ctitle h3{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text);min-width:0}
.cco{color:var(--sub);font-size:12px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badge{font-size:11px;padding:2px 8px;border-radius:10px;white-space:nowrap;flex-shrink:0;font-weight:500}
.mode-r{background:#ecfdf5;color:#059669}
.mode-h{background:#fffbeb;color:var(--orange)}
.mode-o{background:#f3f4f6;color:#6b7280}
.mode-u{background:#f9fafb;color:#9ca3af}

.cmeta{color:var(--sub);font-size:13px;margin-bottom:10px}
.dets{display:flex;gap:12px;flex-wrap:wrap;font-size:13px;color:var(--sub);margin-bottom:14px;word-break:break-word;padding-bottom:12px;border-bottom:1px solid var(--border)}
.dets span{word-break:break-word}
.sgrp{margin-bottom:12px}
.sgrp-lbl{font-size:13px;font-weight:600;margin-bottom:4px;color:var(--text)}
.skill-list{list-style:disc;padding-left:20px;margin:0}
.skill-list li{padding:3px 0;font-size:14px;word-break:break-word}
.skill-have{color:#059669}
.skill-miss{color:var(--danger)}
.skill-nice{color:var(--orange)}

.cfoot{display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:8px;border-top:1px solid var(--border)}
.lilink{font-size:12px;color:var(--accent);flex:1}
.lilink:hover{text-decoration:underline}
.btn{padding:5px 12px;border-radius:5px;font-size:12px;cursor:pointer;border:1px solid;transition:all .15s;font-weight:500;background:#fff}
.btn-a{border-color:#86efac;color:var(--green)}
.btn-a.on{background:var(--green);color:#fff;border-color:var(--green)}
.btn-s{border-color:var(--border);color:var(--sub)}
.btn-s.on{border-color:var(--danger);color:var(--danger);background:#fef2f2}

.fsec-hdr{font-size:12px;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:.05em;margin:18px 0 6px}
.flist{padding:10px 14px;background:var(--card);border:1px solid var(--border);border-radius:8px}
.fgrp{margin-bottom:10px}
.fgrp:last-child{margin-bottom:0}
.fgrp-lbl{font-size:12px;color:var(--sub);margin-bottom:3px;font-weight:500}
.fitem{font-size:12px;color:#999;padding:1px 0}
.fitem a{color:#aaa}
.fitem a:hover{color:var(--sub)}

#toast{position:fixed;bottom:18px;right:18px;background:#1a1a1a;color:#fff;padding:7px 14px;border-radius:6px;font-size:12px;opacity:0;transition:opacity .3s;pointer-events:none}
#toast.show{opacity:1}
</style>
</head>
<body>
<script id="jobs-data" type="application/json">__JOBS_DATA__</script>

<div id="hdr">
  <h1>Job Report &mdash; <span id="date-lbl"></span></h1>
  <div id="summary"></div>
  <div id="filters">
    <div class="fl">
      <span class="fl-label">Score &ge;</span>
      <input type="range" id="score-slider" min="0" max="100" step="5" value="0">
      <span id="score-val">0</span>
    </div>
    <div class="fl" id="mode-btns"></div>
    <div class="fl">
      <input type="text" id="search" placeholder="Search company / title…">
    </div>
    <button id="show-hidden">Show hidden</button>
  </div>
</div>

<div id="main"></div>
<div id="toast"></div>

<script>
(function(){
const DATA = JSON.parse(document.getElementById('jobs-data').textContent);
const MODE_CLASS = {Remote:'mode-r', Hybrid:'mode-h', Onsite:'mode-o', Unknown:'mode-u'};

// Seed state from server-embedded initial_state (no async fetch needed on load)
let state = DATA.initial_state || {};
let showHidden = false, minScore = 0, query = '';
let modes = new Set(['Remote','Hybrid','Onsite','Unknown']);

function esc(s){
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}

async function postToggle(jobId, action, value){
  try{
    const r=await fetch('/toggle',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({job_id:jobId,action,value})});
    if(!r.ok) throw new Error();
  }catch(e){ toast('Could not save — is the server still running?'); }
}

function jobState(id){ return state[id]||{applied:false,hidden:false}; }

function isVisible(job){
  const s=jobState(job.job_id);
  if(s.hidden && !showHidden) return false;
  if(job.score < minScore) return false;
  if(!modes.has(job.work_mode)) return false;
  if(query){
    const q=query.toLowerCase();
    if(!job.company.toLowerCase().includes(q) && !job.title.toLowerCase().includes(q)) return false;
  }
  return true;
}

function buildSkillsHtml(job){
  let h='';
  if(job.matched_required && job.matched_required.length)
    h+=`<div class="sgrp"><div class="sgrp-lbl">✅ Required (have)</div><ul class="skill-list">${
      job.matched_required.map(x=>`<li class="skill-have">${esc(x)}</li>`).join('')}</ul></div>`;
  if(job.unmatched_required && job.unmatched_required.length)
    h+=`<div class="sgrp"><div class="sgrp-lbl">❌ Required (missing)</div><ul class="skill-list">${
      job.unmatched_required.map(x=>`<li class="skill-miss">${esc(x)}</li>`).join('')}</ul></div>`;
  if(job.matched_nice && job.matched_nice.length)
    h+=`<div class="sgrp"><div class="sgrp-lbl">⭐ Preferred</div><ul class="skill-list">${
      job.matched_nice.map(x=>`<li class="skill-nice">${esc(x)}</li>`).join('')}</ul></div>`;
  return h;
}

function buildCard(job){
  const s=jobState(job.job_id);
  const card=document.createElement('div');
  card.className='card'+(s.applied?' applied':'')+(s.hidden?' skipped':'');
  card.dataset.id=job.job_id;
  if(!isVisible(job)) card.setAttribute('hidden','');

  const meta=[job.location,job.employment_type].filter(Boolean).join(' · ');
  const dets=[];
  if(job.tech_notes) dets.push(`🔧 ${esc(job.tech_notes)}`);
  if(job.seniority && job.seniority!=='Unknown') dets.push(`📊 ${esc(job.seniority)}`);
  if(job.salary) dets.push(`💰 ${esc(job.salary)}`);
  if(job.industry && job.industry!=='Unknown') dets.push(`🏭 ${esc(job.industry)}`);

  card.innerHTML=`
    <div class="ch">
      <div class="score-col">
        <div class="snum">${job.score}</div>
        <div class="sbar-wrap"><div class="sbar" style="width:${job.score}%"></div></div>
      </div>
      <div class="ctitle">
        <h3>${esc(job.title)}</h3>
        <div class="cco">${esc(job.company)}</div>
      </div>
      <span class="badge ${MODE_CLASS[job.work_mode]||'mode-u'}">${esc(job.work_mode)}</span>
    </div>
    ${meta?`<div class="cmeta">${esc(meta)}</div>`:''}
    ${dets.length?`<div class="dets">${dets.map(d=>`<span>${d}</span>`).join('')}</div>`:''}
    ${buildSkillsHtml(job)}
    <div class="cfoot">
      <a class="lilink" href="${esc(job.url)}" target="_blank" rel="noopener">↗ View on LinkedIn</a>
      <button class="btn btn-a${s.applied?' on':''}" data-id="${esc(job.job_id)}" data-act="applied">${
        s.applied?'✓ Applied':'Applied'}</button>
      <button class="btn btn-s${s.hidden?' on':''}" data-id="${esc(job.job_id)}" data-act="hidden">${
        s.hidden?'↩ Unhide':'Skip'}</button>
    </div>`;
  return card;
}

function countVisible(){ return DATA.scored.filter(isVisible).length; }
function countApplied(){ return DATA.scored.filter(j=>(state[j.job_id]||{}).applied).length; }

function updateSummary(){
  document.getElementById('summary').textContent=
    `${countVisible()} of ${DATA.scored.length} scored · ${
      (DATA.filtered||[]).length} filtered out · ${countApplied()} applied`;
}

function renderFiltered(){
  const old=document.getElementById('fsec'); if(old) old.remove();
  if(!DATA.filtered||!DATA.filtered.length) return;
  const grps={};
  for(const fj of DATA.filtered){ const r=fj.reason||'Other'; (grps[r]||(grps[r]=[])).push(fj); }
  const sec=document.createElement('div'); sec.id='fsec';
  sec.innerHTML=`<div class="fsec-hdr">Filtered Out (${DATA.filtered.length})</div>
    <div class="flist">${Object.entries(grps).map(([r,jobs])=>`
      <div class="fgrp">
        <div class="fgrp-lbl">${esc(r)} (${jobs.length})</div>
        ${jobs.map(j=>`<div class="fitem">${j.url
          ?`<a href="${esc(j.url)}" target="_blank">${esc(j.company)} — ${esc(j.title)}</a>`
          :`${esc(j.company)} — ${esc(j.title)}`}</div>`).join('')}
      </div>`).join('')}
    </div>`;
  document.getElementById('main').appendChild(sec);
}

function render(){
  const main=document.getElementById('main');
  main.innerHTML='';
  for(const job of DATA.scored) main.appendChild(buildCard(job));
  renderFiltered();
  updateSummary();
}

function applyFilters(){
  for(const card of document.querySelectorAll('.card')){
    const job=DATA.scored.find(j=>j.job_id===card.dataset.id);
    if(!job) continue;
    if(isVisible(job)) card.removeAttribute('hidden'); else card.setAttribute('hidden','');
  }
  updateSummary();
}

function setupFilters(){
  document.getElementById('score-slider').addEventListener('input',e=>{
    minScore=+e.target.value;
    document.getElementById('score-val').textContent=minScore;
    applyFilters();
  });
  const mb=document.getElementById('mode-btns');
  for(const m of['Remote','Hybrid','Onsite']){
    const btn=document.createElement('button');
    btn.className='mbtn on'; btn.dataset.mode=m; btn.textContent=m;
    btn.addEventListener('click',()=>{
      if(modes.has(m)){modes.delete(m);btn.classList.remove('on');}
      else{modes.add(m);btn.classList.add('on');}
      applyFilters();
    });
    mb.appendChild(btn);
  }
  document.getElementById('search').addEventListener('input',e=>{
    query=e.target.value.trim(); applyFilters();
  });
  document.getElementById('show-hidden').addEventListener('click',function(){
    showHidden=!showHidden; this.classList.toggle('on',showHidden); applyFilters();
  });
}

document.getElementById('main').addEventListener('click',async function(e){
  const btn=e.target.closest('.btn[data-act]'); if(!btn) return;
  const jobId=btn.dataset.id, act=btn.dataset.act;
  const cur=jobState(jobId);
  const newVal=!cur[act];
  state[jobId]={applied:cur.applied||false, hidden:cur.hidden||false};
  state[jobId][act]=newVal;
  await postToggle(jobId, act, newVal);

  const card=document.querySelector(`.card[data-id="${jobId}"]`); if(!card) return;
  if(act==='applied'){
    card.classList.toggle('applied',newVal);
    btn.classList.toggle('on',newVal);
    btn.textContent=newVal?'✓ Applied':'Applied';
  } else {
    card.classList.toggle('skipped',newVal);
    btn.classList.toggle('on',newVal);
    btn.textContent=newVal?'↩ Unhide':'Skip';
    if(!showHidden){ if(newVal) card.setAttribute('hidden',''); else card.removeAttribute('hidden'); }
  }
  updateSummary();
});

function init(){
  document.getElementById('date-lbl').textContent=DATA.display_date||DATA.date;
  setupFilters();
  render();
}
init();
})();
</script>
</body>
</html>"""
