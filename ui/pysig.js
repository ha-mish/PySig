"use strict";

const state = {
  model: blankModel(), filename: null, dirty: false, tool: "select", selected: null,
  undo: [], redo: [], commandHistory: [], commandIndex: 0, grid: true, viewBox: {x:0,y:0,w:1400,h:850}, draggingArm:null, panning:null,
};
const pdfState={slot:"LMA",page:1,pages:0,tool:"pan",zoom:1,x:0,y:0,drag:null,points:[],marks:{LMA:[],LMB:[]},metadata:{LMA:{loaded:false},LMB:{loaded:false}}};

function blankModel(){return {model:{id:"Untitled",name:"Untitled model"},calculation:{method:"simulation"},settings:{jurisdiction:"AU-WA",driving_side:"left",pcu_length_m:7.35},intersections:[{id:"I1",name:"Intersection 1",controller_id:"C1",arms:[],movement_ids:[]}],lanes:[],movements:[],network_links:[],routes:[],origin_destination_matrix:{values:{}}};}
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const clone=x=>JSON.parse(JSON.stringify(x));
let latestResults=null;
let movementDrag=null;
function markDirty(value=true){state.dirty=value;$("#saved-state").textContent=value?"UNSAVED":"SAVED";$("#saved-state").style.color=value?"#E7A681":"#BFC9C5";}
function snapshot(){state.undo.push(clone(state.model));if(state.undo.length>50)state.undo.shift();state.redo=[];}
function mutate(fn){snapshot();fn(state.model);markDirty();render();}
function intersection(){return state.model.intersections?.[0];}
function allArms(){return (state.model.intersections||[]).flatMap(i=>(i.arms||[]).map(a=>({...a,intersection_id:i.id})));}
function arm(id){return allArms().find(a=>a.id===id);}
function lane(id){return (state.model.lanes||[]).find(l=>l.id===id);}
function movement(id){return (state.model.movements||[]).find(m=>m.id===id);}
function controllerForIntersection(intersectionId){const i=(state.model.intersections||[]).find(x=>x.id===intersectionId);if(!i)return null;return (state.model.controllers||[]).find(c=>c.id===i.controller_id)||(state.model.controller?.id===i.controller_id?state.model.controller:null);}
function phasesForController(controllerId){return (state.model.phases||[]).filter(p=>(p.controller_id||controllerId)===controllerId);}
function isEntryLane(laneId){const l=lane(laneId),a=l?arm(l.arm_id):null;return (a?.relation||'').toLowerCase()==='entry';}
function movementSignalsForLane(laneId){if(!isEntryLane(laneId))return [];return (state.model.movements||[]).filter(m=>m.from_lane_id===laneId).map(m=>({movement_id:m.id,signal_group_id:m.signal_group_id,movement_type:m.movement_type||'unknown'}));}
function signalGroupsForLane(laneId){return [...new Set(movementSignalsForLane(laneId).map(x=>x.signal_group_id).filter(Boolean))];}
function phaseMembership(signalGroupId,controllerId){return phasesForController(controllerId).filter(p=>(p.active_signal_groups||[]).includes(signalGroupId)).map(p=>p.id);}
function allSignalGroups(){return [...new Set((state.model.movements||[]).filter(m=>isEntryLane(m.from_lane_id)).map(m=>m.signal_group_id).filter(Boolean))].sort();}
function renameSignalGroup(oldId,newId){if(!newId||oldId===newId)return;mutate(model=>{(model.movements||[]).forEach(m=>{if(m.signal_group_id===oldId)m.signal_group_id=newId;});(model.phases||[]).forEach(p=>{p.active_signal_groups=(p.active_signal_groups||[]).map(sg=>sg===oldId?newId:sg);});});}
function toggleSignalGroupPhase(signalGroupId,phaseId,enabled){mutate(model=>{const phase=(model.phases||[]).find(p=>p.id===phaseId);if(!phase)return;phase.active_signal_groups??=[];const set=new Set(phase.active_signal_groups);if(enabled)set.add(signalGroupId);else set.delete(signalGroupId);phase.active_signal_groups=[...set];});}
function log(text,kind=""){const div=document.createElement("div");div.className=kind;div.textContent=text;$("#command-history").append(div);$("#command-history").scrollTop=1e9;}

async function api(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw new Error(d.error||r.statusText);return d;}
function setTool(tool){state.tool=tool;$$('.tool[data-tool]').forEach(b=>b.classList.toggle('active',b.dataset.tool===tool));log(`Tool: ${tool}`);}

function getGeometry(){
  const inter=intersection(),arms=inter?.arms||[],cx=700,cy=425,geom={};
  arms.forEach((a,index)=>{
    const bearing=a.bearing_degrees??([270,180,90,0][index%4]);
    const rad=bearing*Math.PI/180,len=a.visual_length??270;
    // Entry and Exit carriageways are offset to opposite sides of the arm axis.
    const relation=(a.relation||'Entry').toLowerCase();
    const carriagewayOffset=Number(a.carriageway_offset_m??18)*(relation==='entry'?1:-1);
    const perp={x:-Math.sin(rad),y:Math.cos(rad)};
    const base={x:cx+perp.x*carriagewayOffset,y:cy+perp.y*carriagewayOffset};
    geom[a.id]={cx:base.x,cy:base.y,x:base.x+Math.cos(rad)*len,y:base.y+Math.sin(rad)*len,bearing,len,axis:{x:cx,y:cy},carriagewayOffset};
  });return geom;
}
function lanePoint(laneObj,atJunction=true){const g=getGeometry()[laneObj.arm_id];if(!g)return{x:700,y:425};const rad=g.bearing*Math.PI/180,perp={x:-Math.sin(rad),y:Math.cos(rad)};const lanes=(state.model.lanes||[]).filter(l=>l.arm_id===laneObj.arm_id),idx=lanes.findIndex(l=>l.id===laneObj.id),off=(idx-(lanes.length-1)/2)*12;const base=atJunction?{x:g.cx+Math.cos(rad)*45,y:g.cy+Math.sin(rad)*45}:{x:g.x,y:g.y};return{x:base.x+perp.x*off,y:base.y+perp.y*off};}

