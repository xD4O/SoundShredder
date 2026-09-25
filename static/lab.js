/* Mixing Lab UI: immutable sources, explicit edit scope, shared playback clock. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), M=LabMath;
  const labels={speech:'Dialogue',music:'Music',effects:'Effects',ambience:'Ambience'};
  const colors={speech:'#ef93bd',music:'#77d7f4',effects:'#f2c17c',ambience:'#9bd6a2'};
  let job=new URLSearchParams(location.search).get('session'), state=null, player=null;
  let time=0, mode='second', pending=false, active=false, timer=null, undo=[], audition=null, canvasRows={};
  let lastTask=null, sessionGeneration=0, busyLabel='', auditionEnd=null, auditionStart=0, labTask=null;
  let sessionsRequest=0;
  let visibleLayer=null, splitTrack=null;
  const viewWrites=new Map(), closingSessions=new Set();
  const info=name=>state?.track_info?.[name]||{label:labels[name],kind:name,depth:1};
  const trackLabel=name=>labels[info(name).kind]||(info(name).kind==='remainder'?'Remainder':info(name).label);
  const trackColor=name=>colors[info(name).kind]||'#b8aecb';
  const visibleTracks=()=>visibleLayer?state.layers?.[visibleLayer]?.children||[]:
    [...M.reachableTracks(state)].filter(name=>!M.activeLayer(state,name));
  function trackPath(name){const meta=info(name);return meta.parent_track?`${trackPath(meta.parent_track)} → ${trackLabel(name)}`:trackLabel(name);}
  const endpoint=()=>`/api/jobs/${job}/lab`;
  const fmt=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(3).padStart(6,'0')}`;
  function notice(text) { $('notice').textContent=text; $('notice').hidden=!text; }
  async function api(url,options={}) {
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),options.body instanceof FormData?120000:20000);
    try {
      const response=await fetch(url,{...options,signal:controller.signal});
      let data; try {data=await response.json();} catch {throw new Error('The local server did not respond. Reopen SoundShredder and retry.');}
      if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'Check the time range and settings, then retry.');
      return data;
    } catch(error) {if(error.name==='AbortError')throw new Error('The local server took too long to respond. Reopen this session to check whether work finished before retrying.');throw error;}
    finally {clearTimeout(timeout);}
  }
  const json=(method,data)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  function interval() {
    if (!state) return [0,1];
    return M.scope(time,mode,state.duration,state.fps||24,+$('range-start').value,+$('range-end').value);
  }
  function validInterval() {
    const [start,end]=interval();
    if (!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>state.duration) throw new Error('Choose an interval inside the clip, with its end after its start.');
    return [start,end];
  }
  function stop() {
    busyLabel='paused';
    if (player) {time=player.current(); player.stop(time);}
    $('video').pause(); $('play').textContent='▶'; $('play').setAttribute('aria-label','Play mix');
    $('playback-label').textContent='Paused';
  }
  function seek(value) { stop(); time=Math.max(0,Math.min(state?.duration||0,value)); if(player)player.time=time; showTime(); }
  function showTime() {
    if (!state) return;
    $('time').textContent=fmt(time); $('scrub').value=time;
    const video=$('video');
    if (state.video && !$('picture').hidden && !video.hidden && Number.isFinite(video.duration)) {
      if (Math.abs(video.currentTime-time)>(player?.playing ? .06 : .0001)) video.currentTime=Math.min(video.duration,time);
      if (player?.playing && video.paused) video.play().catch(()=>{});
    }
    const [start,end]=interval();
    $('scope-label').textContent=`${start.toFixed(3)} – ${end.toFixed(3)} s`;
    $('target-range').textContent=`Target interval: ${start.toFixed(3)} – ${end.toFixed(3)} s`;
    const outputTrim=audition?1:M.playbackProtection(state,visibleLayer);
    for (const [name,t] of Object.entries(state.tracks)) {
      const gain=M.valueAt(t.regions,Math.min(time,state.duration-1e-9));
      const fader=$(`fader-${name}`);
      if(!fader)continue;
      fader.value=gain===null?-60:gain;
      $(`gain-${name}`).textContent=gain===null?'Muted':`${gain>0?'+':''}${gain.toFixed(1)} dB`;
      $(`mute-${name}`).setAttribute('aria-pressed',String(gain===null));
      let peak=0;
      if (player?.playing) peak=player.peak(name)*outputTrim;
      else if(t.asset) {
        const asset=state.assets[audition&&state.assets[audition].track===name?audition:t.asset];
        peak=asset.peaks[Math.min(asset.peaks.length-1,Math.floor(time*asset.peak_hz))]||0;
        peak*=audition?1:M.gainAt(t.regions,time)*outputTrim;
        if (audition&&asset.id!==audition || player?.solo&&player.solo!==name&&!audition) peak=0;
      }
      const db=M.dbfs(peak);
      const grouped=!player?.playing&&M.activeLayer(state,name);
      $(`peak-${name}`).textContent=grouped?`Layer ${grouped.depth} active`:db<=-100?'−∞ dBFS':`${db.toFixed(1)} dBFS`;
      $(`meter-${name}`).style.height=grouped?'0%':`${Math.max(0,Math.min(100,(db+60)/60*100))}%`;
    }
    const master=player?.playing?M.dbfs(player.peak('master')):-120;
    $('master-db').textContent=master<=-100?'−∞':`${master.toFixed(1)} dBFS`;
    $('master-fill').style.width=`${Math.max(0,Math.min(100,(master+60)/60*100))}%`;
    $('meter-caption').textContent=player?.playing?'LIVE PEAK · dBFS':'AT PLAYHEAD · 100 ms PEAK';
    drawLanes();
  }
  function setBusy() {
    const locked=pending||active;
    $('source-file').disabled=locked;
    for (const id of ['preview','apply','export','extract','stem-file','undo','split-run','layer-toggle']) $(id).disabled=locked||!state;
    $('split-device').disabled=locked;
    $('undo').disabled=locked||!undo.length;
    for(const node of document.querySelectorAll('.channel select,.channel input,.channel .reset,.channel [id^="mute-"]')) node.disabled=locked||!state;
    if(state) {
      for(const [name,t] of Object.entries(state.tracks)) for(const suffix of ['fader','mute','solo','reset']) {
        const node=$(`${suffix}-${name}`); if(node)node.disabled=locked||!t.asset||(suffix!=='solo'&&Boolean(M.activeLayer(state,name)));
      }
      const leaves=M.activeTracks(state),reachable=M.reachableTracks(state);
      for(const name of visibleTracks()){
        $(`version-${name}`).disabled=locked||Boolean(M.activeLayer(state,name));
        $(`split-${name}`).disabled=locked||!leaves[name]||state.assets[state.tracks[name].asset]?.role==='preview'||info(name).depth>=8;
      }
      $('split-run').disabled=locked||!leaves[splitTrack];
      if(visibleLayer)$('layer-toggle').disabled=locked||!reachable.has(state.layers[visibleLayer].parent_track);
    }
    $('saved').textContent=pending?'Saving…':active?'Processing…':state?`Saved · revision ${state.revision}`:'';
    showExtraction();
  }
  function showExtraction() {
    if(!state)return;
    const stemNames=['speech','music','effects'];
    const missing=stemNames.filter(name=>!state.tracks[name].asset);
    const extracting=active&&labTask?.operation==='extract';
    const stopped=!active&&labTask?.operation==='extract'&&['failed','cancelled'].includes(labTask.status);
    const ready=!missing.length, playable=Boolean(audition)||Object.keys(M.playbackTracks(state,visibleLayer)).length>0;
    $('stem-extraction').dataset.state=extracting?'running':ready?'ready':stopped?'stopped':'empty';
    $('extraction-title').textContent=extracting?'Extracting your stems…':ready?'Your stems are ready.':
      stopped?(labTask.status==='cancelled'?'Extraction cancelled.':'Extraction stopped.'):
      missing.length===3?'Extract your audio stems.':'Complete your audio stems.';
    $('extraction-description').textContent=extracting?'Keep this session open to follow progress. Your tracks will appear below when extraction finishes.':
      ready?'Dialogue, music and effects are available below. Press Play to listen, then shape your mix.':
      stopped?'Your saved tracks and source are intact. Retry extraction when you’re ready.':
      missing.length===3?'Separate this file into dialogue, music and effects, then mix them with your footage.':
      `Create the remaining tracks: ${missing.map(name=>labels[name]).join(', ')}. Existing tracks are retained.`;
    for(const name of stemNames){
      const available=Boolean(state.tracks[name].asset), status=$(`status-${name}`);
      status.dataset.ready=String(available);
      status.querySelector('b').textContent=available?'Ready':extracting?'Extracting…':'Not extracted';
    }
    $('extract').textContent=extracting?'Extracting stems…':ready?'Stems ready':stopped?'Retry extraction':missing.length===3?'Extract stems':'Extract missing stems';
    $('extract').disabled=pending||active||ready;
    $('extract-device').disabled=pending||active;
    $('extraction-progress').hidden=!extracting;
    if(extracting){$('extraction-message').textContent=labTask.message;$('extraction-meter').value=labTask.progress||0;}
    $('play').disabled=!playable;
    $('mix-ready-hint').hidden=playable;
    $('mix-ready-hint').textContent=visibleLayer?'No tracks selected in this layer. Enable a stem or return to Master.':extracting?'Your stems are being extracted. Play will be available when they’re ready.':
      'Extract stems above, or import a track, to play your mix.';
    if(!playable)$('playback-label').textContent=extracting?'Extracting stems…':'Waiting for stems';
  }
  async function saveTracks(next,remember=true) {
    if(pending||active)return;
    const generation=sessionGeneration, focus=document.activeElement?.id;
    stop(); const before=structuredClone(state.tracks); if(remember)undo.push(before); undo=undo.slice(-30);
    pending=true; setBusy(); notice('');
    try { const data=await api(endpoint(),json('PUT',{revision:state.revision,tracks:next}));if(generation===sessionGeneration)accept(data); }
    catch(error) {
      if(generation!==sessionGeneration)return;
      if(remember)undo.pop(); notice(error.message);
      try {accept(await api(endpoint()));} catch {}
    } finally {if(generation===sessionGeneration){pending=false; setBusy();if(focus?.match(/^(fader|version|mute|reset)-/))$(focus)?.focus({preventScroll:true});}}
  }
  function gainEdit(name,db) {
    if(pending||active)return;
    try {
      const [start,end]=validInterval(), next=structuredClone(state.tracks);
      next[name].regions=M.insert(next[name].regions,start,end,db);
      saveTracks(next);
    } catch(error) {notice(error.message);}
  }
  function renderLayers() {
    if(visibleLayer&&!state.layers?.[visibleLayer])visibleLayer=null;
    const select=$('layer-view');select.replaceChildren(new Option('Master · All active layers',''));
    for(const layer of Object.values(state.layers||{})){
      select.add(new Option(`Layer ${layer.depth} · ${trackPath(layer.parent_track)}${layer.active?'':' · saved'}`,layer.id));
    }
    select.value=visibleLayer||'';
    const layer=state.layers?.[visibleLayer],reachable=M.reachableTracks(state);
    $('layer-master').setAttribute('aria-pressed',String(!layer));
    $('channels-heading').textContent=layer?`02 / LAYER ${layer.depth} MIX`:'02 / MASTER MIX';
    $('channels').classList.toggle('master-channels',!layer);
    $('layer-back').hidden=$('layer-original').hidden=$('layer-toggle').hidden=!layer;
    if(layer){
      const used=layer.active&&reachable.has(layer.parent_track);
      $('layer-description').textContent=`Listening only to ${trackPath(layer.parent_track)} · Layer ${layer.depth}. Other branches are excluded. ${used?'Your edits also flow into Master.':'Saved branch; currently outside Master.'}`;
      $('layer-toggle').textContent=layer.active?'Use parent in mix':'Use this split in mix';
    }else $('layer-description').textContent='Hear the full mix and edit its active stems from every depth. Deeper splits replace their parent here, with all saved volume and cleanup edits included.';
    history.replaceState({},'',`/lab?session=${job}${visibleLayer?`&layer=${visibleLayer}`:''}`);
    const choices=Object.keys(state.tracks).filter(name=>reachable.has(name)&&!M.activeLayer(state,name));
    for(const id of ['target-track','import-track']){
      const menu=$(id),selected=menu.value;menu.replaceChildren();
      for(const name of choices)menu.add(new Option(info(name).depth===1?trackLabel(name):`Layer ${info(name).depth} · ${trackPath(name)}`,name));
      menu.value=choices.includes(selected)?selected:choices.find(name=>state.tracks[name].asset)||choices[0];
    }
  }
  function chooseLayer(id) {
    if(!state)return;
    const resume=player?.playing||busyLabel==='buffering';
    stop();audition=null;auditionEnd=null;player?.setSolo(null);
    visibleLayer=id;splitTrack=null;$('split-panel').hidden=true;
    renderLayers();makeChannels();renderResult();setAuditionLabel();setBusy();showTime();notice('');
    if(resume&&!$('play').disabled)player.start(time>=state.duration?0:time,state,null,visibleLayer);
  }
  function showSplit(name) {
    if(pending||active||!M.activeTracks(state)[name])return;
    splitTrack=name;$('split-panel').hidden=false;
    $('split-heading').textContent=`Create Layer ${info(name).depth+1}.`;
    $('split-description').textContent=`Split ${trackPath(name)} again with Bandit. The current stem stays available as the parent, and the four new tracks become the active mix for this branch.`;
    $('split-run').textContent=`Split into Layer ${info(name).depth+1}`;
    setBusy();$('split-panel').scrollIntoView({behavior:'smooth',block:'center'});$('split-run').focus({preventScroll:true});
  }
  async function toggleLayer() {
    if(pending||active||!visibleLayer)return;
    const generation=sessionGeneration,layer=state.layers[visibleLayer];
    stop();pending=true;setBusy();notice('');
    try {const data=await api(`${endpoint()}/layer`,json('PUT',{revision:state.revision,layer:layer.id,enabled:!layer.active}));if(generation===sessionGeneration)accept(data);}
    catch(error){if(generation===sessionGeneration)notice(error.message);}
    finally{if(generation===sessionGeneration){pending=false;setBusy();}}
  }
  function makeChannels() {
    $('channels').replaceChildren(); $('lanes').replaceChildren(); canvasRows={};
    for(const name of visibleTracks()) {
      const label=trackLabel(name);
      const t=state.tracks[name], channel=document.createElement('div');
      channel.className=`channel${t.asset?'':' empty'}`; channel.style.setProperty('--color',trackColor(name));
      // All interpolated values below are fixed local channel identifiers and labels.
      channel.innerHTML=`<h3>${label}</h3><select id="version-${name}" aria-label="${label} stem version"></select><div class="level"><div class="meter"><i id="meter-${name}"></i></div><input id="fader-${name}" aria-label="${label} gain in selected interval" type="range" min="-60" max="6" step="0.5" value="0"><div class="scale"><span>+6</span><span>0</span><span>−18</span><span>−36</span><span>−60</span></div></div><output id="gain-${name}">0.0 dB</output><div id="peak-${name}" class="peak">−∞ dBFS</div><div class="channel-actions"><button id="mute-${name}" title="Mute only the selected interval" aria-label="Mute ${label} in selected interval" aria-pressed="false">M</button><button id="solo-${name}" title="Solo for listening; does not affect export" aria-label="Solo ${label}" aria-pressed="false">S</button><a id="download-${name}" title="Download selected source stem before fader edits" aria-label="Download ${label} source stem">↓</a></div><button id="reset-${name}" class="reset">Reset interval</button>`;
      $('channels').append(channel);
      const badge=document.createElement('small');badge.className='layer-badge';badge.textContent=`LAYER ${info(name).depth}`;channel.prepend(badge);
      if(!visibleLayer){const path=document.createElement('div');path.className='channel-path';path.textContent=trackPath(name);path.title=trackPath(name);channel.querySelector('h3').after(path);}
      const split=document.createElement('button');split.id=`split-${name}`;split.className='split-stem';split.textContent='Split again ↗';
      split.title=`Split ${label} into Layer ${info(name).depth+1}`;split.onclick=()=>showSplit(name);channel.append(split);
      const deeper=M.activeLayer(state,name);
      if(deeper){const button=document.createElement('button');button.className='open-layer';button.textContent=`Open Layer ${deeper.depth} →`;button.onclick=()=>chooseLayer(deeper.id);channel.append(button);}
      const select=$(`version-${name}`), empty=new Option('No track', ''); select.add(empty);
      for(const asset of Object.values(state.assets).filter(a=>a.track===name&&a.role!=='removed')) select.add(new Option(asset.label,asset.id));
      select.value=t.asset||'';
      select.onchange=()=>{audition=null; const next=structuredClone(state.tracks);next[name].asset=select.value||null;saveTracks(next);};
      const fader=$(`fader-${name}`);
      fader.onpointerdown=stop;
      fader.oninput=()=>{stop(); $(`gain-${name}`).textContent=`${+fader.value>0?'+':''}${(+fader.value).toFixed(1)} dB`;};
      fader.onchange=()=>gainEdit(name,+fader.value);
      $(`mute-${name}`).onclick=()=>gainEdit(name,M.valueAt(t.regions,time)===null?0:null);
      $(`reset-${name}`).onclick=()=>gainEdit(name,0);
      $(`solo-${name}`).onclick=()=>{
        const solo=player.solo===name?null:name; player.setSolo(solo);
        for(const k of visibleTracks())$(`solo-${k}`).setAttribute('aria-pressed',String(k===solo));
        showTime();
      };
      $(`solo-${name}`).setAttribute('aria-pressed',String(player?.solo===name));
      const link=$(`download-${name}`);if(t.asset)link.href=`${endpoint()}/assets/${t.asset}`;else link.hidden=true;
      const lane=document.createElement('div'); lane.className='lane';lane.style.setProperty('--color',trackColor(name));
      const title=document.createElement('span'); title.textContent=!visibleLayer&&info(name).depth>1?trackPath(name):label;
      const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',`${label} waveform and timed volume edits`);
      canvas.tabIndex=0;canvas.setAttribute('role','slider');canvas.setAttribute('aria-valuemin','0');canvas.setAttribute('aria-valuemax',String(state.duration));
      lane.append(title,canvas);$('lanes').append(lane);canvasRows[name]=canvas;
      let drag=null;
      const at=event=>Math.max(0,Math.min(state.duration,(event.clientX-canvas.getBoundingClientRect().left)/canvas.clientWidth*state.duration));
      canvas.onpointerdown=e=>{stop();drag={time:at(e),x:e.clientX};canvas.setPointerCapture(e.pointerId);};
      canvas.onpointermove=e=>{
        if(!drag||Math.abs(e.clientX-drag.x)<3)return;
        setScope('range');$('range-start').value=Math.min(drag.time,at(e)).toFixed(3);$('range-end').value=Math.max(drag.time,at(e)).toFixed(3);showTime();
      };
      canvas.onpointerup=e=>{if(drag&&Math.abs(e.clientX-drag.x)<3)seek(drag.time);drag=null;};
      canvas.onpointercancel=()=>{drag=null;};
      canvas.onkeydown=e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();seek(time+(e.key==='ArrowRight'?1:-1)*(state.fps?1/state.fps:.1));}};
    }
  }
  function drawLanes() {
    if(!state)return;
    const [start,end]=interval();
    for(const [name,canvas] of Object.entries(canvasRows)) {
      const dpr=Math.min(devicePixelRatio||1,2), width=canvas.clientWidth, height=canvas.clientHeight;
      if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)){canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
      const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
      const x=t=>t/state.duration*width, track=state.tracks[name], asset=state.assets[track.asset];
      ctx.fillStyle='#77efc91a';ctx.fillRect(x(start),0,x(end)-x(start),height);
      ctx.strokeStyle=trackColor(name);ctx.globalAlpha=.45;ctx.lineWidth=1;
      if(asset) {
        const peaks=asset.peaks, norm=Math.max(.05,asset.peak);
        ctx.beginPath();for(let px=1;px<width;px+=3) {const index=Math.min(peaks.length-1,Math.floor(px/width*peaks.length));const h=Math.min(20,peaks[index]/norm*20);ctx.moveTo(px,24-h);ctx.lineTo(px,24+h);}ctx.stroke();
      }
      ctx.globalAlpha=1;
      for(const r of track.regions){const left=x(r.start),w=Math.max(1,x(r.end)-left);ctx.fillStyle='#77efc955';ctx.fillRect(left,height-17,w,15);if(w>35){ctx.font='8px sans-serif';ctx.fillStyle='#dafbee';ctx.fillText(r.db===null?'MUTE':`${r.db} dB`,left+3,height-6,Math.max(1,w-5));}}
      ctx.fillStyle='#e5fff5';ctx.fillRect(Math.min(width-1,x(time)),0,1,height);
      canvas.setAttribute('aria-valuenow',time.toFixed(3));
    }
  }
  function setScope(next) {
    mode=next;for(const button of $('scopes').children)button.setAttribute('aria-pressed',String(button.dataset.scope===mode));
    $('range-start').disabled=mode!=='range';$('range-end').disabled=mode!=='range';showTime();
  }
  function renderResult() {
    const name=$('target-track').value, asset=state.assets[state.tracks[name].asset], box=$('target-result');
    box.replaceChildren();box.hidden=!asset?.removed;
    if(!asset?.removed)return;
    const text=document.createElement('div');const r=asset.applied_cleanup;
    text.textContent=`${asset.role==='preview'?'PREVIEW ONLY':'CLEANUP VERSION'} · ${r.start.toFixed(2)}–${r.end.toFixed(2)} s · ${asset.cleanup.passes} pass(es). ${asset.cleanup.prompt}`;
    box.append(text);
    for(const [label,id] of [['Before',asset.parent],['Cleaned',asset.id],['Removed sounds',asset.removed]]) {
      const button=document.createElement('button');button.textContent=label;button.onclick=()=>listen(id,r.start,r.end);box.append(button);
    }
    const download=document.createElement('a');download.textContent='Download removed ↓';download.href=`${endpoint()}/assets/${asset.removed}`;box.append(download);
    const reuse=document.createElement('button');reuse.textContent='Reuse these settings';reuse.onclick=()=>{
      $('prompt').value=asset.cleanup.prompt;$('strength').value=asset.cleanup.strength;$('strength').dispatchEvent(new Event('input'));
      $('passes').value=asset.cleanup.passes;$('range-start').value=asset.cleanup.start;$('range-end').value=asset.cleanup.end??state.duration;setScope('range');
    };box.append(reuse);
  }
  function renderDownloads() {
    const out=$('downloads'), ex=state.export;out.replaceChildren();out.hidden=!ex;if(!ex)return;
    const p=document.createElement('p');p.textContent=ex.revision===state.revision?'Export matches the saved mix.':`Export is from revision ${ex.revision}. Export again to include newer edits.`;out.append(p);
    const names={'mix.wav':'WAV mix','mixing-lab.zip':'All stems + mix ZIP','mixed-video.mp4':'Video + new sound','mix-report.json':'Edit report'};
    for(const filename of ex.files) {const a=document.createElement('a');a.textContent=names[filename]||ex.file_labels?.[filename]||`${labels[filename.split('.')[0]]||filename} WAV`;a.href=`${endpoint()}/exports/${ex.id}/${filename}`;out.append(a);}
    if(ex.video_error){const error=document.createElement('p');error.textContent=ex.video_error;out.append(error);}
  }
  function renderState() {
    const focus=document.activeElement?.id;
    $('welcome').hidden=true;$('work').hidden=false;$('filename').textContent=state.filename;
    $('format').textContent=`${(state.rate/1000).toFixed(1)} kHz · ${state.channels===2?'Stereo':'Mono'} · ${(state.duration).toFixed(2)} s${state.fps?` · ${state.fps.toFixed(2)} nominal fps`:''}`;
    $('source-basis').hidden=!['targeted','bubble'].includes(state.source_mode);
    $('scrub').max=state.duration;$('duration').textContent=`/ ${fmt(state.duration)}`;
    $('range-start').max=state.duration;$('range-end').max=state.duration;
    $('range-end').value=Math.min(state.duration,+$('range-end').value);
    $('video').hidden=!state.video;$('audio-art').hidden=state.video;
    const videoURL=`/api/jobs/${job}/video`;
    if(state.video&&$('video').getAttribute('src')!==videoURL)$('video').src=videoURL;
    $('show-video').disabled=!state.video;$('export-video').disabled=!state.video;
    $('back').disabled=!state.fps;$('forward').disabled=!state.fps;
    document.querySelector('[data-scope="frame"]').disabled=!state.fps;
    if(!state.fps&&mode==='frame')mode='second';
    $('frame-note').textContent=state.fps?'Drag a lane for a range · frame steps use nominal FPS (VFR may differ)':'Drag a lane for a range · use seconds when video FPS is unavailable';
    renderLayers();makeChannels();setScope(mode);renderResult();renderDownloads();setBusy();showTime();
    if(focus?.match(/^(fader|version|mute|reset)-/))$(focus)?.focus({preventScroll:true});
  }
  function accept(data) {
    labTask=data.task;
    active=Boolean(data.task?.active);
    if(data.state && (!state||state.revision<data.state.revision)) {
      const changedLayers=JSON.stringify(state?.layers||{})!==JSON.stringify(data.state.layers||{});
      if(data.task?.operation==='split'&&data.state.last_layer!==state?.last_layer){visibleLayer=data.state.last_layer;splitTrack=null;$('split-panel').hidden=true;}
      if(changedLayers)undo=[];
      if(state&&state.last_task!==data.state.last_task&&['import','extract','cleanup'].includes(data.task?.operation)){
        undo.push(structuredClone(state.tracks));undo=undo.slice(-30);
      }
      stop();state=data.state;audition=null;auditionEnd=null;
      if(player?.solo&&(!visibleTracks().includes(player.solo)||!M.leafNames(state,player.solo).length))player.solo=null;
      renderState();setAuditionLabel();
    } else if(data.state&&state.revision===data.state.revision){state=data.state;renderDownloads();}
    $('job-progress').hidden=!active||(labTask?.operation==='extract'&&Boolean(state));
    if(data.task){$('progress-label').textContent=data.task.message;$('progress').value=data.task.progress||0;}
    if(data.task && !active && lastTask!==`${data.task.id}:${data.task.status}`) {
      lastTask=`${data.task.id}:${data.task.status}`;
      if(['failed','cancelled'].includes(data.task.status))notice(data.task.message);
    }
    setBusy();
  }
  async function poll(generation) {
    if(generation!==sessionGeneration||!job)return;
    try {if(!pending){const data=await api(endpoint());if(generation!==sessionGeneration)return;if(!pending)accept(data);}}
    catch(error){if(generation===sessionGeneration)notice(error.message);}
    if(generation===sessionGeneration)timer=setTimeout(()=>poll(generation),active?650:3000);
  }
  async function action(operation,extra={}) {
    if(pending||active)return;
    const generation=sessionGeneration;
    stop();pending=true;setBusy();notice('');
    try {const data=await api(`${endpoint()}/actions/${operation}`,json('POST',{revision:state?.revision||0,device:$('device').value,...extra}));if(generation===sessionGeneration)accept(data);}
    catch(error){if(generation===sessionGeneration)notice(error.message);}
    finally {if(generation===sessionGeneration){pending=false;setBusy();}}
  }
  function setAuditionLabel() {
    const layer=state.layers?.[visibleLayer],label=layer?`Layer ${layer.depth}`:'Master';
    $('audition-label').textContent=audition?`Audition only: ${state.assets[audition].label}`:
      layer?`${trackPath(layer.parent_track)} · only this branch is playing`:'All active layers · deeper edits included';
    $('listening-scope').textContent=audition?'SOURCE AUDITION · ONE TRACK':layer?`LAYER ${layer.depth} ONLY · ${trackPath(layer.parent_track)}`:'MASTER · ALL ACTIVE LAYERS';
    $('return-mix').hidden=!audition;$('return-mix').textContent=`Return to ${label}`;
    $('output-label').textContent=audition?'AUDITION':layer?`LAYER ${layer.depth} OUT`:'MASTER';
    const trim=audition?1:M.playbackProtection(state,visibleLayer);
    $('trim').textContent=audition?'Source audition · before fader edits and output protection':
      `Output protection: ${M.dbfs(trim).toFixed(1)} dB · reserves +6 dB headroom · ${layer?(trim===M.protection(state)?'Master reference level':'saved branch preview'):'same trim on export'}`;
  }
  function playbackStatus(status,message) {
    busyLabel=status;
    $('playback-label').textContent=status==='buffering'?'Buffering stems…':status==='playing'?'Playing in sync':'Paused';
    $('play').textContent=status==='playing'?'Ⅱ':status==='buffering'?'…':'▶';
    $('play').setAttribute('aria-label',status==='playing'?'Pause mix':'Play mix');
    if(status==='error'){notice(message);$('video').pause();}
    if(status==='empty')notice(visibleLayer?'No tracks selected in this layer. Enable a stem or return to Master.':'Extract stems or import a track to start mixing.');
    if(status==='paused'){$('video').pause();showTime();}
  }
  function listen(asset,start,end) {stop();audition=asset;time=start;auditionStart=start;auditionEnd=end;setAuditionLabel();showExtraction();player.start(time,state,audition,visibleLayer);}
  async function openSession(id) {
    const requestedLayer=id===job?new URLSearchParams(location.search).get('layer'):null;
    ++sessionGeneration;const generation=sessionGeneration;clearTimeout(timer);stop();player?.dispose();player=null;
    state=null;job=id;undo=[];audition=null;auditionEnd=null;lastTask=null;labTask=null;active=false;pending=false;canvasRows={};
    visibleLayer=requestedLayer;splitTrack=null;$('split-panel').hidden=true;
    history.replaceState({},'',id?`/lab?session=${id}`:'/lab');
    $('separator-link').href=id?`/?session=${id}`:'/';
    $('work').hidden=true;$('welcome').hidden=false;$('job-progress').hidden=true;notice('');time=0;
    $('video').removeAttribute('src');$('video').load();
    $('source-file').value='';setBusy();
    if(!id)$('source-file').focus({preventScroll:true});
    if(!id){await loadSessions();return;}
    player=new LabPlayer(endpoint(),t=>{if(generation!==sessionGeneration)return;time=t;if(audition&&auditionEnd!==null&&t>=auditionEnd){player.stop(auditionEnd);time=auditionEnd;$('video').pause();playbackStatus('paused');}showTime();},(status,message)=>{if(generation===sessionGeneration)playbackStatus(status,message);});
    try {
      await setSessionView(id,false);if(generation!==sessionGeneration)return;
      let source=await api(`/api/jobs/${id}`);
      if(generation!==sessionGeneration)return;
      if(source.status!=='complete'||source.worker_active){
        notice('Finish processing this source in Audio separator, then open it in the Lab.');$('welcome').hidden=false;return;
      }
      const data=await api(endpoint());if(generation!==sessionGeneration)return;accept(data);
      if(!data.state&&!data.task?.active)await action('prepare');
      if(generation!==sessionGeneration)return;
      poll(generation);loadSessions();
    } catch(error){if(generation===sessionGeneration){notice(error.message);$('welcome').hidden=false;}}
  }
  function setSessionView(id,closed) {
    // A slow reopen must finish before a later close of the same session.
    const request=(viewWrites.get(id)||Promise.resolve()).catch(()=>{}).then(()=>
      api(`/api/jobs/${id}/lab/view`,json('PUT',{closed})));
    viewWrites.set(id,request);
    const release=()=>{if(viewWrites.get(id)===request)viewWrites.delete(id);};
    request.then(release,release);return request;
  }
  async function closeSession(id=job) {
    if(!id||closingSessions.has(id))return;
    closingSessions.add(id);
    const closing=setSessionView(id,true);
    if(id===job)openSession(null);
    const generation=sessionGeneration;
    try {await closing;if(generation===sessionGeneration)notice('Session closed. Reopen it from Closed sessions in the sidebar.');}
    catch(error){if(generation===sessionGeneration)notice(`Could not close this saved session: ${error.message}`);}
    finally {closingSessions.delete(id);loadSessions();}
  }
  async function loadSessions() {
    const request=++sessionsRequest;
    try {
      const jobs=await api('/api/lab/sessions');if(request!==sessionsRequest)return;
      $('sessions').replaceChildren();$('closed-session-list').replaceChildren();
      let openCount=0,closedCount=0;
      for(const item of jobs){const a=document.createElement('a');a.href=`/lab?session=${item.id}`;a.textContent=item.filename;
        if(item.id===job)a.setAttribute('aria-current','page');const s=document.createElement('small');
        s.textContent=item.lab_running?'Processing…':item.closed?'Reopen saved mix':item.status==='complete'?'Open in Mixing Lab':item.status;a.append(s);
        a.onclick=e=>{e.preventDefault();openSession(item.id);};
        if(item.closed){closedCount++;$('closed-session-list').append(a);continue;}
        openCount++;const row=document.createElement('div');row.className='session-row';row.dataset.session=item.id;
        const close=document.createElement('button');close.textContent='×';close.title=`Close ${item.filename}`;
        close.setAttribute('aria-label',`Close session ${item.filename}`);close.disabled=closingSessions.has(item.id);
        close.onclick=()=>closeSession(item.id);row.append(a,close);$('sessions').append(row);
      }
      if(!openCount){const empty=document.createElement('p');empty.className='sessions-empty';empty.textContent='No open sessions. Upload a file or reopen a saved mix.';$('sessions').append(empty);}
      $('closed-count').textContent=closedCount;$('closed-sessions').hidden=!closedCount;
    } catch(error){if(request===sessionsRequest)notice(error.message);}
  }
  async function upload(file) {
    if(!file)return;if(file.size>500*1024*1024){notice('Choose a file smaller than 500 MB.');return;}
    if(pending||active)return;const generation=sessionGeneration;
    pending=true;$('source-file').value='';$('source-file').disabled=true;notice('Uploading to your local workspace…');
    try {
      const form=new FormData();form.append('file',file);form.append('mode','inspect');
      const result=await api('/api/jobs',{method:'POST',body:form});if(generation!==sessionGeneration){loadSessions();return;}notice('Reading the source audio and video timing…');
      let ready=false;
      for(let attempt=0;attempt<300;attempt++){
        if(generation!==sessionGeneration){loadSessions();return;}
        const status=await api(`/api/jobs/${result.id}`);
        if(status.status==='complete'&&!status.worker_active){ready=true;break;}
        if(['failed','cancelled'].includes(status.status))throw new Error(status.message);
        await new Promise(resolve=>setTimeout(resolve,700));
      }
      if(!ready)throw new Error('This file is taking longer to read. Open its session from Audio separator to check progress.');
      if(generation===sessionGeneration){pending=false;await openSession(result.id);}else loadSessions();
    } catch(error){if(generation===sessionGeneration)notice(error.message);}
    finally {if(generation===sessionGeneration){pending=false;$('source-file').disabled=false;}}
  }
  $('source-file').onchange=e=>upload(e.target.files[0]);
  $('welcome').ondragover=e=>{e.preventDefault();};$('welcome').ondrop=e=>{e.preventDefault();upload(e.dataTransfer.files[0]);};
  $('new-session').onclick=()=>openSession(null);$('close-session').onclick=()=>closeSession();
  $('play').onclick=()=>{if(!state)return;if(player.playing||busyLabel==='buffering'){stop();busyLabel='paused';return;}const start=audition&&time>=auditionEnd?auditionStart:time>=state.duration?0:time;player.start(start,state,audition,visibleLayer);};
  $('scrub').oninput=e=>seek(+e.target.value);
  $('back').onclick=()=>seek(Math.max(0,(Math.round(time*state.fps)-1)/state.fps));
  $('forward').onclick=()=>seek((Math.round(time*state.fps)+1)/state.fps);
  $('show-video').onchange=e=>{$('picture').hidden=!e.target.checked;if(!e.target.checked)$('video').pause();else showTime();};
  $('video').addEventListener('loadedmetadata',showTime);
  $('video').addEventListener('error',()=>{if(state?.video)notice('This browser cannot preview this video format. Audio mixing is still available; you can download the WAV for your editor.');});
  $('return-mix').onclick=()=>{stop();audition=null;auditionEnd=null;setAuditionLabel();showExtraction();showTime();};
  $('scopes').onclick=e=>{if(e.target.dataset.scope)setScope(e.target.dataset.scope);};
  for(const id of ['range-start','range-end'])$(id).oninput=showTime;
  $('undo').onclick=()=>{if(undo.length)saveTracks(undo.pop(),false);};
  $('strength').oninput=()=>{$('strength-label').textContent=`${Math.round(+$('strength').value*100)}%`;};
  $('target-track').onchange=renderResult;
  for(const id of ['preview','apply'])$(id).onclick=()=>{
    try {const [start,end]=validInterval();action('cleanup',{track:$('target-track').value,prompt:$('prompt').value,strength:+$('strength').value,passes:+$('passes').value,start,end,preview:id==='preview'});}
    catch(error){notice(error.message);}
  };
  $('extract').onclick=()=>action('extract',{device:$('extract-device').value});$('export').onclick=()=>action('export',{video:state.video&&$('export-video').checked});
  for(const id of ['device','extract-device','split-device'])$(id).onchange=()=>{
    for(const other of ['device','extract-device','split-device'])$(other).value=$(id).value;
  };
  $('layer-view').onchange=()=>chooseLayer($('layer-view').value||null);
  $('layer-master').onclick=()=>chooseLayer(null);
  $('layer-back').onclick=()=>chooseLayer(info(state.layers[visibleLayer].parent_track).layer||null);
  $('layer-original').onclick=()=>{const layer=state.layers[visibleLayer];listen(layer.source_track.asset,0,state.duration);};
  $('layer-toggle').onclick=toggleLayer;
  $('split-dismiss').onclick=()=>{$('split-panel').hidden=true;splitTrack=null;};
  $('split-run').onclick=()=>{if(splitTrack)action('split',{track:splitTrack,device:$('split-device').value});};
  $('cancel').onclick=async()=>{const generation=sessionGeneration;try{const data=await api(`${endpoint()}/cancel`,{method:'POST'});if(generation===sessionGeneration)accept(data);}catch(error){if(generation===sessionGeneration)notice(error.message);}};
  $('cancel-extract').onclick=()=>$('cancel').click();
  $('stem-file').onchange=async e=>{
    const file=e.target.files[0];if(!file||pending||active)return;
    const generation=sessionGeneration;
    stop();pending=true;setBusy();notice('Importing your stem…');
    try {const form=new FormData();form.append('file',file);form.append('revision',state.revision);form.append('track',$('import-track').value);form.append('fit',$('fit').value);const data=await api(`${endpoint()}/import`,{method:'POST',body:form});if(generation===sessionGeneration){accept(data);notice('');}}
    catch(error){if(generation===sessionGeneration)notice(error.message);}finally{if(generation===sessionGeneration){pending=false;e.target.value='';setBusy();}}
  };
  $('updates').onclick=async()=>{
    $('updates').disabled=true;
    try {const result=await api('/api/updates/check',{method:'POST'});$('update-info').textContent=(result.message||'Checked GitHub.')+' This Lab is an unreleased development preview.';}
    catch(error){$('update-info').textContent=error.message;}finally{$('updates').disabled=false;}
  };
  window.addEventListener('resize',()=>drawLanes());
  window.addEventListener('pagehide',()=>{stop();player?.dispose();clearTimeout(timer);});
  api('/api/system').then(info=>{$('version').textContent=`v${info.version}`;for(const id of ['device','extract-device','split-device'])$(id).querySelector('[value="cuda"]').disabled=!info.gpu_available;}).catch(error=>notice(error.message));
  openSession(job);
})();
