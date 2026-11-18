'use strict';
const el = id => document.getElementById(id);
let bootstrap, data, playing = false, current = 0, previousFrame = 0, scale = 4;
const ink = '#1c1917', clay = '#9a3b12', ash = '#6b6157', red = '#a21e28';

function pause() { playing = false; el('play').textContent = 'Play'; }
function error(message) { el('error').textContent = message; el('error').hidden = !message; }
function fit(canvas) {
  const ratio = window.devicePixelRatio || 1, rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width * ratio));
  canvas.height = Math.max(1, Math.round(rect.height * ratio));
  const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
  return [ctx, rect.width, rect.height];
}
function trace(canvas) {
  const [ctx, w, h] = fit(canvas), channel = Number(canvas.dataset.channel);
  if (!data) { ctx.fillStyle = ash; ctx.fillText('Data unavailable', 40, 50); return; }
  const left = 35, right = w - 10, top = 12, bottom = h - 23, duration = data.time_s.at(-1);
  const x = t => left + t / duration * (right - left), y = a => top + (scale - a) / (2 * scale) * (bottom - top);
  ctx.font = '10px system-ui'; ctx.lineWidth = 1;
  for (const value of [-scale, 0, scale]) {
    ctx.strokeStyle = '#c9c0b3'; ctx.beginPath(); ctx.moveTo(left, y(value)); ctx.lineTo(right, y(value)); ctx.stroke();
    ctx.fillStyle = ash; ctx.fillText(String(value), 2, y(value) + 3);
  }
  const rail = data.config.clip_g ?? 3;
  ctx.strokeStyle = '#a21e2870'; ctx.setLineDash([2, 4]);
  for (const value of [-rail, rail]) {ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(right,y(value));ctx.stroke();}
  ctx.setLineDash([]);
  for (const [key, color, dashed] of [['boundaries_s','#6b615733',false],['augmented_boundaries_s','#9a3b1240',true]]) {
    ctx.strokeStyle = color; ctx.setLineDash(dashed ? [2, 3] : []);
    for (const t of data[key]) { ctx.beginPath();ctx.moveTo(x(t),top);ctx.lineTo(x(t),bottom);ctx.stroke(); }
  }
  for (const [key, color, dashed] of [['original_g',ink,false],['augmented_g',clay,true]]) {
    ctx.strokeStyle = color; ctx.lineWidth = 1.1; ctx.setLineDash(dashed ? [5, 3] : []); ctx.beginPath();
    data[key].forEach((row, i) => { const px=x(data.time_s[i]),py=y(row[channel]); if(i===0)ctx.moveTo(px,py);else ctx.lineTo(px,py); }); ctx.stroke();
  }
  ctx.setLineDash([]);ctx.strokeStyle = red;ctx.lineWidth = 1;
  // A visible rail mark denotes contact; the transform provenance specifies hard clipping.
  data.augmented_g.forEach((row,i) => { if(Math.abs(row[channel])>=rail-1e-6){const px=x(data.time_s[i]),py=y(row[channel]);ctx.beginPath();ctx.moveTo(px-2,py-2);ctx.lineTo(px+2,py+2);ctx.moveTo(px-2,py+2);ctx.lineTo(px+2,py-2);ctx.stroke();} });
  ctx.strokeStyle = clay;ctx.beginPath();ctx.moveTo(x(current),top);ctx.lineTo(x(current),bottom);ctx.stroke();
  ctx.fillStyle = ash;ctx.fillText('0 s',left,bottom+17);ctx.fillText(duration.toFixed(1)+' s',Math.max(left,right-38),bottom+17);
}
function arm() {
  const [ctx,w,h] = fit(el('arm'));
  if (!bootstrap) return;
  const candidate = bootstrap.placements.candidates.find(p=>p.id===el('placement').value);
  if (!candidate) return;
  if (data?.optical?.available && el('motion-mode').value==='optical') {opticalArm(ctx,w,h,candidate);return;}
  const factor=w/300, shoulder=[w*.51,h*.2], len1=95*factor,len2=82*factor;
  const a=.30+.36*Math.sin(current*1.6),b=a+.6+.7*Math.sin(current*1.6+.4);
  const elbow=[shoulder[0]+Math.sin(a)*len1,shoulder[1]+Math.cos(a)*len1];
  const wrist=[elbow[0]+Math.sin(b)*len2,elbow[1]+Math.cos(b)*len2];
  const line=(from,to,color,width)=>{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(...from);ctx.lineTo(...to);ctx.stroke();};
  line([shoulder[0]-28*factor,shoulder[1]-18*factor],shoulder,'#c9c0b3',22*factor);
  line(shoulder,elbow,'#c9c0b3',27*factor);line(elbow,wrist,'#c9c0b3',22*factor);
  line(shoulder,elbow,ink,2);line(elbow,wrist,ink,2);
  const dot=(point,name)=>{ctx.fillStyle=ink;ctx.beginPath();ctx.arc(...point,4*factor,0,2*Math.PI);ctx.fill();ctx.font='12px system-ui';ctx.fillText(name,point[0]-57*factor,point[1]-7*factor);};
  dot(shoulder,'Shoulder');dot(elbow,'Elbow');dot(wrist,'Wrist');
  function mount(from,to,m,label) {
    const dx=to[0]-from[0],dy=to[1]-from[1],norm=Math.hypot(dx,dy),offset=11*factor*Math.cos(m.surface_deg*Math.PI/180);
    const point=[from[0]+m.fraction*dx+dy/norm*offset,from[1]+m.fraction*dy-dx/norm*offset];
    ctx.fillStyle=clay;ctx.fillRect(point[0]-6*factor,point[1]-7*factor,12*factor,14*factor);
    ctx.fillStyle=clay;ctx.font='bold 12px system-ui';ctx.fillText(label,point[0]+10*factor,point[1]+4*factor);
  }
  mount(shoulder,elbow,candidate.upper,'U');mount(elbow,wrist,candidate.forearm,'F');
  ctx.fillStyle=ash;ctx.font='11px system-ui';ctx.fillText('U upper arm   F forearm',12,h-12);
}
function opticalArm(ctx,w,h,candidate) {
  const motion=data.optical, index=Math.min(motion.time_s.length-1,Math.round(current*20));
  const boards=motion.boards.map(rows=>rows[index]);
  ctx.font='12px system-ui';ctx.fillStyle=ash;
  if(current>motion.time_s.at(-1)+.05||boards.some(board=>!board)){ctx.fillText('Optical pose unavailable at this frame',12,h/2);return;}
  const project=p=>[p[0]+.5*p[2],-p[1]+.1*p[2]], centers=boards.map(b=>project(b.position_m));
  const middle=[(centers[0][0]+centers[1][0])/2,(centers[0][1]+centers[1][1])/2], factor=Math.min(w/.95,h/.95);
  const pixel=p=>[w/2+(p[0]-middle[0])*factor,h/2+(p[1]-middle[1])*factor];
  function rotate(q,v) {
    const norm=Math.hypot(...q),[x,y,z,s]=q.map(a=>a/norm),[a,b,c]=v;
    return [(1-2*(y*y+z*z))*a+2*(x*y-z*s)*b+2*(x*z+y*s)*c,
      2*(x*y+z*s)*a+(1-2*(x*x+z*z))*b+2*(y*z-x*s)*c,
      2*(x*z-y*s)*a+2*(y*z+x*s)*b+(1-2*(x*x+y*y))*c];
  }
  boards.forEach((board,i)=>{
    const length=i===0?.30:.25, radius=i===0?.045:.035, mount=i===0?candidate.upper:candidate.forearm;
    const axis=rotate(board.quaternion_xyzw,[length/2,0,0]);
    const from=pixel(project(board.position_m.map((p,k)=>p-axis[k]))),to=pixel(project(board.position_m.map((p,k)=>p+axis[k])));
    ctx.strokeStyle='#c9c0b3';ctx.lineWidth=15;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(...from);ctx.lineTo(...to);ctx.stroke();
    const angle=mount.surface_deg*Math.PI/180,offset=rotate(board.quaternion_xyzw,[(mount.fraction-.5)*length,radius*(Math.cos(angle)-1),radius*Math.sin(angle)]);
    const point=pixel(project(board.position_m.map((p,k)=>p+offset[k])));
    ctx.fillStyle=clay;ctx.fillRect(point[0]-5,point[1]-6,10,12);ctx.fillText(i===0?'U':'F',point[0]+8,point[1]);
    const origin=pixel(centers[i]);ctx.fillStyle=ink;ctx.beginPath();ctx.arc(...origin,3,0,Math.PI*2);ctx.fill();
  });
  ctx.fillStyle=ash;ctx.fillText('Dots: measured board origins',12,h-28);ctx.fillText('Segments / sensor offsets: assumed',12,h-12);
}
function draw() {arm();document.querySelectorAll('.trace').forEach(trace);el('time').textContent=current.toFixed(2)+' s';}
function describeMount() {
  const c=bootstrap.placements.candidates.find(p=>p.id===el('placement').value);
  const d=c.definitions||{};
  el('mount-description').textContent=(d.upper||`Upper: ${c.upper.fraction*100}% from shoulder, surface ${c.upper.surface_deg}°.`)+' '+(d.forearm||`Forearm: ${c.forearm.fraction*100}% from elbow, surface ${c.forearm.surface_deg}°.`);
  arm();
}
async function preview() {
  pause();error('');el('apply').disabled=true;el('recording').disabled=true;el('status').textContent='Computing the Python transformation and C detector events…';
  try {
    const config=structuredClone(bootstrap.config);
    config.orientation.max_degrees=Number(el('rotation').value);config.noise_std_g=Number(el('noise').value);config.seed=Number(el('seed').value);
    const response=await fetch('/api/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source:el('recording').value,config,seed:Number(el('seed').value)})});
    const result=await response.json();if(!response.ok)throw new Error(result.error);
    data=result;current=0;el('scrub').value=0;el('scrub').max=data.time_s.at(-1);
    const opticalOption=el('motion-mode').options[1];opticalOption.disabled=!data.optical.available;
    opticalOption.textContent=data.optical.available?'Measured optical boards (unaligned)':'Measured optical boards (unavailable)';
    if(!data.optical.available)el('motion-mode').value='illustration';motionStatus();
    let largest=3;for(const key of ['original_g','augmented_g'])for(const row of data[key])for(const value of row)largest=Math.max(largest,Math.abs(value));scale=Math.ceil(largest);
    const rail=data.config.clip_g??3;let contacts=0;for(const row of data.augmented_g)for(const value of row)if(Math.abs(value)>=rail-1e-6)contacts++;
    el('signal-summary').textContent=`${data.time_s.length} synchronized samples at 100 Hz · ${contacts} transformed channel-samples at the ±${rail} g rails · C events ${data.boundaries_s.length} original / ${data.augmented_boundaries_s.length} transformed. No anatomical repetition labels.`;
    el('provenance').textContent=JSON.stringify({provenance:data.provenance,seed:data.seed,config:data.config,config_sha256:data.config_sha256,transformation:data.transformation,optical:{...data.optical,time_s:undefined,boards:undefined}},null,2);
    for(const name of ['play','reset','scrub','export'])el(name).disabled=false;
    el('status').textContent=`${data.provenance.volunteer} / ${data.provenance.exercise} / ${data.provenance.side} · measured source + transformed preview · physical transfer unvalidated`;draw();
  } catch (failure) {
    data=null;pause();for(const name of ['play','reset','scrub','export'])el(name).disabled=true;
    el('provenance').textContent='Unavailable for this preview';el('signal-summary').textContent='Signals unavailable; choose another recording or correct the settings.';
    error(failure.message);el('status').textContent='Preview unavailable';draw();
  } finally {el('apply').disabled=false;el('recording').disabled=false;}
}
async function start() {
  try {
    const response=await fetch('/api/bootstrap');if(!response.ok)throw new Error('Local configurations unavailable');bootstrap=await response.json();
    for(const item of bootstrap.sources) { const option=document.createElement('option');option.value=item.source;option.textContent=`${item.source} · series label ${item.series_label}`;el('recording').append(option); }
    el('recording').firstElementChild.remove();if(!bootstrap.sources.length)throw new Error('No paired recordings available');
    for(const p of bootstrap.placements.candidates){const option=document.createElement('option');option.value=p.id;option.textContent=p.name;el('placement').append(option);}
    el('rotation').value=bootstrap.config.orientation.max_degrees;el('noise').value=bootstrap.config.noise_std_g;el('seed').value=bootstrap.config.seed;
    for(const name of ['recording','placement','apply'])el(name).disabled=false;describeMount();await preview();
  } catch(failure){error(failure.message);el('status').textContent='Local data unavailable';}
}
el('apply').addEventListener('click',preview);el('recording').addEventListener('change',preview);
el('placement').addEventListener('change',describeMount);
function motionStatus(){el('motion-status').textContent=el('motion-mode').value==='optical'?'Measured optical board poses on their own recording-start clock. The shared replay control does not establish time alignment with IMU traces. Segment axes, lengths and mount offsets are assumed; no joint-angle validation.':'Illustrative motion. Joint angles, geometry and animation phase are not calibrated to these recordings.';}
el('motion-mode').addEventListener('change',()=>{motionStatus();arm();});
el('play').addEventListener('click',()=>{if(!data)return;playing=!playing;el('play').textContent=playing?'Pause':'Play';previousFrame=0;});
el('reset').addEventListener('click',()=>{pause();current=0;el('scrub').value=0;draw();});
el('scrub').addEventListener('input',()=>{pause();current=Number(el('scrub').value);draw();});
el('export').addEventListener('click',()=>{if(!data)return;const exported={...data,inspection_view:{candidate_id:el('placement').value,motion_mode:el('motion-mode').value,time_s:current,relationship:'Candidate controls change assumed drawing geometry, not recorded acceleration'}};const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(exported)],{type:'application/json'}));link.href=url;link.download='tally-preview.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
window.addEventListener('resize',draw);
function frame(now){if(playing&&data){if(previousFrame)current=Math.min(current+(now-previousFrame)/1000,data.time_s.at(-1));previousFrame=now;el('scrub').value=current;draw();if(current>=data.time_s.at(-1))pause();}requestAnimationFrame(frame);}
requestAnimationFrame(frame);start();