function svg(tag,attrs={},text=""){const e=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text)e.textContent=text;return e;}
function lanePoint(laneObj,atJunction=true){const g=getGeometry()[laneObj.arm_id];if(!g)return {x:700,y:425};const rad=g.bearing*Math.PI/180;const perp={x:-Math.sin(rad),y:Math.cos(rad)};const lanes=(state.model.lanes||[]).filter(l=>l.arm_id===laneObj.arm_id);const idx=lanes.findIndex(l=>l.id===laneObj.id);const off=(idx-(lanes.length-1)/2)*12;const base=atJunction?{x:g.cx+Math.cos(rad)*45,y:g.cy+Math.sin(rad)*45}:{x:g.x,y:g.y};return {x:base.x+perp.x*off,y:base.y+perp.y*off};}
function lanePolygon(laneObj){const g=getGeometry()[laneObj.arm_id];if(!g)return null;const all=(state.model.lanes||[]).filter(l=>l.arm_id===laneObj.arm_id);const idx=all.findIndex(l=>l.id===laneObj.id);const n=Math.max(1,all.length);const width=50/n;const rad=g.bearing*Math.PI/180,perp={x:-Math.sin(rad),y:Math.cos(rad)},dir={x:Math.cos(rad),y:Math.sin(rad)};const offset=(idx-(n-1)/2)*width;const half=width/2-1;const inner=40,outer=g.len;const c1={x:g.cx+dir.x*inner+perp.x*offset,y:g.cy+dir.y*inner+perp.y*offset},c2={x:g.cx+dir.x*outer+perp.x*offset,y:g.cy+dir.y*outer+perp.y*offset};return [{x:c1.x+perp.x*half,y:c1.y+perp.y*half},{x:c2.x+perp.x*half,y:c2.y+perp.y*half},{x:c2.x-perp.x*half,y:c2.y-perp.y*half},{x:c1.x-perp.x*half,y:c1.y-perp.y*half}];}
function centroid(points){return {x:points.reduce((a,p)=>a+p.x,0)/points.length,y:points.reduce((a,p)=>a+p.y,0)/points.length};}
function resultForLane(id){return latestResults?.lanes?.find?.(x=>x.lane_id===id)||null;}
function render(){
  const layer=$("#model-layer");layer.innerHTML="";const inter=intersection(),arms=inter?.arms||[],geom=getGeometry();$("#blank-prompt").classList.toggle("hidden",arms.length>0);$("#document-name").textContent=state.model.model?.name||"Untitled";$("#status-model").textContent=`${arms.length} ARMS · ${(state.model.lanes||[]).length} LANES · ${(state.model.movements||[]).length} MOVEMENTS`;
  arms.forEach(a=>{const g=geom[a.id];const bed=svg("line",{x1:g.cx,y1:g.cy,x2:g.x,y2:g.y,class:"road-bed","data-type":"arm","data-id":a.id});bed.addEventListener('click',ev=>{ev.stopPropagation();selectObject('arm',a.id)});layer.append(bed);if(state.tool==='geometry'){const h=svg('circle',{cx:g.x,cy:g.y,r:10,class:'geometry-handle','data-arm-handle':a.id});h.addEventListener('pointerdown',ev=>beginArmDrag(ev,a.id));layer.append(h);}});
  if(arms.length)layer.append(svg("circle",{cx:700,cy:425,r:43,class:"junction-core"}));
  (state.model.lanes||[]).forEach(l=>{const poly=lanePolygon(l);if(!poly)return;const a=arm(l.arm_id);const points=poly.map(p=>`${p.x},${p.y}`).join(' ');const cls=`lane-band ${(a?.relation||'').toLowerCase()} ${state.selected?.type==='lane'&&state.selected.id===l.id?'selected':''}`;const shape=svg("polygon",{points,class:cls,"data-type":"lane","data-id":l.id});shape.addEventListener('click',ev=>{ev.stopPropagation();selectObject('lane',l.id)});shape.addEventListener('pointerdown',ev=>beginMovementDrag(ev,l.id));layer.append(shape);const c=centroid(poly);const aa=arm(l.arm_id);const arrow=(aa?.relation||'Entry')==='Entry'?'◀':'▶';layer.append(svg('text',{x:c.x,y:c.y-12,class:'lane-direction','text-anchor':'middle'},arrow));if(state.tool==='signal'&&isEntryLane(l.id)){const dot=svg('circle',{cx:lanePoint(l,true).x,cy:lanePoint(l,true).y,r:7,class:`signal-dot ${state.selected?.type==='lane'&&state.selected.id===l.id?'selected':''}`});dot.addEventListener('click',ev=>{ev.stopPropagation();selectObject('lane',l.id)});layer.append(dot);}const c2=c;layer.append(svg('text',{x:c2.x,y:c2.y,class:'lane-label','text-anchor':'middle'},l.id));const rr=resultForLane(l.id);if(rr)layer.append(svg('text',{x:c2.x,y:c2.y+15,class:'lane-result','text-anchor':'middle'},`Q ${Number(rr.maximum_queue_pcu||0).toFixed(1)} · D ${Number(rr.mean_delay_seconds_per_pcu||0).toFixed(1)}s · x ${Number(rr.simulated_degree_of_saturation||0).toFixed(2)}`));});
  arms.forEach(a=>{const g=geom[a.id],lx=g.x+Math.cos(g.bearing*Math.PI/180)*30,ly=g.y+Math.sin(g.bearing*Math.PI/180)*30;layer.append(svg('text',{x:lx,y:ly,class:'arm-label','text-anchor':'middle'},a.name||a.id));layer.append(svg('text',{x:lx,y:ly+15,class:'arm-sub','text-anchor':'middle'},`${a.id} · ${a.direction||''} · ${a.relation||''}`));});
  (state.model.movements||[]).forEach(m=>{const from=lane(m.from_lane_id),to=lane(m.to_lane_id);if(!from||!to)return;const a=lanePoint(from,true),b=lanePoint(to,true),mx=(a.x+b.x)/2,my=(a.y+b.y)/2-45;const e=svg('path',{d:`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`,class:'movement-line','data-type':'movement','data-id':m.id});e.addEventListener('click',ev=>{ev.stopPropagation();selectObject('movement',m.id)});layer.append(e);});renderInspector();
}
function pointerXY(ev){const r=$("#canvas").getBoundingClientRect(),v=state.viewBox;return{x:v.x+(ev.clientX-r.left)/r.width*v.w,y:v.y+(ev.clientY-r.top)/r.height*v.h};}
function applyView(){const v=state.viewBox;$("#canvas").setAttribute("viewBox",`${v.x} ${v.y} ${v.w} ${v.h}`);}
function zoom(factor,anchor={x:700,y:425}){const v=state.viewBox,nw=Math.max(250,Math.min(3500,v.w*factor)),nh=nw*850/1400,rx=(anchor.x-v.x)/v.w,ry=(anchor.y-v.y)/v.h;state.viewBox={x:anchor.x-rx*nw,y:anchor.y-ry*nh,w:nw,h:nh};applyView();log(`Zoom ${Math.round(1400/nw*100)}%`);}
function fitView(){state.viewBox={x:0,y:0,w:1400,h:850};applyView();log("Fit model to view");}
function beginArmDrag(ev,armId){if(state.tool!=='geometry')return;ev.preventDefault();ev.stopPropagation();snapshot();state.draggingArm={id:armId};window.addEventListener('pointermove',dragArm);window.addEventListener('pointerup',endArmDrag,{once:true});}
function dragArm(ev){if(!state.draggingArm)return;const p=pointerXY(ev),a=state.model.intersections[0].arms.find(x=>x.id===state.draggingArm.id),dx=p.x-700,dy=p.y-425;a.bearing_degrees=Math.round(Math.atan2(dy,dx)*180/Math.PI);a.visual_length=Math.max(100,Math.round(Math.hypot(dx,dy)));markDirty();render();}
function endArmDrag(){window.removeEventListener('pointermove',dragArm);state.draggingArm=null;render();}
function beginPan(ev){if(state.tool!=='pan')return;ev.preventDefault();state.panning={x:ev.clientX,y:ev.clientY,view:{...state.viewBox}};window.addEventListener('pointermove',panMove);window.addEventListener('pointerup',endPan,{once:true});}
function panMove(ev){if(!state.panning)return;const rect=$("#canvas").getBoundingClientRect(),dx=(ev.clientX-state.panning.x)/rect.width*state.panning.view.w,dy=(ev.clientY-state.panning.y)/rect.height*state.panning.view.h;state.viewBox={...state.panning.view,x:state.panning.view.x-dx,y:state.panning.view.y-dy};applyView();}
function endPan(){window.removeEventListener('pointermove',panMove);state.panning=null;}
function beginMovementDrag(ev,laneId){if(state.tool!=="movement")return;ev.preventDefault();ev.stopPropagation();movementDrag={from:laneId,start:lanePoint(lane(laneId),true)};const preview=svg('path',{id:'movement-preview',class:'drag-preview'});$('#interaction-layer').append(preview);window.addEventListener('pointermove',dragMovement);window.addEventListener('pointerup',endMovement,{once:true});}
function dragMovement(ev){if(!movementDrag)return;const p=pointerXY(ev),a=movementDrag.start,mx=(a.x+p.x)/2,my=(a.y+p.y)/2-35;$('#movement-preview')?.setAttribute('d',`M ${a.x} ${a.y} Q ${mx} ${my} ${p.x} ${p.y}`);}
function endMovement(ev){window.removeEventListener('pointermove',dragMovement);const target=document.elementFromPoint(ev.clientX,ev.clientY)?.closest?.('[data-type="lane"]');const from=movementDrag?.from,to=target?.dataset?.id;movementDrag=null;$('#movement-preview')?.remove();if(from&&to&&from!==to){addMovement(from,to);setTool('select');}}

