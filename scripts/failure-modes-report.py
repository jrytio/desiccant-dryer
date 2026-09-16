#!/usr/bin/env python3
"""Render docs/failure-modes.md as a filterable, colour-coded HTML page.

Usage: scripts/failure-modes-report.py [output.html]
The markdown stays the source of truth; this only reads it.
"""
import html, json, pathlib, re, sys

SRC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "failure-modes.md"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("failure-modes.html")

ROW = re.compile(r"^\| ([A-L]-\d\d) \| (.+) \| [🔴🟠🟡🔵⚪] (P[0-4]) \| (HW|WIRE|FW|CFG|OPS) \| (virtual|bench|live|inspect) \| (✱?) \|$")
CAT = re.compile(r"^## ([A-L])\. (.+)$")
PRI_MEANING, items, cats, issues, cur = {}, [], [], [], None
ISSUE = re.compile(r"^\| (\d+) \| (.+?) \| ((?:[A-L]-\d\d(?:, )?)+) \| (P[0-4]) \|$")
for ln in SRC.read_text().splitlines():
    m = re.match(r"^\| \*\*(P[0-4])\*\* \| (.+) \|$", ln)
    if m: PRI_MEANING[m.group(1)] = m.group(2)
    m = CAT.match(ln)
    if m: cur = m.group(1); cats.append({"key": cur, "name": m.group(2)})
    m = ISSUE.match(ln)
    if m:
        issues.append({"n": int(m.group(1)), "title": m.group(2), "ids": m.group(3).split(", "), "pri": m.group(4)})
    m = ROW.match(ln)
    if m:
        i, text, pri, kind, ver, gap = m.groups()
        items.append({"id": i, "cat": cur, "text": text, "pri": pri, "kind": kind, "verify": ver, "gap": bool(gap)})

issue_of = {i: iss["n"] for iss in issues for i in iss["ids"]}
for it in items: it["issue"] = issue_of.get(it["id"])
counts = {p: sum(1 for x in items if x["pri"] == p) for p in ["P0", "P1", "P2", "P3", "P4"]}
data = json.dumps({"cats": cats, "items": items, "issues": issues, "meaning": PRI_MEANING}, ensure_ascii=False)

