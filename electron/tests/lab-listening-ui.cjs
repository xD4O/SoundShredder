// Verify the real UI and Web Audio graph with distinguishable tones per stem.
// API fixtures are private: no user sessions or model jobs are changed.
const {chromium}=require('playwright');
const {model}=require('./lab-layers-ui.cjs');
const M=require('../../static/lab-math.js');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.SOUNDSHREDDER_TEST_URL||'http://127.0.0.1:7863',id='f'.repeat(32);
const out=path.resolve(__dirname,'../../artifacts/mixing-lab/listening-ui');

function tone(frequency){
  const audio=Buffer.alloc(44+144000*2);audio.write('RIFF');audio.writeUInt32LE(audio.length-8,4);audio.write('WAVEfmt ',8);
  audio.writeUInt32LE(16,16);audio.writeUInt16LE(1,20);audio.writeUInt16LE(1,22);audio.writeUInt32LE(48000,24);audio.writeUInt32LE(96000,28);
  audio.writeUInt16LE(2,32);audio.writeUInt16LE(16,34);audio.write('data',36);audio.writeUInt32LE(audio.length-44,40);
  for(let i=0;i<144000;i++)audio.writeInt16LE(Math.round(1311*Math.sin(2*Math.PI*frequency*i/48000)),44+i*2);
  return audio;
}