function selectObject(type,id){state.selected={type,id};render();}
function field(label,value,key,type="text",options=null){const row=document.createElement("div");row.className="property-row";const lab=document.createElement("label");lab.textContent=label;let input;if(options){input=document.createElement("select");options.forEach(o=>{const opt=document.createElement("option");opt.value=o;opt.textContent=o;input.append(opt);});input.value=value??"";}else{input=document.createElement("input");input.type=type;input.value=value??"";}input.addEventListener("change",()=>updateSelected(key,type==='number'?Number(input.value):input.value));row.append(lab,input);return row;}
function group(title,fields){const g=document.createElement("section");g.className="property-group";const h=document.createElement("h3");h.textContent=title;g.append(h,...fields);return g;}
function openPhaseDialog(intersectionId){
  const ctl=controllerForIntersection(intersectionId);if(!ctl){log('No controller defined for this intersection','error');return;}
  $('#phase-controller-label').textContent=`${ctl.id} · ${ctl.cycle_time_s}s cycle`;
  renderPhaseDialog(ctl.id);$('#phase-dialog').classList.remove('hidden');
}
function renderPhaseDialog(controllerId){
  const host=$('#phase-list');host.innerHTML='';const phases=phasesForController(controllerId);const groups=allSignalGroups();
  phases.forEach((phase,index)=>{const row=document.createElement('article');row.className='phase-row';row.dataset.phaseId=phase.id;
    const head=document.createElement('div');head.className='phase-row-head';head.innerHTML=`<b>${phase.id}</b><span>Phase ${index+1}</span>`;const del=document.createElement('button');del.textContent='×';del.title='Delete phase';del.onclick=()=>deletePhase(phase.id);head.append(del);row.append(head);
    const grid=document.createElement('div');grid.className='phase-fields';
    const phaseId=document.createElement('input');phaseId.value=phase.id;phaseId.dataset.prop='id';
    const duration=document.createElement('input');duration.type='number';duration.step='1';duration.value=phase.duration_s??0;duration.dataset.prop='duration_s';
    const intergreen=document.createElement('input');intergreen.type='number';intergreen.step='1';intergreen.value=phase.intergreen_after_s??0;intergreen.dataset.prop='intergreen_after_s';
    [['ID',phaseId],['Duration s',duration],['Intergreen s',intergreen]].forEach(([lab,input])=>{const wrap=document.createElement('label');wrap.innerHTML=`<span>${lab}</span>`;wrap.append(input);grid.append(wrap);});row.append(grid);
    const sg=document.createElement('div');sg.className='phase-signal-groups';const title=document.createElement('b');title.textContent='ACTIVE SIGNAL GROUPS';sg.append(title);if(!groups.length){const none=document.createElement('em');none.textContent='Create movements and signal groups first.';sg.append(none);}else groups.forEach(groupId=>{const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.value=groupId;check.checked=(phase.active_signal_groups||[]).includes(groupId);label.append(check,document.createTextNode(groupId));sg.append(label);});row.append(sg);host.append(row);
  });
  if(!phases.length)host.innerHTML='<div class="phase-empty">No phases defined. Add the first phase.</div>';
}
function addPhase(){const ctl=controllerForIntersection(intersection()?.id);if(!ctl)return;mutate(model=>{model.phases??=[];const existing=phasesForController(ctl.id).length;model.phases.push({id:`P_${String.fromCharCode(65+existing)}`,controller_id:ctl.id,active_signal_groups:[],duration_s:10,intergreen_after_s:5});});renderPhaseDialog(ctl.id);}
function deletePhase(phaseId){const ctl=controllerForIntersection(intersection()?.id);mutate(model=>{model.phases=(model.phases||[]).filter(p=>p.id!==phaseId);});renderPhaseDialog(ctl?.id);}
function applyPhaseDialog(){const ctl=controllerForIntersection(intersection()?.id);if(!ctl)return;const rows=[...document.querySelectorAll('.phase-row')];const replacements=rows.map(row=>{const oldId=row.dataset.phaseId;const values={};row.querySelectorAll('[data-prop]').forEach(input=>values[input.dataset.prop]=input.type==='number'?Number(input.value):input.value.trim());const active=[...row.querySelectorAll('.phase-signal-groups input:checked')].map(x=>x.value);return {oldId,phase:{id:values.id||oldId,controller_id:ctl.id,active_signal_groups:active,duration_s:values.duration_s,intergreen_after_s:values.intergreen_after_s}};});
  mutate(model=>{const other=(model.phases||[]).filter(p=>(p.controller_id||ctl.id)!==ctl.id);model.phases=[...other,...replacements.map(x=>x.phase)];if(model.phase_sequences){Object.values(model.phase_sequences).forEach(seq=>{if(seq.controller_id===ctl.id)seq.phase_ids=replacements.map(x=>x.phase.id);});}});$('#phase-dialog').classList.add('hidden');log(`Updated ${replacements.length} phases for ${ctl.id}`,'success');
}
function renderInspector(){const box=$("#inspector-content");box.innerHTML="";if(!state.selected){box.innerHTML='<div class="empty-inspector">Select an arm, lane or movement.</div>';return;}let obj;if(state.selected.type==='arm')obj=arm(state.selected.id);if(state.selected.type==='lane')obj=lane(state.selected.id);if(state.selected.type==='movement')obj=movement(state.selected.id);if(!obj){state.selected=null;return renderInspector();}
  box.append(group("IDENTIFICATION",[field("ID",obj.id,"id"),field("Name",obj.name,"name")]));
  if(state.selected.type==='lane'){
    const laneArm=arm(obj.arm_id);
    if((laneArm?.relation||'').toLowerCase()==='entry'){
      const ctl=controllerForIntersection(obj.intersection_id);
      const signals=movementSignalsForLane(obj.id);
      const groups=[...new Set(signals.map(x=>x.signal_group_id).filter(Boolean))];
      const sig=group("SIGNAL CONTROL",[]);
      const summary=document.createElement('div');summary.className='signal-summary';summary.innerHTML=`<div><span>Controller</span><b>${ctl?.id||'—'}</b></div><div><span>Cycle</span><b>${ctl?.cycle_time_s??'—'} s</b></div><div><span>Offset</span><b>${ctl?.offset_s??0} s</b></div>`;sig.append(summary);const editPhases=document.createElement('button');editPhases.className='edit-phases';editPhases.textContent='EDIT PHASE DEFINITIONS';editPhases.onclick=()=>openPhaseDialog(obj.intersection_id);sig.append(editPhases);
      if(!signals.length){const none=document.createElement('div');none.className='signal-none';none.textContent='No signal-controlled movements leave this entry lane.';sig.append(none);}else{
        groups.forEach(sg=>{
          const card=document.createElement('div');card.className='signal-card';
          const header=document.createElement('header');const dot=document.createElement('i');const idInput=document.createElement('input');idInput.className='signal-id-input';idInput.value=sg;idInput.title='Rename signal group';idInput.addEventListener('change',()=>renameSignalGroup(sg,idInput.value.trim()));header.append(dot,idInput);card.append(header);
          const members=signals.filter(x=>x.signal_group_id===sg);const moveLine=document.createElement('div');moveLine.innerHTML=`<span>Movements</span><strong>${members.map(x=>x.movement_id).join(', ')}</strong>`;card.append(moveLine);
          const phaseBox=document.createElement('div');phaseBox.className='phase-membership';const label=document.createElement('span');label.textContent='Active phases';phaseBox.append(label);
          const choices=document.createElement('section');choices.className='phase-checks';phasesForController(ctl?.id).forEach(ph=>{const item=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=(ph.active_signal_groups||[]).includes(sg);check.addEventListener('change',()=>toggleSignalGroupPhase(sg,ph.id,check.checked));item.append(check,document.createTextNode(ph.id));choices.append(item);});phaseBox.append(choices);card.append(phaseBox);sig.append(card);
        });
      }
      box.append(sig);
    } else {
      const info=group("SIGNAL CONTROL",[]);const note=document.createElement('div');note.className='signal-none';note.textContent='Exit lane — signal controls are defined on entry lanes only.';info.append(note);box.append(info);
    }
  }
  if(state.selected.type==='lane'){const r=resultForLane(obj.id);if(r){const res=group("ANALYSIS",[]);[["Demand",r.demand_pcu_per_hour],["Capacity",r.simulated_service_capacity_pcu_per_hour],["DoS",r.simulated_degree_of_saturation],["Max queue PCU",r.maximum_queue_pcu],["Max queue m",r.maximum_queue_m],["Delay s/PCU",r.mean_delay_seconds_per_pcu],["LOS",r.level_of_service]].forEach(([k,v])=>{const d=document.createElement('div');d.className='metric';d.innerHTML=`<span>${k}</span><b>${typeof v==='number'?v.toFixed(2):(v??'—')}</b>`;res.append(d);});box.append(res);}}
  if(state.selected.type==='arm')box.append(group("GEOMETRY",[field("Direction",obj.direction,"direction"),field("Relation",obj.relation,"relation","text",["Entry","Exit"]),field("Bearing °",obj.bearing_degrees??0,"bearing_degrees","number"),field("Length",obj.visual_length??270,"visual_length","number"),field("Road offset",obj.carriageway_offset_m??18,"carriageway_offset_m","number")]));
  if(state.selected.type==='lane')box.append(group("LANE",[field("Arm",obj.arm_id,"arm_id","text",allArms().map(a=>a.id)),field("Length m",obj.physical_length_m??100,"physical_length_m","number"),field("Parent",obj.parent_lane_id??"","parent_lane_id")]));
  if(state.selected.type==='movement')box.append(group("MOVEMENT",[field("From lane",obj.from_lane_id,"from_lane_id","text",(state.model.lanes||[]).map(l=>l.id)),field("To lane",obj.to_lane_id,"to_lane_id","text",(state.model.lanes||[]).map(l=>l.id)),field("Type",obj.movement_type,"movement_type","text",["through","left","right","u_turn","unknown"]),field("Signal group",obj.signal_group_id,"signal_group_id")]));
  if(state.selected.type==='movement'){
    const ctl=controllerForIntersection(obj.intersection_id);const originEntry=isEntryLane(obj.from_lane_id);const sig=group("SIGNAL CONTROL",[]);const phaseButton=document.createElement('button');phaseButton.className='edit-phases';phaseButton.textContent='EDIT PHASE DEFINITIONS';phaseButton.onclick=()=>openPhaseDialog(obj.intersection_id);sig.append(phaseButton);
    if(!originEntry){const note=document.createElement('div');note.className='signal-none';note.textContent='Movement origin is not an Entry arm; signal editing is disabled.';sig.append(note);}else{
      const sg=obj.signal_group_id||'';const card=document.createElement('div');card.className='signal-card';const header=document.createElement('header'),dot=document.createElement('i'),input=document.createElement('input');input.className='signal-id-input';input.value=sg;input.addEventListener('change',()=>updateSelected('signal_group_id',input.value.trim()));header.append(dot,input);card.append(header);
      const ctrl=document.createElement('div');ctrl.innerHTML=`<span>Controller</span><strong>${ctl?.id||'—'}</strong>`;card.append(ctrl);
      const choices=document.createElement('section');choices.className='phase-checks';phasesForController(ctl?.id).forEach(ph=>{const item=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=(ph.active_signal_groups||[]).includes(sg);check.addEventListener('change',()=>toggleSignalGroupPhase(sg,ph.id,check.checked));item.append(check,document.createTextNode(ph.id));choices.append(item);});card.append(choices);sig.append(card);
    }box.append(sig);
  }
  const del=document.createElement("button");del.className="delete-object";del.textContent="DELETE OBJECT";del.onclick=deleteSelected;box.append(del);
}
function updateSelected(key,value){mutate(model=>{let obj;if(state.selected.type==='arm')obj=(model.intersections[0].arms||[]).find(a=>a.id===state.selected.id);if(state.selected.type==='lane')obj=model.lanes.find(l=>l.id===state.selected.id);if(state.selected.type==='movement')obj=model.movements.find(m=>m.id===state.selected.id);if(!obj)return;const old=obj.id;obj[key]=value;if(key==='id'){state.selected.id=value;if(state.selected.type==='arm')(model.lanes||[]).forEach(l=>{if(l.arm_id===old)l.arm_id=value});if(state.selected.type==='lane')(model.movements||[]).forEach(m=>{if(m.from_lane_id===old)m.from_lane_id=value;if(m.to_lane_id===old)m.to_lane_id=value});}});}
function deleteSelected(){const sel=state.selected;if(!sel)return;mutate(model=>{if(sel.type==='arm'){model.intersections[0].arms=model.intersections[0].arms.filter(a=>a.id!==sel.id);model.lanes=model.lanes.filter(l=>l.arm_id!==sel.id);}if(sel.type==='lane'){model.lanes=model.lanes.filter(l=>l.id!==sel.id);model.movements=model.movements.filter(m=>m.from_lane_id!==sel.id&&m.to_lane_id!==sel.id);}if(sel.type==='movement')model.movements=model.movements.filter(m=>m.id!==sel.id);});state.selected=null;render();}

