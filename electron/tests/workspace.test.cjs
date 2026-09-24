// Exercise workspace state transitions in an isolated DOM, without opening or
// controlling a user's browser. Native rendering remains a separate release gate.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { parseHTML } = require('linkedom');
const root = path.resolve(__dirname, '../..');

function workspace() {
  const { window } = parseHTML(fs.readFileSync(path.join(root, 'static/index.html'), 'utf8'));
  const document = window.document;
  const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
  assert.equal(new Set(ids).size, ids.length, 'Element IDs must be unique');
  for (const select of document.querySelectorAll('select')) Object.defineProperty(select, 'value', {
    get() { return this._value ?? this.options[0].value; }, set(value) { this._value = String(value); }
  });
  for (const input of document.querySelectorAll('input[type=checkbox]')) input.checked = input.hasAttribute('checked');
  for (const canvas of document.querySelectorAll('canvas')) {
    canvas.getBoundingClientRect = () => ({ left:0, width:640, height:96 });
    canvas.getContext = () => ({ scale(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){} });
  }
  for (const audio of document.querySelectorAll('audio')) {
    audio.pause = () => { audio.paused = true; }; audio.paused = true;
    audio.play = async () => { audio.paused = false; audio.dispatchEvent(new window.Event('play')); };
    audio.load = () => {}; audio.duration = 20; audio.currentTime = 0; audio.readyState = 1;
    Object.defineProperty(audio, 'src', {get(){return this.getAttribute('src');},set(v){this.setAttribute('src',v);}});
  }
  const jobs = new Map(), requests = [], pendingFrames = new Set(), pendingTimers = new Set();
  const response = (data, ok=true) => ({ok, json:async()=>data});
  let delayNext = false;
  async function fetch(url, options={}) {
    requests.push({url,method:options.method||'GET'});
    if (url === '/api/system') return response({version:'1.2.2',active_jobs:[],gpu_available:false,
      features:{bubble_cleanup:true,listening_tracks:true,bubble_multipass:true,rerun_source:true,targeted_cleanup:true,cleanup_versions:true}});
    if (url === '/api/jobs' && !options.method) return response([...jobs.values()]);
    if (url === '/api/jobs' || url.endsWith('/rerun')) {
      const input = url === '/api/jobs' ? Object.fromEntries(options.body.entries()) : JSON.parse(options.body);
      const id = String(jobs.size+1).padStart(32,'0');
      const cleanup = input.mode==='targeted' ? {prompt:input.prompt,strength:Number(input.bubble_strength),
        start:Number(input.range_start||0),end:input.range_end==null?null:Number(input.range_end),passes:Number(input.bubble_passes)} :
        {kind:input.bubble_type||'water',strength:Number(input.bubble_strength||.85),start:0,end:null,passes:1};
      const preview = input.preview===true || input.preview==='true';
      const revision=id.slice(-12), gains=input.mode==='stems'?{speech:1,music:0,effects:1}:{speech:1,music:1,effects:1};
      const job = {id, filename:'sample.mp4',status:delayNext?'running':'complete',message:'Ready',progress:1,video_preview:true,
        settings:{mode:input.mode,cleanup,preview,gains,device:'cpu',cpu_fallback:true,source_basis:input.source_basis||'original'},
        source:{duration:20,sample_rate:8000,channels:2,waveform:[.1,.3,.4,.2]},
        report:{mode:input.mode,passes:cleanup.passes,preview,applied_cleanup:{...cleanup,start:cleanup.start,end:preview?Math.min(cleanup.end??20,cleanup.start+10):cleanup.end??20},
          device:'cpu',duration:20,sample_rate:8000,channels:2,warnings:[],output_format:'Float WAV'},
        mix:{mode:input.mode,revision,mix:`cleaned-${revision}.wav`,removed:`removed-${revision}.wav`,bundle:`soundshredder-${revision}.zip`,report:`report-${revision}.json`,
          waveform:[.1,.2],cleanup,gains,preview}};
      if (input.mode==='inspect') {delete job.report;delete job.mix;}
      jobs.set(id,job); delayNext=false; return response({id});
    }
    const id=url.split('/')[3], job=jobs.get(id);
    if (url.endsWith('/cancel')) {job.status='cancelled';job.message='Cancelled';return response(job);}
    if (url.endsWith('/versions')) return response([...jobs.values()].reverse().map(j=>({id:j.id,status:j.status,mode:j.settings.mode,
      cleanup:j.settings.cleanup,preview:j.settings.preview,applied_cleanup:j.report?.applied_cleanup,source_basis:j.settings.source_basis})));
    if (url.endsWith('/listening')) return response({status:'complete',missing:['speech','music','effects'],
      tracks:{speech:{},music:{},effects:{},removed:{file:job.mix.removed,waveform:[.1]}},removed_definition:'Target removed'});
    if (job) return response(job);
    throw new Error('Unexpected request '+url);
  }
  const context = vm.createContext({ document, window:{devicePixelRatio:1,addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})},
    location:{hash:'',search:''}, history:{replaceState(){}}, videoPreview:{setSource(){}},
    requestAnimationFrame(callback){ const token=setImmediate(()=>{pendingFrames.delete(token);callback();});pendingFrames.add(token);return token; },
    setTimeout(callback,delay){const token=setTimeout(()=>{pendingTimers.delete(token);callback();},delay);pendingTimers.add(token);return token;},
    clearTimeout(token){pendingTimers.delete(token);clearTimeout(token);}, URL, FormData, fetch, console, confirm:()=>true });
  vm.runInContext(fs.readFileSync(path.join(root,'static/app.js'),'utf8'),context);
  const $=id=>document.getElementById(id);
  const input=(id,value)=>{$(id).value=String(value);$(id).dispatchEvent(new window.Event('input'));};
  const check=(id,value)=>{$(id).checked=value;$(id).dispatchEvent(new window.Event('input'));};
  const upload=()=>{
    Object.defineProperty($('file-input'),'files',{configurable:true,value:[new File(['audio'],'sample.mp4',{type:'video/mp4'})]});
    $('file-input').dispatchEvent(new window.Event('change'));
  };
  return {$,input,check,upload,jobs,requests,context,window,delay(){delayNext=true;},close(){
    vm.runInContext('clearTimeout(pollTimer); clearTimeout(listeningTimer);',context);
    for(const token of pendingFrames) clearImmediate(token);
    for(const token of pendingTimers) clearTimeout(token);
  }};
}
async function until(fn) {
  for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,5));}
  throw new Error('Workspace state did not arrive');
}

