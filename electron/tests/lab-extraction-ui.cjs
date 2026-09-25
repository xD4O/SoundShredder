// Render the real Lab against private API fixtures. The server supplies static
// files only; no saved sessions or model jobs are changed by these checks.
// Start the source server, then run npm run test:lab-ui from electron/.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.env.SOUNDSHREDDER_TEST_URL||'http://127.0.0.1:7863';
const id='f'.repeat(32), keys=['speech','music','effects','ambience'];
const out=path.resolve(__dirname,'../../artifacts/mixing-lab/extraction-ui');

function fixture(initial=[]) {
  const state={schema:1,revision:1,filename:'Extraction workflow example.mp4',frames:144000,
    rate:48000,channels:2,duration:3,fps:24,video:false,assets:{},
    tracks:Object.fromEntries(keys.map(name=>[name,{asset:null,regions:[]}]))};
  const data={state,task:null,stems_available:false},requests=[];
  function add(name) {
    state.assets[name]={id:name,track:name,label:'Saved stem',role:'original',peaks:[.1,.2,.1],peak:.2,peak_hz:1};
    state.tracks[name].asset=name;
  }
  initial.forEach(add);
  return {data,requests,async route(route){
    const request=route.request(), url=new URL(request.url()), method=request.method();let response;
    if(url.pathname==='/api/system')response={version:'1.2.2',gpu_available:false};
    else if(url.pathname==='/api/lab/sessions')response=[];
    else if(url.pathname.endsWith('/lab/view'))response={id,...request.postDataJSON()};
    else if(url.pathname===`/api/jobs/${id}`)response={id,status:'complete',worker_active:false};
    else if(url.pathname.endsWith('/actions/extract')){
      requests.push(request.postDataJSON());
      data.task={id:'test-extraction',operation:'extract',active:true,status:'running',progress:.4,message:'Separating your audio into tracks…'};response=data;
    }else if(url.pathname.endsWith('/cancel')){
      data.task={...data.task,active:false,status:'cancelled',progress:0,message:'Extraction cancelled.'};response=data;
    }else if(url.pathname===`/api/jobs/${id}/lab`&&method==='GET')response=data;
    else throw new Error(`Unexpected Lab test request: ${method} ${url.pathname}`);
    await route.fulfill({json:structuredClone(response)});
  },complete(){['speech','music','effects'].forEach(add);state.revision++;state.last_task='test-extraction';
    data.task={...data.task,active:false,status:'complete',progress:1,message:'Your Lab is ready.'};}};
}

(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.SOUNDSHREDDER_TEST_BROWSER||(process.platform==='win32'?'msedge':undefined)});
  try {
    const errors=[];
    const page=await browser.newPage({viewport:{width:1500,height:1000}}), model=fixture();
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/api/**',route=>model.route(route));
    await page.goto(`${base}/lab?session=${id}`);
    await page.locator('#extract').waitFor();
    assert.equal(await page.locator('.channel').count(),4);
    assert.equal(await page.locator('#layer-view, .split-stem, #split-run').count(),0);
    assert.equal(model.requests.length,0,'Opening an uploaded source must not automatically extract');
    assert.equal(await page.locator('#extract').isEnabled(),true);
    assert.equal(await page.locator('#play').isEnabled(),false);
    assert.match(await page.locator('#mix-ready-hint').textContent(),/Extract stems above/);
    const button=await page.locator('#extract').boundingBox(), video=await page.locator('.console').boundingBox();
    assert.ok(button.y+button.height<video.y,'Extraction belongs above the video and mixer');
    assert.ok(button.y+button.height<1000,'The initial action must be visible without scrolling on desktop');
    await page.waitForFunction(()=>document.querySelector('#extract-device option[value="cuda"]').disabled);
    await page.locator('#extract-device').selectOption('cpu');
    assert.equal(await page.locator('#device').inputValue(),'cpu');
    await page.screenshot({path:path.join(out,'ready-to-extract.png')});
    await page.locator('#extract').click();
    await page.locator('#extraction-progress').waitFor();
    assert.equal(model.requests.length,1);assert.equal(model.requests[0].device,'cpu');
    assert.equal(await page.locator('#extract').isDisabled(),true);
    assert.equal(await page.locator('#job-progress').isVisible(),false,'Only show extraction progress once');
    await page.locator('#cancel-extract').click();
    await page.waitForFunction(()=>document.querySelector('#extract').textContent==='Retry extraction');
    assert.equal(await page.locator('#extract').isEnabled(),true);
    await page.locator('#extract').click();model.complete();
    await page.waitForFunction(()=>document.querySelector('#extraction-title').textContent==='Your stems are ready.');
    assert.equal(await page.locator('#play').isEnabled(),true);
    assert.equal(await page.locator('#extract').isDisabled(),true);
    assert.equal(await page.locator('#mix-ready-hint').isVisible(),false);
    await page.reload();await page.waitForFunction(()=>document.querySelector('#extraction-title').textContent==='Your stems are ready.');
    assert.equal(model.requests.length,2,'Reopening a prepared mix must not rerun extraction');
    const partial=fixture(['ambience','music']);
    await page.unroute('**/api/**');await page.route('**/api/**',route=>partial.route(route));
    await page.reload();await page.waitForFunction(()=>document.querySelector('#extract').textContent==='Extract missing stems');
    assert.equal(await page.locator('#play').isEnabled(),true,'Imported tracks can be played before full extraction');
    assert.match(await page.locator('#extraction-description').textContent(),/Dialogue, Effects/);
    const imported=structuredClone(partial.data.state.tracks);
    await page.locator('#extract').click();await page.locator('#extraction-progress').waitFor();
    partial.data.task={...partial.data.task,status:'failed',active:false,message:'Could not load the model. Retry.'};
    await page.waitForFunction(()=>document.querySelector('#extract').textContent==='Retry extraction');
    assert.deepEqual(partial.data.state.tracks,imported);
    for(const width of [1100,760,390]){
      await page.setViewportSize({width,height:1000});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      const area=await page.locator('#stem-extraction').boundingBox(), consoleArea=await page.locator('.console').boundingBox();
      assert.ok(area.y+area.height<=consoleArea.y);
      await page.screenshot({path:path.join(out,`extraction-${width}.png`),fullPage:true});
    }
    assert.deepEqual(errors,[]);
    console.log('Lab extraction UI passed: prominent empty-state action, device choice, progress, cancel/retry, failures, ready/reopen, partial imports and responsive layouts.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