function addArm(x=900,y=425){const i=intersection();const cx=700,cy=425;const deg=Math.atan2(y-cy,x-cx)*180/Math.PI;const id=`A${(i.arms||[]).length+1}`;mutate(m=>{m.intersections[0].arms??=[];m.intersections[0].arms.push({id,name:`Arm ${id.slice(1)}`,direction:"",relation:"Entry",bearing_degrees:Math.round(deg),visual_length:Math.round(Math.hypot(x-cx,y-cy))});});selectObject('arm',id);}
function addLane(armId){const lanes=(state.model.lanes||[]).filter(l=>l.arm_id===armId);const id=`${armId}_${lanes.length+1}`;mutate(m=>{m.lanes??=[];m.lanes.push({id,intersection_id:intersection().id,arm_id:armId,physical_length_m:100,saturation_flow:{method:"direct",value_pcu_per_hour:1900}});});selectObject('lane',id);}
function addMovement(fromId,toId){const id=`M_${fromId}_${toId}`.replace(/[^A-Za-z0-9_]/g,"_");mutate(m=>{m.movements??=[];m.movements.push({id,intersection_id:intersection().id,from_lane_id:fromId,to_lane_id:toId,movement_type:"unknown",signal_group_id:"SG1",free_flow_time_s:0});m.intersections[0].movement_ids??=[];m.intersections[0].movement_ids.push(id);});selectObject('movement',id);}