page = """<title>Desiccant Dryer Failure Modes</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&display=swap">
<style>
:root{
  --bg:#F3F5F7; --panel:#FFFFFF; --ink:#1B2126; --ink-2:#4B555E; --ink-3:#7C868F; --line:#D9DEE3; --line-2:#E9ECEF;
  --accent:#1F5F8B; --accent-ink:#FFFFFF; --chip:#EAEFF3; --hover:#F7F9FB; --focus:#1F5F8B;
  --p0:#B3261E; --p1:#C4601A; --p2:#A98400; --p3:#2F6DB0; --p4:#7C868F;
  --p0-bg:#FBEDEC; --p1-bg:#FCF0E6; --p2-bg:#FBF5DF; --p3-bg:#E8F0F9; --p4-bg:#EEF0F2;
  --gap:#7A3E9D; --gap-bg:#F3EAF8;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --bg:#14181C; --panel:#1B2126; --ink:#E6EAEE; --ink-2:#AEB7BF; --ink-3:#7C868F; --line:#2C343B; --line-2:#242B31;
  --accent:#6FB1E0; --accent-ink:#0F1A24; --chip:#252D34; --hover:#20272D; --focus:#6FB1E0;
  --p0:#F0665E; --p1:#E9924F; --p2:#D9B33A; --p3:#6FA6E0; --p4:#98A2AB;
  --p0-bg:#3A1F1E; --p1-bg:#3A2A1B; --p2-bg:#36311A; --p3-bg:#1C2C3D; --p4-bg:#252B31;
  --gap:#C69AE6; --gap-bg:#2E2238;
}}
:root[data-theme="dark"]{
  --bg:#14181C; --panel:#1B2126; --ink:#E6EAEE; --ink-2:#AEB7BF; --ink-3:#7C868F; --line:#2C343B; --line-2:#242B31;
  --accent:#6FB1E0; --accent-ink:#0F1A24; --chip:#252D34; --hover:#20272D; --focus:#6FB1E0;
  --p0:#F0665E; --p1:#E9924F; --p2:#D9B33A; --p3:#6FA6E0; --p4:#98A2AB;
  --p0-bg:#3A1F1E; --p1-bg:#3A2A1B; --p2-bg:#36311A; --p3-bg:#1C2C3D; --p4-bg:#252B31;
  --gap:#C69AE6; --gap-bg:#2E2238;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.45 "IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;margin:0}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
header{padding:28px 32px 18px;max-width:1240px;margin:0 auto}
h1{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;font-weight:600;font-size:28px;letter-spacing:-.01em;margin:0 0 6px;text-wrap:balance}
.sub{color:var(--ink-2);max-width:68ch;margin:0}
.eyebrow{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);margin-bottom:8px}
.scale{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0 0}
.tile{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--pc);padding:10px 12px;border-radius:4px;cursor:pointer;text-align:left;color:var(--ink);font:inherit}
.tile:focus-visible,.chip:focus-visible,input:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.tile[aria-pressed="false"]{opacity:.45}
.tile .n{font-size:24px;font-weight:600;line-height:1;color:var(--pc)}
.tile .l{font-weight:600;margin-top:4px}
.tile .d{font-size:12px;color:var(--ink-2);margin-top:2px;line-height:1.35}
.bar{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 32px}
.bar-in{max-width:1240px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center}
.group{display:flex;gap:6px;align-items:center}
.group .g{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);margin-right:2px}
.chip{background:var(--chip);color:var(--ink-2);border:1px solid transparent;border-radius:999px;padding:3px 10px;font:inherit;font-size:12.5px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink)}
.chip.gapc[aria-pressed="true"]{background:var(--gap);color:#fff}
input[type=search]{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:4px;padding:5px 9px;font:inherit;font-size:13px;min-width:220px}
.shown{margin-left:auto;color:var(--ink-2);font-size:12.5px}
main{max-width:1240px;margin:0 auto;padding:8px 32px 48px}
section{margin-top:26px}
section[hidden]{display:none}
h2{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;font-weight:600;font-size:18px;margin:0 0 8px;display:flex;align-items:baseline;gap:10px}
h2 .k{color:var(--ink-3);font-weight:500}
h2 .cc{font-size:12px;color:var(--ink-3);font-weight:400;margin-left:auto}
.wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%;min-width:760px}
th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-weight:500}
td{padding:7px 10px;border-bottom:1px solid var(--line-2);vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--hover)}
tr[hidden]{display:none}
td.id{width:64px;border-left:4px solid var(--pc);color:var(--ink-2);white-space:nowrap}
td.pri{width:64px;white-space:nowrap}
.pb{display:inline-block;font-weight:600;font-size:12px;padding:1px 7px;border-radius:3px;color:var(--pc);background:var(--pbg)}
td.kind,td.ver{width:76px;color:var(--ink-2);font-size:12.5px;white-space:nowrap}
td.gap{width:44px;text-align:center}
.gb{display:inline-block;font-size:11px;font-weight:600;color:var(--gap);background:var(--gap-bg);border-radius:3px;padding:1px 6px}
tr.p0 td.id,tr.p0 .pb{--pc:var(--p0);--pbg:var(--p0-bg)}
tr.p1 td.id,tr.p1 .pb{--pc:var(--p1);--pbg:var(--p1-bg)}
tr.p2 td.id,tr.p2 .pb{--pc:var(--p2);--pbg:var(--p2-bg)}
tr.p3 td.id,tr.p3 .pb{--pc:var(--p3);--pbg:var(--p3-bg)}
tr.p4 td.id,tr.p4 .pb{--pc:var(--p4);--pbg:var(--p4-bg)}
td.iss{width:52px;white-space:nowrap}
.il{color:var(--accent);text-decoration:none;font-weight:500;cursor:pointer;background:none;border:0;font:inherit;padding:0}
.il:hover{text-decoration:underline}
#issues td.t{width:auto}
#issues td.ids{color:var(--ink-2);font-size:12.5px}
.key{font-size:12.5px;color:var(--ink-2);margin:14px 0 0;max-width:110ch}
.key b{color:var(--ink)}
.empty{color:var(--ink-3);padding:24px 10px;text-align:center}
@media (max-width:900px){.scale{grid-template-columns:repeat(2,1fr)}header,.bar,main{padding-left:16px;padding-right:16px}}
@media (prefers-reduced-motion:no-preference){.tile,.chip{transition:opacity .15s,background .15s}}
</style>
<header>
  <div class="eyebrow">esp32-desiccant-dryer-controller · replaces the stock board in an Azco VMD-08 · __N__ items</div>
  <h1>Desiccant Dryer Failure Modes</h1>
  <p class="sub">Every hardware and software failure we could think of, grouped by subsystem and ranked from “this starts a fire” to “the display is wrong”. Source of truth is <span class="mono">docs/failure-modes.md</span>; this page is rendered from it. Click a priority tile or a chip to filter.</p>
  <div class="scale" id="scale"></div>
  <p class="key"><b>Kind</b>: HW component fault · WIRE assembly or wiring error · FW firmware logic · CFG YAML or tunable · OPS operator or Home Assistant action. <b>Verify</b>: virtual provable in the host or virtual build · bench real board, mains off · live energised heaters, instrumented · inspect a build or config review. <b>Gap</b>: the firmware has no detection for this today.</p>
</header>
<div class="bar"><div class="bar-in">
  <div class="group" id="kind"><span class="g">Kind</span></div>
  <div class="group" id="verify"><span class="g">Verify</span></div>
  <div class="group"><button class="chip gapc" id="gaponly" aria-pressed="false">Gaps only</button></div>
  <input type="search" id="q" placeholder="Search text or ID" aria-label="Search failures">
  <span class="shown" id="shown"></span>
</div></div>
<main id="main"></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const PRI=['P0','P1','P2','P3','P4'];
const LABEL={P0:'Fire / shock',P1:'Damage or lost safety layer',P2:'Wet air or silent stop',P3:'Degraded operation',P4:'Display only'};
const st={pri:new Set(PRI),kind:new Set(),verify:new Set(),gap:false,q:''};
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const scale=document.getElementById('scale');
PRI.forEach(p=>{const n=D.items.filter(i=>i.pri===p).length;const b=document.createElement('button');b.className='tile';b.style.setProperty('--pc',`var(--${p.toLowerCase()})`);b.setAttribute('aria-pressed','true');b.dataset.p=p;
 b.innerHTML=`<div class="n mono">${n}</div><div class="l">${p} · ${LABEL[p]}</div><div class="d">${esc(D.meaning[p]||'')}</div>`;
 b.onclick=()=>{if(st.pri.size===PRI.length){st.pri=new Set([p]);}else if(st.pri.has(p)){st.pri.delete(p);if(!st.pri.size)st.pri=new Set(PRI);}else st.pri.add(p);render();};scale.appendChild(b);});
function chips(id,vals){const g=document.getElementById(id);vals.forEach(v=>{const c=document.createElement('button');c.className='chip';c.textContent=v;c.setAttribute('aria-pressed','false');c.dataset.v=v;c.onclick=()=>{st[id].has(v)?st[id].delete(v):st[id].add(v);render();};g.appendChild(c);});}
chips('kind',['HW','WIRE','FW','CFG','OPS']);chips('verify',['virtual','bench','live','inspect']);
document.getElementById('gaponly').onclick=e=>{st.gap=!st.gap;render();};
document.getElementById('q').oninput=e=>{st.q=e.target.value.trim().toLowerCase();render();};
const main=document.getElementById('main');
D.cats.forEach(c=>{const s=document.createElement('section');s.id='cat-'+c.key;
 const rows=D.items.filter(i=>i.cat===c.key).map(i=>`<tr class="${i.pri.toLowerCase()}" data-id="${i.id}"><td class="id mono">${i.id}</td><td>${esc(i.text)}</td><td class="pri"><span class="pb">${i.pri}</span></td><td class="kind mono">${i.kind}</td><td class="ver mono">${i.verify}</td><td class="gap">${i.gap?'<span class="gb">gap</span>':''}</td><td class="iss mono">${i.issue?`<button class="il" data-iss="${i.issue}" title="Show issue ${i.issue}">#${i.issue}</button>`:''}</td></tr>`).join('');
 s.innerHTML=`<h2><span class="k mono">${c.key}</span>${esc(c.name)}<span class="cc mono" data-cc></span></h2><div class="wrap"><table><thead><tr><th>ID</th><th>Failure</th><th>Pri</th><th>Kind</th><th>Verify</th><th>Gap</th><th>Issue</th></tr></thead><tbody>${rows}</tbody></table></div>`;
 main.appendChild(s);});
const iss=document.createElement('section');iss.id='issues';
iss.innerHTML=`<h2><span class="k mono">§</span>Proposed GitHub issues<span class="cc mono">${D.issues.length} issues</span></h2><div class="wrap"><table><thead><tr><th>#</th><th>Title</th><th>Rows</th><th>Pri</th></tr></thead><tbody>${D.issues.map(x=>`<tr class="${x.pri.toLowerCase()}"><td class="id mono"><button class="il" data-iss="${x.n}">#${x.n}</button></td><td class="t">${esc(x.title)}</td><td class="ids mono">${x.ids.join(', ')}</td><td class="pri"><span class="pb">${x.pri}</span></td></tr>`).join('')}</tbody></table></div>`;
main.appendChild(iss);
st.issue=null;
main.addEventListener('click',e=>{const b=e.target.closest('[data-iss]');if(!b)return;st.issue=st.issue===+b.dataset.iss?null:+b.dataset.iss;st.pri=new Set(PRI);render();window.scrollTo({top:0,behavior:'smooth'});});
const byId=Object.fromEntries(D.items.map(i=>[i.id,i]));
function render(){
 document.querySelectorAll('.tile').forEach(b=>b.setAttribute('aria-pressed',String(st.pri.has(b.dataset.p))));
 ['kind','verify'].forEach(id=>document.querySelectorAll('#'+id+' .chip').forEach(c=>c.setAttribute('aria-pressed',String(st[id].has(c.dataset.v)))));
 document.getElementById('gaponly').setAttribute('aria-pressed',String(st.gap));
 let shown=0;
 document.querySelectorAll('section:not(#issues)').forEach(s=>{let n=0;s.querySelectorAll('tbody tr').forEach(tr=>{const i=byId[tr.dataset.id];
  const ok=st.pri.has(i.pri)&&(!st.kind.size||st.kind.has(i.kind))&&(!st.verify.size||st.verify.has(i.verify))&&(!st.gap||i.gap)&&(!st.issue||i.issue===st.issue)&&(!st.q||(i.id+' '+i.text).toLowerCase().includes(st.q));
  tr.hidden=!ok;if(ok)n++;});shown+=n;s.hidden=n===0;s.querySelector('[data-cc]').textContent=n+' shown';});
 document.getElementById('shown').textContent=shown+' of '+D.items.length+' shown'+(st.issue?' · issue #'+st.issue+' (click # again to clear)':'');
document.querySelectorAll('.il').forEach(b=>b.style.fontWeight=(+b.dataset.iss===st.issue)?'700':'500');
}
render();
</script>
"""
OUT.write_text(page.replace("__DATA__", data.replace("</", "<\\/")).replace("__N__", str(len(items))))
print(f"{len(items)} items, {counts} -> {OUT}")