test('guided workflow prepares a source, saves previews, protects stale exports and records chained inputs', async()=>{
  const ui=workspace();
  try {
    await until(()=>!ui.$('mode-targeted').disabled);
    ui.$('mode-targeted').click();assert.equal(ui.$('targeted-panel').hidden,false);assert.equal(ui.$('quick-panel').hidden,true);
    ui.upload();await until(()=>ui.jobs.size===1&&!ui.$('mode-targeted').disabled);
    assert.equal([...ui.jobs.values()][0].settings.mode,'inspect');
    assert.equal(ui.$('results').hidden,true);assert.equal(ui.$('prepare-source').textContent,'Waveform ready ✓');
    ui.input('target-prompt','Water bubbling');ui.check('target-range',true);ui.input('target-start',7);ui.input('target-end',11);
    ui.input('target-strength',70);ui.input('target-passes',3);ui.$('preview-target').click();
    await until(()=>ui.jobs.size===2&&!ui.$('results').hidden&&!ui.$('mode-targeted').disabled);
    const preview=[...ui.jobs.values()][1];
    assert.equal(preview.settings.preview,true);assert.equal(preview.settings.cleanup.passes,3);assert.equal(preview.settings.cleanup.strength,.7);
    assert.match(ui.$('download-mix').textContent,/preview/);assert.equal(ui.$('target-source').querySelector('[value="cleaned"]').disabled,true);
    ui.input('target-prompt','A ringing phone');assert.equal(ui.$('download-mix').hidden,true);assert.match(ui.$('result-notice').textContent,/previous version/);
    ui.$('separate').click();await until(()=>ui.jobs.size===3&&!ui.$('mode-targeted').disabled);
    assert.equal([...ui.jobs.values()][2].settings.preview,false);assert.equal(ui.$('target-source').querySelector('[value="cleaned"]').disabled,false);
    ui.input('target-source','cleaned');ui.input('target-prompt','Wind noise');ui.$('separate').click();
    await until(()=>ui.jobs.size===4&&!ui.$('mode-targeted').disabled);
    assert.equal([...ui.jobs.values()][3].settings.source_basis,'cleaned');
    assert.match(ui.$('listening-help').textContent,/previous cleaned version/);
    assert.match(ui.$('original-audio').getAttribute('aria-label'),/previous cleaned version/);
    await until(()=>ui.$('cleanup-versions').children.length===4);
    ui.$('cleanup-versions').children[2].click();await until(()=>ui.$('target-prompt').value==='Water bubbling');
    assert.equal(ui.$('target-passes').value,'3');
    ui.$('mode-quick').click();assert.equal(ui.$('quick-panel').hidden,false);assert.equal(ui.$('targeted-panel').hidden,true);
    ui.$('new-session').click();assert.equal(ui.$('versions-panel').hidden,true);assert.equal(ui.$('results').hidden,true);
  } finally {ui.close();}
});

