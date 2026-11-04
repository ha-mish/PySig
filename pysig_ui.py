"""PySig 4.2 local browser interface.

Place this file beside main.py and run:

    python pysig_ui.py

The interface binds to 127.0.0.1 only, opens the default browser, edits the
selected YAML configuration, starts PySig in a background subprocess and shows
output files. No web framework or internet connection is required.
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required. Install it with: conda install pyyaml") from exc

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "configs" / "example_network_optimisation.yaml"
DEFAULT_OUTPUT = ROOT / "results"
MAX_BODY = 4 * 1024 * 1024


@dataclass
class RunState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    running: bool = False
    command: list[str] = field(default_factory=list)
    started_at: float | None = None
    finished_at: float | None = None
    return_code: int | None = None
    log: list[str] = field(default_factory=list)
    process: subprocess.Popen | None = None

    def snapshot(self) -> dict:
        with self.lock:
            elapsed = 0.0
            if self.started_at:
                elapsed = (self.finished_at or time.time()) - self.started_at
            return {
                "running": self.running,
                "command": self.command,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "return_code": self.return_code,
                "elapsed_s": round(elapsed, 2),
                "log": "".join(self.log[-2500:]),
            }


STATE = RunState()
APP = {"config": DEFAULT_CONFIG, "output": DEFAULT_OUTPUT}


def safe_resolve(base: Path, relative: str) -> Path:
    candidate = (base / relative).resolve()
    if base.resolve() not in candidate.parents and candidate != base.resolve():
        raise ValueError("Path is outside the permitted directory")
    return candidate


def read_yaml_text() -> str:
    return APP["config"].read_text(encoding="utf-8")


def load_yaml() -> dict:
    data = yaml.safe_load(read_yaml_text())
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def model_summary(data: dict) -> dict:
    intersections = data.get("intersections") or []
    lanes = data.get("lanes") or []
    movements = data.get("movements") or []
    links = data.get("network_links") or []
    controllers = data.get("controllers") or ([data["controller"]] if data.get("controller") else [])
    routes = data.get("routes") or []
    od_values = (data.get("origin_destination_matrix") or {}).get("values") or {}
    od_total = sum(float(v) for row in od_values.values() if isinstance(row, dict) for v in row.values())

    default_iid = intersections[0].get("id", "I1") if intersections else "I1"
    lane_by_id = {x.get("id"): x for x in lanes}
    movement_rows = []
    for m in movements:
        lane = lane_by_id.get(m.get("from_lane_id"), {})
        movement_rows.append({
            **m,
            "intersection_id": m.get("intersection_id") or lane.get("intersection_id") or default_iid,
            "lane_storage_pcu": lane.get("storage_pcu"),
            "lane_length_m": lane.get("physical_length_m"),
        })
    if not intersections and movements:
        intersections = [{
            "id": default_iid,
            "controller_id": controllers[0].get("id", "C1") if controllers else "C1",
            "movement_ids": [m.get("id") for m in movements],
        }]
    return {
        "model": data.get("model", {}),
        "run": data.get("run", {}),
        "settings": data.get("settings", {}),
        "intersections": intersections,
        "lanes": lanes,
        "movements": movement_rows,
        "links": links,
        "controllers": controllers,
        "phases": data.get("phases") or [],
        "routes": routes,
        "od_total": od_total,
        "assignment": data.get("assignment", {}),
        "network": data.get("network", {}),
        "optimisation": data.get("optimisation", {}),
    }


def list_outputs() -> list[dict]:
    out = APP["output"]
    if not out.exists():
        return []
    items = []
    for path in sorted(out.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        stat = path.stat()
        items.append({
            "name": path.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "kind": path.suffix.lower().lstrip(".") or "file",
        })
    return items


def output_preview(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return {"type": "json", "data": json.loads(path.read_text(encoding="utf-8"))}
    if suffix in (".yaml", ".yml"):
        return {"type": "yaml", "text": path.read_text(encoding="utf-8")}
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        return {"type": "csv", "rows": rows[:501], "truncated": len(rows) > 501}
    try:
        return {"type": "text", "text": path.read_text(encoding="utf-8")[:500000]}
    except UnicodeDecodeError:
        return {"type": "binary", "size": path.stat().st_size}


def start_run(mode: str) -> None:
    with STATE.lock:
        if STATE.running:
            raise RuntimeError("A PySig run is already in progress")
        output = APP["output"]
        output.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(ROOT / "main.py"), mode,
                   "--config", str(APP["config"]), "--output", str(output)]
        STATE.running = True
        STATE.command = command
        STATE.started_at = time.time()
        STATE.finished_at = None
        STATE.return_code = None
        STATE.log = ["PySig UI\n", "Command: " + " ".join(command) + "\n\n"]
        STATE.process = None

    def worker() -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with STATE.lock:
                STATE.process = process
            assert process.stdout is not None
            for line in process.stdout:
                with STATE.lock:
                    STATE.log.append(line)
                    if len(STATE.log) > 5000:
                        STATE.log = STATE.log[-4000:]
            code = process.wait()
            with STATE.lock:
                STATE.return_code = code
                STATE.log.append(f"\nProcess finished with exit code {code}.\n")
        except Exception:
            with STATE.lock:
                STATE.return_code = -1
                STATE.log.append("\n" + traceback.format_exc())
        finally:
            with STATE.lock:
                STATE.running = False
                STATE.finished_at = time.time()
                STATE.process = None

    threading.Thread(target=worker, name="pysig-runner", daemon=True).start()


def stop_run() -> bool:
    with STATE.lock:
        process = STATE.process
    if process and process.poll() is None:
        process.terminate()
        return True
    return False


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PySig Studio</title>
<style>
:root{--ink:#263238;--paper:#fffaf4;--panel:#fff;--line:#e8ded4;--pink:#ff9eb5;--red:#ff6b6b;--orange:#ffb86b;--yellow:#ffe66d;--mint:#8de4c1;--aqua:#72d6e8;--blue:#8bb8ff;--lilac:#c5a3ff;--shadow:0 8px 28px rgba(67,46,35,.10)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}button,input,select,textarea{font:inherit}.app{display:grid;grid-template-columns:260px 1fr;min-height:100vh}.side{background:#263238;color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-size:25px;font-weight:900;letter-spacing:-.8px}.brand b{color:var(--yellow)}.version{font-size:12px;color:#b9c5c9;margin-bottom:28px}.nav button{display:flex;width:100%;border:0;background:transparent;color:#dbe4e7;padding:12px 14px;margin:5px 0;border-radius:12px;text-align:left;font-weight:700;cursor:pointer}.nav button.active{background:var(--mint);color:#17352c}.nav button:hover{background:#394a50}.nav button.active:hover{background:var(--mint)}.sidefoot{position:absolute;left:18px;right:18px;bottom:20px;color:#aebdc1;font-size:11px}.main{padding:26px 30px 50px;min-width:0}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;gap:16px}.title h1{margin:0;font-size:28px;letter-spacing:-.7px}.title p{margin:3px 0;color:#6c777b}.status{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 12px;font-weight:800}.dot{width:10px;height:10px;border-radius:50%;background:var(--mint)}.dot.running{background:var(--orange);animation:pulse 1s infinite}.dot.failed{background:var(--red)}@keyframes pulse{50%{opacity:.35}}.view{display:none}.view.active{display:block}.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:18px;min-width:0}.card h2,.card h3{margin:0 0 12px}.metric{grid-column:span 3;min-height:112px}.metric .num{font-weight:900;font-size:30px}.metric .label{color:#6b777b;font-weight:700}.metric:nth-child(1){background:var(--pink)}.metric:nth-child(2){background:var(--yellow)}.metric:nth-child(3){background:var(--aqua)}.metric:nth-child(4){background:var(--lilac)}.wide{grid-column:span 12}.eight{grid-column:span 8}.four{grid-column:span 4}.toolbar{display:flex;gap:9px;flex-wrap:wrap;align-items:center;margin-bottom:13px}.btn{border:0;border-radius:12px;padding:10px 15px;font-weight:800;cursor:pointer;background:var(--blue);color:#183151}.btn.primary{background:var(--red);color:white}.btn.green{background:var(--mint);color:#17352c}.btn.yellow{background:var(--yellow)}.btn.ghost{background:#f2ece6}.btn:disabled{opacity:.45;cursor:not-allowed}.field{border:1px solid var(--line);border-radius:11px;padding:9px 11px;background:white}.editor{width:100%;height:64vh;resize:vertical;border:1px solid #d9cec4;border-radius:14px;padding:16px;background:#20282c;color:#e8f2f4;font:13px/1.55 Consolas,Monaco,monospace;tab-size:2}.notice{padding:11px 13px;border-radius:12px;background:#fff3bf;border:1px solid #ecd66c;margin:10px 0}.console{height:58vh;overflow:auto;background:#20282c;color:#d9f4eb;border-radius:14px;padding:16px;white-space:pre-wrap;font:12px/1.5 Consolas,monospace}.files{display:grid;grid-template-columns:280px 1fr;gap:15px}.filelist{max-height:65vh;overflow:auto}.file{display:block;width:100%;border:0;border-bottom:1px solid var(--line);background:white;padding:12px;text-align:left;cursor:pointer}.file:hover,.file.active{background:#e7f8f1}.file b{display:block}.file small{color:#728084}.preview{min-height:60vh;overflow:auto}.tablewrap{overflow:auto;max-height:65vh}.data{border-collapse:collapse;width:100%;font-size:12px}.data th{position:sticky;top:0;background:#263238;color:white}.data th,.data td{padding:7px 9px;border:1px solid #e5ddd6;text-align:left;white-space:nowrap}.data tr:nth-child(even){background:#faf6f1}pre.json{white-space:pre-wrap;background:#20282c;color:#e7f6ef;border-radius:13px;padding:15px}.canvas{width:100%;height:560px;border-radius:16px;background:#f7f2eb;border:1px solid #e0d5ca}.legend{display:flex;gap:13px;flex-wrap:wrap;color:#647175;font-size:12px;margin-top:9px}.swatch{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-2px}.pill{display:inline-block;border-radius:99px;padding:4px 9px;font-size:11px;font-weight:800;background:#eee}.error{color:#9f1f2d}.ok{color:#176849}@media(max-width:950px){.app{grid-template-columns:1fr}.side{position:relative;height:auto}.sidefoot{display:none}.nav{display:flex;overflow:auto}.nav button{white-space:nowrap}.main{padding:18px}.metric{grid-column:span 6}.eight,.four{grid-column:span 12}.files{grid-template-columns:1fr}.canvas{height:480px}}
</style>
</head>
<body><div class="app">
<aside class="side"><div class="brand">PySig <b>Studio</b></div><div class="version">Local browser UI · Version 4.2</div><div class="nav">
<button class="active" data-view="dashboard">Overview</button><button data-view="network">Network view</button><button data-view="yaml">YAML editor</button><button data-view="run">Run model</button><button data-view="outputs">Outputs</button></div><div class="sidefoot">Runs locally on 127.0.0.1.<br>No model data leaves this computer.</div></aside>
<main class="main"><header class="top"><div class="title"><h1 id="pageTitle">Model overview</h1><p id="modelName">Loading model...</p></div><div class="status"><span class="dot" id="statusDot"></span><span id="statusText">Ready</span></div></header>
<section id="dashboard" class="view active"><div class="grid"><div class="card metric"><div class="num" id="mIntersections">0</div><div class="label">Intersections</div></div><div class="card metric"><div class="num" id="mMovements">0</div><div class="label">Movements</div></div><div class="card metric"><div class="num" id="mRoutes">0</div><div class="label">Routes</div></div><div class="card metric"><div class="num" id="mDemand">0</div><div class="label">OD demand · PCU/h</div></div><div class="card eight"><h2>Model configuration</h2><div id="summary"></div></div><div class="card four"><h2>Quick actions</h2><div class="toolbar"><button class="btn primary" onclick="runModel('optimise')">Optimise network</button><button class="btn green" onclick="runModel('run')">Run assignment</button></div><p>Use the YAML editor to change assumptions, controller candidates, demand and network links.</p><div class="notice">The network drawing is schematic because the current YAML does not include geographic coordinates or arm bearings.</div></div></div></section>
<section id="network" class="view"><div class="card"><div class="toolbar"><button class="btn ghost" onclick="drawNetwork()">Redraw</button><span class="pill">Schematic bird's-eye view</span></div><svg id="networkSvg" class="canvas" viewBox="0 0 1200 560" preserveAspectRatio="xMidYMid meet"></svg><div class="legend"><span><i class="swatch" style="background:#263238"></i>road</span><span><i class="swatch" style="background:#8bb8ff"></i>movement</span><span><i class="swatch" style="background:#ff6b6b"></i>network link</span><span><i class="swatch" style="background:#ffe66d"></i>controller</span></div></div></section>
<section id="yaml" class="view"><div class="card"><div class="toolbar"><select id="configSelect" class="field"></select><button class="btn ghost" onclick="loadConfig()">Load</button><button class="btn primary" onclick="saveConfig()">Save YAML</button><button class="btn yellow" onclick="validateYaml()">Check syntax</button><span id="saveState"></span></div><textarea id="yamlEditor" class="editor" spellcheck="false"></textarea><p class="notice">Saving replaces the selected YAML file. Create a copy in the configs folder before making major changes.</p></div></section>
<section id="run" class="view"><div class="grid"><div class="card four"><h2>Run controls</h2><label><b>Operation</b></label><select id="runMode" class="field" style="width:100%;margin:8px 0 14px"><option value="optimise">Optimise network</option><option value="run">Run network assignment</option></select><div class="toolbar"><button id="runButton" class="btn primary" onclick="runSelected()">Start run</button><button id="stopButton" class="btn ghost" onclick="stopRun()">Stop</button></div><div id="runFacts"></div></div><div class="card eight"><h2>Run log</h2><div id="console" class="console">No run started.</div></div></div></section>
<section id="outputs" class="view"><div class="card"><div class="toolbar"><button class="btn green" onclick="loadOutputs()">Refresh files</button><span id="outputCount"></span></div><div class="files"><div id="fileList" class="filelist"></div><div id="preview" class="preview"><p>Select an output file.</p></div></div></div></section>
</main></div>
<script>
let model=null, runTimer=null, selectedFile='';
const titles={dashboard:'Model overview',network:'Network view',yaml:'YAML editor',run:'Run model',outputs:'Outputs'};
document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));document.getElementById(b.dataset.view).classList.add('active');document.getElementById('pageTitle').textContent=titles[b.dataset.view];if(b.dataset.view==='network')drawNetwork();if(b.dataset.view==='outputs')loadOutputs();});
async function api(url,opt){const r=await fetch(url,opt);const data=await r.json().catch(()=>({error:r.statusText}));if(!r.ok)throw new Error(data.error||r.statusText);return data}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fmtBytes(n){if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';return (n/1048576).toFixed(1)+' MB'}
async function boot(){await refreshState();await loadConfigList();await loadConfig();await pollRun();}
async function refreshState(){const s=await api('/api/state');model=s.model;document.getElementById('modelName').textContent=(model.model.name||model.model.id||'Unnamed model')+' · '+s.config;document.getElementById('mIntersections').textContent=model.intersections.length;document.getElementById('mMovements').textContent=model.movements.length;document.getElementById('mRoutes').textContent=model.routes.length;document.getElementById('mDemand').textContent=model.od_total.toLocaleString();document.getElementById('summary').innerHTML=`<table class="data"><tr><th>Item</th><th>Value</th></tr><tr><td>Run mode</td><td>${esc(model.run.mode||'network')}</td></tr><tr><td>Controllers</td><td>${model.controllers.length}</td></tr><tr><td>Lanes</td><td>${model.lanes.length}</td></tr><tr><td>Network links</td><td>${model.links.length}</td></tr><tr><td>Horizon</td><td>${esc(model.network.horizon_s||'default')} s</td></tr><tr><td>Time slice</td><td>${esc(model.network.time_slice_s||'default')} s</td></tr></table>`;}
async function loadConfigList(){const d=await api('/api/configs');const sel=document.getElementById('configSelect');sel.innerHTML=d.configs.map(x=>`<option value="${esc(x)}" ${x===d.selected?'selected':''}>${esc(x)}</option>`).join('');}
async function loadConfig(){const name=document.getElementById('configSelect').value;const d=await api('/api/config?name='+encodeURIComponent(name));document.getElementById('yamlEditor').value=d.text;document.getElementById('saveState').textContent='';await refreshState();}
async function saveConfig(){try{const name=document.getElementById('configSelect').value;const text=document.getElementById('yamlEditor').value;await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,text})});document.getElementById('saveState').innerHTML='<span class="ok">Saved</span>';await refreshState();drawNetwork();}catch(e){document.getElementById('saveState').innerHTML='<span class="error">'+esc(e.message)+'</span>'}}
async function validateYaml(){try{const d=await api('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:document.getElementById('yamlEditor').value})});document.getElementById('saveState').innerHTML='<span class="ok">Valid YAML · '+d.intersections+' intersection(s)</span>'}catch(e){document.getElementById('saveState').innerHTML='<span class="error">'+esc(e.message)+'</span>'}}
function svgEl(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,v));if(text)e.textContent=text;return e}
function drawNetwork(){if(!model)return;const svg=document.getElementById('networkSvg');svg.innerHTML='';const defs=svgEl('defs');const marker=svgEl('marker',{id:'arrow',viewBox:'0 0 10 10',refX:'9',refY:'5',markerWidth:'7',markerHeight:'7',orient:'auto-start-reverse'});marker.appendChild(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#ff6b6b'}));defs.appendChild(marker);svg.appendChild(defs);const ints=model.intersections.length?model.intersections:[{id:'I1'}];const pos={};ints.forEach((it,i)=>{const x=ints.length===1?600:150+i*(900/Math.max(1,ints.length-1)),y=280;pos[it.id]={x,y};});model.links.forEach(l=>{const a=pos[l.from_intersection_id],b=pos[l.to_intersection_id];if(!a||!b)return;svg.appendChild(svgEl('line',{x1:a.x+95,y1:a.y,x2:b.x-95,y2:b.y,stroke:'#ff6b6b','stroke-width':'18','stroke-linecap':'round',opacity:'.78','marker-end':'url(#arrow)'}));svg.appendChild(svgEl('text',{x:(a.x+b.x)/2,y:a.y-18,'text-anchor':'middle',fill:'#9b2f39','font-size':'13','font-weight':'800'},`${l.id} · ${l.length_m} m · ${l.speed_kmh} km/h`));});ints.forEach((it,i)=>{const {x,y}=pos[it.id];svg.appendChild(svgEl('rect',{x:x-115,y:y-115,width:230,height:230,rx:28,fill:'#d8d2c8'}));svg.appendChild(svgEl('rect',{x:x-115,y:y-37,width:230,height:74,fill:'#39464b'}));svg.appendChild(svgEl('rect',{x:x-37,y:y-115,width:74,height:230,fill:'#39464b'}));['-93,-45 -45,-45','45,-45 93,-45','-93,45 -45,45','45,45 93,45'].forEach(points=>svg.appendChild(svgEl('line',{x1:x+Number(points.split(' ')[0].split(',')[0]),y1:y+Number(points.split(' ')[0].split(',')[1]),x2:x+Number(points.split(' ')[1].split(',')[0]),y2:y+Number(points.split(' ')[1].split(',')[1]),stroke:'#fff4d8','stroke-width':'3','stroke-dasharray':'12 8'})));const moves=model.movements.filter(m=>m.intersection_id===it.id);moves.forEach((m,j)=>{const side=j%4,rank=Math.floor(j/4),off=(rank-1)*12;let x1=x,y1=y,x2=x,y2=y;if(side===0){x1=x-105;y1=y-18+off;x2=x-35;y2=y-18+off}if(side===1){x1=x+18+off;y1=y-105;x2=x+18+off;y2=y-35}if(side===2){x1=x+105;y1=y+18+off;x2=x+35;y2=y+18+off}if(side===3){x1=x-18+off;y1=y+105;x2=x-18+off;y2=y+35}svg.appendChild(svgEl('line',{x1,y1,x2,y2,stroke:['#8bb8ff','#8de4c1','#ffb86b','#c5a3ff'][j%4],'stroke-width':'8','stroke-linecap':'round'}));svg.appendChild(svgEl('text',{x:x1+(side===0?-5:side===2?5:0),y:y1+(side===1?-7:side===3?16:4),'text-anchor':side===0?'end':side===2?'start':'middle',fill:'#263238','font-size':'11','font-weight':'800'},m.id));});svg.appendChild(svgEl('circle',{cx:x,cy:y,r:31,fill:'#ffe66d',stroke:'#263238','stroke-width':'4'}));svg.appendChild(svgEl('text',{x,y:y+5,'text-anchor':'middle','font-size':'16','font-weight':'900',fill:'#263238'},it.id));const c=model.controllers.find(c=>c.intersection_id===it.id);if(c)svg.appendChild(svgEl('text',{x,y:y+145,'text-anchor':'middle','font-size':'13','font-weight':'800',fill:'#59666a'},`${c.id} · ${c.cycle_time_s}s · offset ${c.offset_s||0}s`));});}
async function runModel(mode){switchView('run');document.getElementById('runMode').value=mode;await startRun(mode)}function runSelected(){startRun(document.getElementById('runMode').value)}
async function startRun(mode){try{await saveConfig();await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});pollRun();}catch(e){alert(e.message)}}
async function stopRun(){try{await api('/api/stop',{method:'POST'});}catch(e){alert(e.message)}}
async function pollRun(){try{const s=await api('/api/run');const dot=document.getElementById('statusDot'),txt=document.getElementById('statusText');dot.className='dot'+(s.running?' running':s.return_code!==null&&s.return_code!==0?' failed':'');txt.textContent=s.running?'Running':s.return_code===0?'Completed':s.return_code!==null?'Failed':'Ready';document.getElementById('console').textContent=s.log||'No run started.';document.getElementById('console').scrollTop=1e9;document.getElementById('runButton').disabled=s.running;document.getElementById('runFacts').innerHTML=`<p><b>Elapsed:</b> ${s.elapsed_s}s</p><p><b>Exit code:</b> ${s.return_code??'—'}</p>`;if(!s.running&&s.return_code!==null)loadOutputs();}catch(e){}clearTimeout(runTimer);runTimer=setTimeout(pollRun,1000)}
function switchView(id){document.querySelector(`.nav button[data-view="${id}"]`).click()}
async function loadOutputs(){const d=await api('/api/outputs');document.getElementById('outputCount').textContent=d.files.length+' file(s)';document.getElementById('fileList').innerHTML=d.files.map(f=>`<button class="file ${selectedFile===f.name?'active':''}" onclick="previewFile('${encodeURIComponent(f.name)}','${esc(f.name)}')"><b>${esc(f.name)}</b><small>${fmtBytes(f.size)} · ${f.kind.toUpperCase()}</small></button>`).join('')||'<p>No outputs yet.</p>';}
async function previewFile(encoded,name){selectedFile=name;loadOutputs();const d=await api('/api/output?name='+encoded);const p=document.getElementById('preview');if(d.type==='csv'){const rows=d.rows||[];p.innerHTML=`<div class="toolbar"><b>${esc(name)}</b><a class="btn ghost" href="/download?name=${encoded}">Download</a></div><div class="tablewrap"><table class="data">${rows.map((r,i)=>`<tr>${r.map(c=>i===0?`<th>${esc(c)}</th>`:`<td>${esc(c)}</td>`).join('')}</tr>`).join('')}</table></div>${d.truncated?'<p>Preview limited to 500 rows.</p>':''}`}else if(d.type==='json'){p.innerHTML=`<div class="toolbar"><b>${esc(name)}</b><a class="btn ghost" href="/download?name=${encoded}">Download</a></div><pre class="json">${esc(JSON.stringify(d.data,null,2))}</pre>`}else{p.innerHTML=`<div class="toolbar"><b>${esc(name)}</b><a class="btn ghost" href="/download?name=${encoded}">Download</a></div><pre class="json">${esc(d.text||'Binary file')}</pre>`}}
boot();
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "PySigStudio/4.2"

    def log_message(self, fmt: str, *args) -> None:
        print("UI:", fmt % args)

    def send_json(self, data, status=200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request is too large")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path, query = parsed.path, parse_qs(parsed.query)
            if path == "/":
                raw = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers(); self.wfile.write(raw); return
            if path == "/api/state":
                self.send_json({"config": str(APP["config"].relative_to(ROOT)),
                                "output": str(APP["output"].relative_to(ROOT)),
                                "model": model_summary(load_yaml())}); return
            if path == "/api/configs":
                configs = sorted(str(p.relative_to(ROOT / "configs")).replace(os.sep, "/")
                                 for p in (ROOT / "configs").rglob("*.yaml"))
                selected = str(APP["config"].relative_to(ROOT / "configs")).replace(os.sep, "/")
                self.send_json({"configs": configs, "selected": selected}); return
            if path == "/api/config":
                name = query.get("name", [str(APP["config"].relative_to(ROOT / "configs"))])[0]
                APP["config"] = safe_resolve(ROOT / "configs", name)
                self.send_json({"name": name, "text": read_yaml_text()}); return
            if path == "/api/run": self.send_json(STATE.snapshot()); return
            if path == "/api/outputs": self.send_json({"files": list_outputs()}); return
            if path in ("/api/output", "/download"):
                name = query.get("name", [""])[0]
                file_path = safe_resolve(APP["output"], name)
                if not file_path.is_file(): raise FileNotFoundError(name)
                if path == "/api/output": self.send_json(output_preview(file_path)); return
                raw = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(file_path.name)}")
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            self.send_json({"error": "Not found"}, 404)
        except FileNotFoundError as exc: self.send_json({"error": f"File not found: {exc}"}, 404)
        except Exception as exc: self.send_json({"error": str(exc)}, 400)

    def do_POST(self) -> None:
        try:
            path = urlparse(self.path).path
            if path == "/api/config":
                body = self.read_json(); name = body.get("name", "")
                target = safe_resolve(ROOT / "configs", name)
                text = body.get("text", "")
                data = yaml.safe_load(text)
                if not isinstance(data, dict): raise ValueError("YAML root must be a mapping")
                target.write_text(text, encoding="utf-8")
                APP["config"] = target
                self.send_json({"saved": True, "name": name}); return
            if path == "/api/validate":
                data = yaml.safe_load(self.read_json().get("text", ""))
                if not isinstance(data, dict): raise ValueError("YAML root must be a mapping")
                self.send_json({"valid": True, "intersections": len(data.get("intersections") or [1])}); return
            if path == "/api/run":
                mode = self.read_json().get("mode", "optimise")
                if mode not in ("run", "optimise"): raise ValueError("Mode must be run or optimise")
                start_run(mode); self.send_json({"started": True, "mode": mode}); return
            if path == "/api/stop": self.send_json({"stopped": stop_run()}); return
            self.send_json({"error": "Not found"}, 404)
        except RuntimeError as exc: self.send_json({"error": str(exc)}, 409)
        except Exception as exc: self.send_json({"error": str(exc)}, 400)


def main() -> int:
    parser = argparse.ArgumentParser(description="PySig local browser UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address; keep 127.0.0.1 unless LAN access is required")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    APP["config"] = args.config.resolve()
    APP["output"] = args.output.resolve()
    if not APP["config"].is_file():
        parser.error(f"Config not found: {APP['config']}")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"PySig Studio is running at {url}")
    print("Press Ctrl+C to stop the server.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PySig Studio...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