async function save(filename=null){if(filename)state.filename=filename;const payload={model:state.model,filename:state.filename};const d=await api('/api/model',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});state.filename=d.filename;markDirty(false);log(`Saved ${d.filename}`,'success');}
async function openModel(name){const d=await api(`/api/open?name=${encodeURIComponent(name)}`);state.model=d.model;state.filename=name;state.selected=null;state.undo=[];markDirty(false);render();log(`Opened ${name}`,'success');}
function newModel(){state.model=blankModel();state.filename=null;state.selected=null;state.undo=[];state.redo=[];markDirty(false);render();log("New blank model",'success');}
async function showOpen(){const d=await api('/api/configs');$("#config-list").innerHTML=d.configs.map(x=>`<option>${x}</option>`).join('');$("#open-dialog").classList.remove('hidden');}
function command(text){const p=text.trim().split(/\s+/);const cmd=(p.shift()||'').toUpperCase();if(!cmd)return;state.commandHistory.push(text);state.commandIndex=state.commandHistory.length;log(`> ${text}`);try{if(cmd==='HELP'){log('HELP · ARM ADD [bearing] · ARM LIST · LANE ADD <arm> · MOVEMENT ADD <from> <to> · SELECT <id> · SET <property> <value> · SAVE · RUN · OPTIMISE','success');return;}if(cmd==='ARM'&&p[0]?.toUpperCase()==='ADD'){const bearing=Number(p[1]??0);const rad=bearing*Math.PI/180;addArm(700+Math.cos(rad)*270,425+Math.sin(rad)*270);return;}if(cmd==='ARM'&&p[0]?.toUpperCase()==='LIST'){allArms().forEach(a=>log(`${a.id}  ${a.name}  ${a.direction}  ${a.relation}`));return;}if(cmd==='LANE'&&p[0]?.toUpperCase()==='ADD'){if(!arm(p[1]))throw Error(`Unknown arm ${p[1]}`);addLane(p[1]);return;}if(cmd==='MOVEMENT'&&p[0]?.toUpperCase()==='ADD'){if(!lane(p[1])||!lane(p[2]))throw Error('MOVEMENT ADD requires valid from and to lanes');addMovement(p[1],p[2]);return;}if(cmd==='SELECT'){const id=p[0];if(arm(id))selectObject('arm',id);else if(lane(id))selectObject('lane',id);else if(movement(id))selectObject('movement',id);else throw Error(`Unknown object ${id}`);return;}if(cmd==='SET'){if(!state.selected)throw Error('Select an object first');updateSelected(p[0],p.slice(1).join(' '));return;}if(cmd==='SAVE'){if(state.filename)save();else $("#save-dialog").classList.remove('hidden');return;}if(cmd==='RUN'){startCalculation('run');return;}if(cmd==='OPTIMISE'){startCalculation('optimise');return;}throw Error(`Unknown command: ${cmd}`);}catch(e){log(e.message,'error');}}
async function startCalculation(mode){if(state.dirty){if(!state.filename){$("#save-dialog").classList.remove('hidden');log('Save the model before calculation','error');return;}await save();}await api('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});$("#run-drawer").classList.remove('hidden');pollRun();}
async function pollRun(){const r=await api('/api/run');$("#run-log").textContent=r.log;$("#run-log").scrollTop=1e9;$("#calculation-status").textContent=r.running?`RUNNING ${r.elapsed_s}s`:r.return_code===0?'COMPLETE':r.return_code==null?'READY':'FAILED';if(r.running)setTimeout(pollRun,700);else if(r.return_code===0)loadLatestResults();}

async function loadLatestResults(){try{latestResults=await api('/api/output?name=results.json');render();}catch(_){latestResults=null;}}
function undo(){if(!state.undo.length)return;state.redo.push(clone(state.model));state.model=state.undo.pop();markDirty();render();}
function redo(){if(!state.redo.length)return;state.undo.push(clone(state.model));state.model=state.redo.pop();markDirty();render();}
async function validateModel(){const d=await api('/api/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:state.model})});if(d.valid)log('Model validation passed','success');else d.errors.forEach(x=>log(x,'error'));}

function handleAction(action){if(action==='new')newModel();if(action==='open')showOpen();if(action==='save')state.filename?save():$('#save-dialog').classList.remove('hidden');if(action==='undo')undo();if(action==='redo')redo();if(action==='zoom-in')zoom(0.8);if(action==='zoom-out')zoom(1.25);if(action==='fit')fitView();if(action==='validate')validateModel();if(action==='grid'){state.grid=!state.grid;$('#grid').style.display=state.grid?'block':'none';$('#status-grid').textContent=state.grid?'GRID 20 m':'GRID OFF';}}

function showModelWorkspace(){
  $('#pdf-workspace').classList.add('hidden');$('#canvas').classList.remove('hidden');$('#blank-prompt').classList.toggle('hidden',(intersection()?.arms||[]).length>0);$$('.doc-tab').forEach(x=>x.classList.toggle('active',!x.dataset.pdfSlot));
}
async function showPdfWorkspace(slot){
  pdfState.slot=slot;$('#pdf-workspace').classList.remove('hidden');$('#canvas').classList.add('hidden');$('#blank-prompt').classList.add('hidden');$$('.doc-tab').forEach(x=>x.classList.toggle('active',x.dataset.pdfSlot===slot));$('#pdf-slot-label').textContent=slot;await loadPdfState();renderPdf();
}
async function loadPdfState(){const data=await api('/api/pdf/state');pdfState.metadata=data;const meta=data[pdfState.slot]||{loaded:false};pdfState.pages=meta.pages||0;pdfState.page=Math.min(Math.max(1,pdfState.page),Math.max(1,pdfState.pages));}
function setPdfTool(tool){pdfState.tool=tool;pdfState.points=[];$$('[data-pdf-tool]').forEach(b=>b.classList.toggle('active',b.dataset.pdfTool===tool));$('#pdf-tool-label').textContent=tool.toUpperCase();}
function applyPdfTransform(){const sheet=$('#pdf-sheet');sheet.style.transform=`translate(${pdfState.x}px,${pdfState.y}px) scale(${pdfState.zoom})`;$('#pdf-zoom-label').textContent=`${Math.round(pdfState.zoom*100)}%`;}
function renderPdf(){const meta=pdfState.metadata[pdfState.slot]||{loaded:false};$('.pdf-empty').classList.toggle('hidden',meta.loaded);$('#pdf-sheet').classList.toggle('hidden',!meta.loaded);$('#pdf-page-label').textContent=`Page ${meta.loaded?pdfState.page:0} / ${meta.pages||0}`;$('#pdf-scale-label').textContent=meta.scale_m_per_px?`SCALE ${Number(meta.scale_m_per_px).toFixed(6)} m/px`:'SCALE NOT CALIBRATED';if(meta.loaded){$('#pdf-image').src=`/api/pdf/page?slot=${pdfState.slot}&page=${pdfState.page}&t=${Date.now()}`;$('#pdf-image').onload=()=>{const img=$('#pdf-image'),overlay=$('#pdf-overlay');overlay.setAttribute('viewBox',`0 0 ${img.naturalWidth} ${img.naturalHeight}`);overlay.setAttribute('width',img.naturalWidth);overlay.setAttribute('height',img.naturalHeight);renderPdfMarks();fitPdf();};}else renderPdfMarks();}
function fitPdf(){const img=$('#pdf-image'),stage=$('#pdf-stage');if(!img.naturalWidth)return;const rect=stage.getBoundingClientRect();pdfState.zoom=Math.min((rect.width-40)/img.naturalWidth,(rect.height-40)/img.naturalHeight);pdfState.x=(rect.width-img.naturalWidth*pdfState.zoom)/2;pdfState.y=(rect.height-img.naturalHeight*pdfState.zoom)/2;applyPdfTransform();}
function pdfPoint(ev){const sheet=$('#pdf-sheet').getBoundingClientRect(),img=$('#pdf-image');return{x:(ev.clientX-sheet.left)/sheet.width*img.naturalWidth,y:(ev.clientY-sheet.top)/sheet.height*img.naturalHeight};}
function distance(a,b){return Math.hypot(b.x-a.x,b.y-a.y);}
function addSvg(tag,attrs,text=''){const e=svg(tag,attrs,text);$('#pdf-overlay').append(e);return e;}
function renderPdfMarks(){const o=$('#pdf-overlay');o.innerHTML='';(pdfState.marks[pdfState.slot]||[]).filter(m=>m.page===pdfState.page).forEach(mark=>{if(mark.type==='distance'||mark.type==='calibration'){addSvg('line',{x1:mark.a.x,y1:mark.a.y,x2:mark.b.x,y2:mark.b.y,class:mark.type==='calibration'?'calibration-line':'measurement-line'});addSvg('circle',{cx:mark.a.x,cy:mark.a.y,r:5,class:'measurement-point'});addSvg('circle',{cx:mark.b.x,cy:mark.b.y,r:5,class:'measurement-point'});addSvg('text',{x:(mark.a.x+mark.b.x)/2,y:(mark.a.y+mark.b.y)/2-8,class:'measurement-text','text-anchor':'middle'},mark.label);}if(mark.type==='angle'){addSvg('polyline',{points:`${mark.a.x},${mark.a.y} ${mark.b.x},${mark.b.y} ${mark.c.x},${mark.c.y}`,class:'angle-line',fill:'none'});addSvg('text',{x:mark.b.x+10,y:mark.b.y-10,class:'measurement-text'},mark.label);}});}
async function uploadPdf(file){if(!file)return;const reader=new FileReader();reader.onload=async()=>{try{log(`Rendering ${file.name} as ${pdfState.slot}...`);const meta=await api('/api/pdf/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:pdfState.slot,filename:file.name,data:reader.result})});pdfState.metadata[pdfState.slot]=meta;pdfState.page=1;pdfState.zoom=1;pdfState.x=0;pdfState.y=0;renderPdf();log(`Loaded ${file.name} (${meta.pages} pages)`,'success');}catch(e){log(e.message,'error');}};reader.readAsDataURL(file);}
async function completePdfMeasurement(){const points=pdfState.points,meta=pdfState.metadata[pdfState.slot];if(pdfState.tool==='calibrate'&&points.length===2){const px=distance(points[0],points[1]);const input=prompt('Known distance in metres:','10');const metres=Number(input);if(!(metres>0)){pdfState.points=[];return;}meta.scale_m_per_px=metres/px;meta.calibration_distance_m=metres;await api('/api/pdf/metadata',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slot:pdfState.slot,scale_m_per_px:meta.scale_m_per_px,calibration_distance_m:metres})});pdfState.marks[pdfState.slot].push({type:'calibration',page:pdfState.page,a:points[0],b:points[1],label:`CAL ${metres.toFixed(2)} m`});$('#pdf-measurement-label').textContent=`Calibration ${metres.toFixed(2)} m`;pdfState.points=[];renderPdfMarks();renderPdf();}
else if(pdfState.tool==='distance'&&points.length===2){const px=distance(points[0],points[1]),metres=meta.scale_m_per_px?px*meta.scale_m_per_px:null,label=metres?`${metres.toFixed(2)} m`:`${px.toFixed(1)} px`;pdfState.marks[pdfState.slot].push({type:'distance',page:pdfState.page,a:points[0],b:points[1],label});$('#pdf-measurement-label').textContent=label;pdfState.points=[];renderPdfMarks();}
else if(pdfState.tool==='angle'&&points.length===3){const u={x:points[0].x-points[1].x,y:points[0].y-points[1].y},v={x:points[2].x-points[1].x,y:points[2].y-points[1].y};const cos=(u.x*v.x+u.y*v.y)/(Math.hypot(u.x,u.y)*Math.hypot(v.x,v.y));const deg=Math.acos(Math.max(-1,Math.min(1,cos)))*180/Math.PI,label=`${deg.toFixed(1)}°`;pdfState.marks[pdfState.slot].push({type:'angle',page:pdfState.page,a:points[0],b:points[1],c:points[2],label});$('#pdf-measurement-label').textContent=label;pdfState.points=[];renderPdfMarks();}}
function bindPdf(){
  $$('.doc-tab').forEach(tab=>tab.addEventListener('click',()=>tab.dataset.pdfSlot?showPdfWorkspace(tab.dataset.pdfSlot):showModelWorkspace()));
  $('#pdf-upload').onclick=()=>$('#pdf-file').click();$('#pdf-file').onchange=e=>uploadPdf(e.target.files[0]);$$('[data-pdf-tool]').forEach(b=>b.onclick=()=>setPdfTool(b.dataset.pdfTool));$('#pdf-clear').onclick=()=>{pdfState.marks[pdfState.slot]=[];renderPdfMarks();};
  $('#pdf-prev').onclick=()=>{if(pdfState.page>1){pdfState.page--;renderPdf();}};$('#pdf-next').onclick=()=>{if(pdfState.page<pdfState.pages){pdfState.page++;renderPdf();}};$('#pdf-zoom-in').onclick=()=>{pdfState.zoom*=1.2;applyPdfTransform();};$('#pdf-zoom-out').onclick=()=>{pdfState.zoom/=1.2;applyPdfTransform();};$('#pdf-fit').onclick=fitPdf;
  $('#pdf-overlay').addEventListener('pointerdown',ev=>{if(pdfState.tool==='pan'){pdfState.drag={x:ev.clientX,y:ev.clientY,ox:pdfState.x,oy:pdfState.y};return;}pdfState.points.push(pdfPoint(ev));completePdfMeasurement();});window.addEventListener('pointermove',ev=>{if(pdfState.drag){pdfState.x=pdfState.drag.ox+ev.clientX-pdfState.drag.x;pdfState.y=pdfState.drag.oy+ev.clientY-pdfState.drag.y;applyPdfTransform();}});window.addEventListener('pointerup',()=>pdfState.drag=null);$('#pdf-stage').addEventListener('wheel',ev=>{ev.preventDefault();pdfState.zoom*=ev.deltaY<0?1.1:0.91;applyPdfTransform();},{passive:false});
}

function bind(){
  $$('[data-action]').forEach(button => {
    button.addEventListener('click', () => handleAction(button.dataset.action));
  });
  $$('.tool[data-tool]').forEach(button => {
    button.addEventListener('click', () => setTool(button.dataset.tool));
  });
  $$('[data-run]').forEach(button => {
    button.addEventListener('click', () => startCalculation(button.dataset.run));
  });
  $$('[data-close]').forEach(button => {
    button.addEventListener('click', () => button.closest('.modal').classList.add('hidden'));
  });
  $('#confirm-open').addEventListener('click', () => {
    openModel($('#config-list').value);
    $('#open-dialog').classList.add('hidden');
  });
  $('#add-phase').addEventListener('click', addPhase);
  $('#apply-phases').addEventListener('click', applyPhaseDialog);
  $('#confirm-save').addEventListener('click', () => {
    save($('#save-filename').value);
    $('#save-dialog').classList.add('hidden');
  });
  $('[data-close-run]').addEventListener('click', () => {
    $('#run-drawer').classList.add('hidden');
  });
  $('#canvas').addEventListener('wheel', event => {event.preventDefault();zoom(event.deltaY<0?0.88:1.14,pointerXY(event));},{passive:false});
  $('#canvas').addEventListener('pointerdown', beginPan);
  $('#canvas').addEventListener('mousemove', event => {
    const p = pointerXY(event);
    $('#status-coordinates').textContent = `X ${p.x.toFixed(1)}  Y ${p.y.toFixed(1)}`;
  });
  $('#canvas').addEventListener('click', event => {
    if (event.target.closest('[data-type]')) return;
    const p = pointerXY(event);
    if (state.tool === 'arm') {
      addArm(p.x, p.y);
      setTool('select');
    } else {
      state.selected = null;
      render();
    }
  });
  $('#command-input').addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      command(event.target.value);
      event.target.value = '';
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      state.commandIndex = Math.max(0, state.commandIndex - 1);
      event.target.value = state.commandHistory[state.commandIndex] || '';
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      state.commandIndex = Math.min(
        state.commandHistory.length,
        state.commandIndex + 1,
      );
      event.target.value = state.commandHistory[state.commandIndex] || '';
    }
  });
  document.addEventListener('keydown', event => {
    if (event.target.matches('input, select, textarea')) return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
      event.preventDefault();
      undo();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') {
      event.preventDefault();
      redo();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      handleAction('save');
    }
    const shortcuts = {v:'select',h:'pan',a:'arm',l:'lane',m:'movement',g:'geometry',s:'signal'};
    if (!event.ctrlKey && !event.metaKey && shortcuts[event.key.toLowerCase()]) {
      setTool(shortcuts[event.key.toLowerCase()]);
    }
  });
}

async function boot(){bind();bindPdf();setPdfTool("pan");try{const d=await api('/api/model');if(d.model&&Object.keys(d.model).length){state.model=d.model;state.filename=d.filename;markDirty(false);}}catch(e){log(e.message,'error');}render();log('PySig Studio ready. Enter HELP for commands.','success');}
boot();