test('invalid target range is actionable and cancelled work can be retried from its saved source',async()=>{
  const ui=workspace();
  try{
    await until(()=>!ui.$('mode-targeted').disabled);ui.$('mode-targeted').click();ui.upload();
    await until(()=>ui.jobs.size===1&&!ui.$('mode-targeted').disabled);
    ui.input('target-prompt','Water bubbling');ui.check('target-range',true);ui.input('target-start',12);ui.input('target-end',5);
    ui.$('preview-target').click();await until(()=>!ui.$('error').hidden);assert.equal(ui.jobs.size,1);
    ui.input('target-end',18);ui.delay();ui.$('separate').click();
    await until(()=>ui.jobs.size===2&&!ui.$('cancel').disabled);assert.equal(ui.$('mode-quick').disabled,true);
    ui.$('cancel').click();await until(()=>!ui.$('mode-quick').disabled);
    assert.equal(ui.$('separate').disabled,false);ui.$('separate').click();
    await until(()=>ui.jobs.size===3&&!ui.$('results').hidden);
    assert.equal(ui.$('error').hidden,true);
  }finally{ui.close();}
});

test('completed audio waits for engine exit before another cleanup is enabled',async()=>{
  const ui=workspace();
  try{
    await until(()=>!ui.$('mode-targeted').disabled);ui.$('mode-targeted').click();ui.upload();
    await until(()=>ui.jobs.size===1&&!ui.$('mode-targeted').disabled);
    ui.input('target-prompt','Water bubbling');ui.delay();ui.$('separate').click();
    await until(()=>ui.jobs.size===2&&vm.runInContext('!!pollTimer',ui.context));
    const job=[...ui.jobs.values()][1];job.status='complete';job.worker_active=true;
    await vm.runInContext(`poll('${job.id}')`,ui.context);
    assert.equal(ui.$('separate').disabled,true);assert.match(ui.$('progress-message').textContent,/Finishing/);
    job.worker_active=false;await vm.runInContext(`poll('${job.id}')`,ui.context);
    assert.equal(ui.$('separate').disabled,false);assert.equal(ui.$('results').hidden,false);
  }finally{ui.close();}
});