(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.SOUNDSHREDDER_TEST_BROWSER||(process.platform==='win32'?'msedge':undefined)});
  try{
    const data=model(),state=data.data.state,errors=[],frequencies={},audio={};let edits=0,holdNext=false,releaseHeld,held;
    const page=await browser.newPage({viewport:{width:1500,height:1100}});page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/api/**',async route=>{
      const request=route.request(),url=new URL(request.url());
      if(url.pathname.includes('/lab/assets/')){
        const asset=url.pathname.split('/').pop();data.buffers.push(asset);
        if(!frequencies[asset])frequencies[asset]=(Object.keys(state.assets).indexOf(asset)+1)*300;
        audio[asset]||=tone(frequencies[asset]);
        if(holdNext){holdNext=false;held=asset;await new Promise(resolve=>{releaseHeld=resolve;});}
        await route.fulfill({contentType:'audio/wav',body:audio[asset]}).catch(error=>{
          if(!/closed|intercept|aborted/i.test(error.message))throw error;
        });return;
      }
      if(request.method()==='PUT'&&url.pathname.endsWith('/lab'))edits++;
      return data.route(route);
    });
    await page.goto(`${base}/lab?session=${id}`);await page.locator('#split-music').waitFor();
    await page.evaluate(()=>{
      const start=LabPlayer.prototype.start;
      LabPlayer.prototype.start=function(...args){window.qaPlayer=this;return start.apply(this,args);};
    });
    await page.locator('#split-music').click();await page.locator('#split-run').click();
    await page.locator('#job-progress').waitFor({state:'visible'});
    const layer=data.finish(),children=state.layers[layer].children;
    await page.waitForFunction(layer=>document.querySelector('#layer-view').value===layer,layer);
    await page.locator('[data-scope="range"]').click();
    await page.locator('#range-start').fill('0');await page.locator('#range-end').fill('3');
    async function save(action){
      await Promise.all([page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/lab')),action()]);
      await page.waitForFunction(revision=>document.querySelector('#saved').textContent===`Saved · revision ${revision}`,state.revision);
    }
    for(const child of children.slice(2))await save(()=>page.locator(`#mute-${child}`).click());
    await page.locator('#range-start').fill('1');await page.locator('#range-end').fill('2');
    await save(()=>page.locator(`#fader-${children[1]}`).evaluate(el=>{el.value=-9;el.dispatchEvent(new Event('change',{bubbles:true}));}));
    const before=JSON.stringify(state.tracks),savedEdits=edits;
    await page.locator('#play').click();
    await page.waitForFunction(()=>window.qaPlayer?.playing);
    assert.deepEqual(data.buffers.sort(),children.map(name=>state.tracks[name].asset).sort());
    assert.match(await page.locator('#listening-scope').textContent(),/LAYER 2 ONLY · Music/);
    await page.locator('#layer-master').click();
    await page.waitForFunction(()=>window.qaPlayer?.playing&&window.qaPlayer.layerId===null);
    const masterNames=Object.keys(M.activeTracks(state));
    assert.deepEqual((await page.evaluate(()=>Object.keys(window.qaPlayer.channels))).sort(),masterNames.sort());
    assert.equal(await page.locator('#fader-music').count(),0,'the parent must not play or show as another active channel');
    assert.equal(await page.locator(`#gain-${children[1]}`).count(),1,'Master exposes the deeper edits');
    await page.locator('#play').click();
    assert.equal(JSON.stringify(state.tracks),before);assert.equal(edits,savedEdits,'view changes do not save or alter a mix');

    // Render through the actual LabPlayer graph, including envelopes and gates.
    // Correlate each known frequency to verify audible output, not just fetches.
    async function render(layerId,solo=null){
      return page.evaluate(async({state,layerId,solo,id})=>{
        const ctx=new OfflineAudioContext(1,48000*3,48000);ctx.resume=()=>Promise.resolve();
        const p=new LabPlayer(`/api/jobs/${id}/lab`,()=>{},()=>{});p.ctx=ctx;p.solo=solo;
        await p.start(0,state,null,layerId);const output=await ctx.startRendering();p.stop();
        const samples=output.getChannelData(0),result={};
        for(const time of [.5,1.5,2.5]){
          result[time]={};const start=Math.round((time+.08)*48000),count=4800;
          Object.keys(state.assets).forEach((asset,index)=>{
            const frequency=(index+1)*300;let sin=0,cos=0;
            for(let i=start;i<start+count;i++){sin+=samples[i]*Math.sin(2*Math.PI*frequency*i/48000);cos+=samples[i]*Math.cos(2*Math.PI*frequency*i/48000);}
            result[time][asset]=2*Math.hypot(sin,cos)/count;
          });
        }
        return result;
      },{state,layerId,solo,id});
    }
    const layerAudio=await render(layer),masterAudio=await render(null),soloAudio=await render(layer,children[0]);
    const voice=state.tracks[children[0]].asset,music=state.tracks[children[1]].asset;
    for(const time of ['0.5','1.5','2.5']){
      for(const asset of Object.keys(state.assets)){
        if(![voice,music].includes(asset))assert.ok(layerAudio[time][asset]<.00001,`Unexpected layer tone ${asset}`);
        if(asset!==voice)assert.ok(soloAudio[time][asset]<.00001,`Solo leaked ${asset}`);
      }
      assert.ok(layerAudio[time][voice]>.01);assert.ok(layerAudio[time][music]>.003);
      assert.ok(masterAudio[time].speech>.01&&masterAudio[time].effects>.01);
      assert.ok(masterAudio[time].music<.00001,'Master must replace the parent music, not double it');
      assert.ok(Math.abs(layerAudio[time][voice]-masterAudio[time][voice])<.00001,'branch level must match Master');
      assert.ok(Math.abs(layerAudio[time][music]-masterAudio[time][music])<.00001,'Master must preserve deeper automation');
    }
    assert.ok(Math.abs(layerAudio['1.5'][music]/layerAudio['0.5'][music]-M.linear(-9))<.001);
    assert.ok(Math.abs(layerAudio['2.5'][music]-layerAudio['0.5'][music])<.00001,'gain resets outside the selected second');

    // Switch while a layer buffer is still in flight. Its delayed completion
    // must never add the previous scope back to the newly started Master.
    await page.locator('#layer-view').selectOption(layer);
    await page.locator('#scrub').evaluate(el=>{el.value=0;el.dispatchEvent(new Event('input',{bubbles:true}));});
    holdNext=true;await page.locator('#play').click();
    await page.waitForFunction(()=>document.querySelector('#playback-label').textContent==='Buffering stems…');
    assert.ok(held);await page.locator('#layer-master').click();
    await page.waitForFunction(()=>window.qaPlayer?.playing&&window.qaPlayer.layerId===null);
    releaseHeld();await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.deepEqual((await page.evaluate(()=>Object.keys(window.qaPlayer.channels))).sort(),masterNames.sort());
    await page.locator('#play').click();

    // A saved inactive branch remains independently listenable and does not
    // silently re-enable its descendants in Master.
    await page.locator('#layer-view').selectOption(layer);await page.locator('#layer-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#layer-toggle').textContent==='Use this split in mix');
    data.buffers.length=0;await page.locator('#play').click();await page.waitForFunction(()=>window.qaPlayer?.playing);
    assert.deepEqual(data.buffers.sort(),children.map(name=>state.tracks[name].asset).sort());
    await page.locator('#layer-master').click();await page.waitForFunction(()=>window.qaPlayer?.playing&&window.qaPlayer.layerId===null);
    assert.deepEqual((await page.evaluate(()=>Object.keys(window.qaPlayer.channels))).sort(),['effects','music','speech']);
    await page.locator('#play').click();
    await page.locator('#layer-view').selectOption(layer);await page.locator('#layer-toggle').click();
    await page.waitForFunction(()=>document.querySelector('#layer-toggle').textContent==='Use parent in mix');
    await page.locator('#layer-master').click();
    for(const width of [1500,760,390]){
      await page.setViewportSize({width,height:1100});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`Master overflow at ${width}`);
      await page.screenshot({path:path.join(out,`master-${width}.png`),fullPage:true});
    }
    await page.setViewportSize({width:1500,height:1100});await page.locator('#layer-view').selectOption(layer);
    await page.screenshot({path:path.join(out,'layer2.png'),fullPage:true});
    for(const child of children)await save(()=>page.locator(`#version-${child}`).selectOption(''));
    assert.equal(await page.locator('#play').isDisabled(),true);
    assert.match(await page.locator('#mix-ready-hint').textContent(),/No tracks selected in this layer/);
    await page.locator('#layer-original').click();await page.waitForFunction(()=>window.qaPlayer?.playing);
    assert.deepEqual(await page.evaluate(()=>Object.keys(window.qaPlayer.channels)),['music']);
    await page.locator('#return-mix').click();assert.equal(await page.locator('#play').isDisabled(),true);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'audio-routing.json'),JSON.stringify({layerAudio,masterAudio,soloAudio},null,2));
    console.log('Lab listening passed: audible branch isolation, Master with timed deep edits, solo, mute, switching during playback/buffering, inactive branches, empty layer, source audition and responsive Master.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
