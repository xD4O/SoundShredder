// Private rendered fixtures verify the controls without running models or editing sessions.
const {chromium}=require('playwright');
const {fixture}=require('./lab-extraction-ui.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.SOUNDSHREDDER_TEST_URL||'http://127.0.0.1:7863',id='f'.repeat(32);
const out=path.resolve(__dirname,'../../artifacts/mixing-lab/layers-ui');
function model(){
  const source=fixture(['speech','music','effects']),state=source.data.state,originalRoute=source.route;
  const audio=Buffer.alloc(44+144000*2);audio.write('RIFF');audio.writeUInt32LE(audio.length-8,4);audio.write('WAVEfmt ',8);
  audio.writeUInt32LE(16,16);audio.writeUInt16LE(1,20);audio.writeUInt16LE(1,22);audio.writeUInt32LE(48000,24);audio.writeUInt32LE(96000,28);
  audio.writeUInt16LE(2,32);audio.writeUInt16LE(16,34);audio.write('data',36);audio.writeUInt32LE(audio.length-44,40);
  for(let i=0;i<144000;i++)audio.writeInt16LE(Math.round(1500*Math.sin(i*.04)),44+i*2);
  let serial=0,pending;const uuid=()=>String(++serial).padStart(32,'0');
  source.buffers=[];source.splitRequests=[];
  source.finish=()=>{
    const name=pending.track,parent=state.tracks[name],depth=(state.track_info?.[name]?.depth||1)+1,layer=uuid(),children=[];
    state.layers||={};state.track_info||={};
    for(const [kind,label] of [['speech','Dialogue'],['music','Music'],['effects','Effects'],['remainder','Remainder']]){
      const child=uuid(),asset=uuid();children.push(child);
      state.assets[asset]={id:asset,track:child,label:`Layer ${depth} · ${label}`,role:'split',parent:parent.asset,layer,depth,kind,peaks:[.1,.1,.1],peak:.1,peak_hz:1};
      state.tracks[child]={asset,regions:structuredClone(parent.regions)};
      state.track_info[child]={label,kind,depth,parent_track:name,layer};
    }
    state.layers[layer]={id:layer,depth,parent_track:name,source_track:structuredClone(parent),children,active:true,method:'Bandit v2'};
    state.revision++;state.last_task=source.data.task.id;state.last_layer=layer;
    source.data.task={...source.data.task,active:false,status:'complete',progress:1,message:'Layer ready.'};return layer;
  };
  source.route=async route=>{
    const request=route.request(),url=new URL(request.url()),body=request.method()==='GET'?null:request.postDataJSON();
    if(url.pathname.endsWith('/actions/split')){
      pending=body;source.splitRequests.push(body);
      source.data.task={id:uuid(),operation:'split',active:true,status:'running',progress:.3,message:'Separating the selected stem…'};
    }else if(url.pathname.endsWith('/lab/layer')){
      state.layers[body.layer].active=body.enabled;state.revision++;
    }else if(url.pathname.endsWith('/lab')&&request.method()==='PUT'){
      state.tracks=body.tracks;state.revision++;
    }else if(url.pathname.includes('/lab/assets/')){
      source.buffers.push(url.pathname.split('/').pop());return route.fulfill({contentType:'audio/wav',body:audio});
    }else return originalRoute(route);
    await route.fulfill({json:structuredClone(source.data)});
  };
  return source;
}
module.exports={model};
if(require.main===module)(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.SOUNDSHREDDER_TEST_BROWSER||(process.platform==='win32'?'msedge':undefined)});
  try{
    const data=model(),state=data.data.state,errors=[];
    const page=await browser.newPage({viewport:{width:1500,height:1100}});page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/api/**',route=>data.route(route));await page.goto(`${base}/lab?session=${id}`);
    await page.locator('#split-effects').waitFor();assert.equal(await page.locator('.layer-badge').first().textContent(),'LAYER 1');
    await page.locator('#split-effects').click();await page.locator('#split-panel').waitFor({state:'visible'});
    await page.locator('#split-device').selectOption('cpu');await page.locator('#split-run').click();
    await page.locator('#job-progress').waitFor({state:'visible'});assert.equal(data.splitRequests[0].track,'effects');assert.equal(data.splitRequests[0].device,'cpu');
    const layer2=data.finish();await page.waitForFunction(layer=>document.querySelector('#layer-view').value===layer,layer2);
    const child=state.layers[layer2].children[1];
    assert.equal(await page.locator('#channels .channel').count(),4);
    assert.equal(await page.locator(`#split-${child}`).isEnabled(),true);
    await page.locator('[data-scope="second"]').click();
    await page.locator('#scrub').evaluate(el=>{el.value=1.5;el.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.locator(`#fader-${child}`).evaluate(el=>{el.value=-9;el.dispatchEvent(new Event('change',{bubbles:true}));});
    await page.waitForFunction(child=>!document.querySelector(`#fader-${child}`).disabled,child);
    assert.equal(state.tracks[child].regions[0].db,-9);
    await page.locator(`#split-${child}`).click();await page.locator('#split-run').click();await page.locator('#job-progress').waitFor({state:'visible'});
    const layer3=data.finish();await page.waitForFunction(layer=>document.querySelector('#layer-view').value===layer,layer3);
    const deep=state.layers[layer3].children[0];assert.equal(state.track_info[deep].depth,3);assert.equal(state.tracks[deep].regions[0].db,-9);
    assert.equal(await page.locator(`#target-track option[value="${deep}"]`).count(),1);
    await page.locator('#layer-master').click();assert.equal(await page.locator('#fader-effects').count(),0);
    assert.equal(await page.locator(`#fader-${deep}`).isEnabled(),true);
    assert.equal(await page.locator('#layer-master').getAttribute('aria-pressed'),'true');
    await page.locator('#layer-view').selectOption(layer3);await page.locator(`#solo-${deep}`).click();
    await page.locator('#play').click();await page.waitForFunction(()=>document.querySelector('#playback-label').textContent==='Playing in sync');
    assert.equal(data.buffers.includes('effects'),false);assert.equal(data.buffers.includes(state.tracks[child].asset),false);
    assert.deepEqual(data.buffers.sort(),state.layers[layer3].children.map(name=>state.tracks[name].asset).sort());await page.locator('#play').click();
    await page.locator('#layer-view').selectOption(layer2);await page.locator('#layer-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#layer-toggle').textContent==='Use this split in mix');
    await page.locator('#layer-view').selectOption('');
    assert.equal(await page.locator('#fader-effects').isEnabled(),true);assert.equal(await page.locator('#solo-effects').getAttribute('aria-pressed'),'false');
    await page.locator('#layer-view').selectOption(layer2);await page.locator('#layer-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#layer-toggle').textContent==='Use parent in mix');
    await page.locator('#layer-view').selectOption(layer3);await page.reload();
    await page.waitForFunction(layer=>document.querySelector('#layer-view').value===layer,layer3);
    assert.equal(state.tracks[deep].regions[0].db,-9);
    for(const width of [1500,760,390]){
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Overflow at ${width}`);
      await page.screenshot({path:path.join(out,`layer3-${width}.png`),fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('Lab layers UI passed: selected-stem requests, recursive layer navigation, inherited edits, leaf playback, solo recovery, parent restore/reuse, reload and responsive layouts.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
