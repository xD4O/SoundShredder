// Render the real Lab with private API fixtures: no user data or jobs change.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.env.SOUNDSHREDDER_TEST_URL||'http://127.0.0.1:7863';
const ids=['1'.repeat(32),'2'.repeat(32)];
const out=path.resolve(__dirname,'../../artifacts/mixing-lab/session-ui');
const waitFor=async predicate=>{for(let n=0;n<100;n++){if(predicate())return;await new Promise(r=>setTimeout(r,20));}throw new Error('Fixture request did not arrive');};
function fixture(){
  const items=ids.map((id,i)=>({id,filename:`Scene ${i+1}.wav`,status:'complete',closed:false}));
  const states=items.map(item=>({schema:1,revision:1,filename:item.filename,frames:144000,rate:48000,channels:1,duration:3,fps:0,video:false,
    assets:{tone:{id:'tone',track:'music',label:'Saved music',role:'original',peaks:[.1,.1,.1],peak:.1,peak_hz:1}},
    tracks:{speech:{asset:null,regions:[]},music:{asset:'tone',regions:[{start:1,end:2,db:-6}]},effects:{asset:null,regions:[]},ambience:{asset:null,regions:[]}}}));
  const bytes=Buffer.alloc(44+144000*2);bytes.write('RIFF');bytes.writeUInt32LE(bytes.length-8,4);bytes.write('WAVEfmt ',8);
  bytes.writeUInt32LE(16,16);bytes.writeUInt16LE(1,20);bytes.writeUInt16LE(1,22);bytes.writeUInt32LE(48000,24);
  bytes.writeUInt32LE(96000,28);bytes.writeUInt16LE(2,32);bytes.writeUInt16LE(16,34);bytes.write('data',36);bytes.writeUInt32LE(bytes.length-44,40);
  for(let i=0;i<144000;i++)bytes.writeInt16LE(Math.round(3000*Math.sin(i*.04)),44+i*2);
  const model={items,states,requests:[],task:null,blockSource:false,sourceRelease:null,blockAudio:false,audioRelease:null,failClose:false};
  model.route=async route=>{
    const request=route.request(),url=new URL(request.url()),method=request.method(),id=url.pathname.split('/')[3],index=ids.indexOf(id);
    model.requests.push({url:url.pathname,method});let response;
    if(url.pathname==='/api/system')response={version:'1.2.2',gpu_available:false};
    else if(url.pathname==='/api/lab/sessions')response=items;
    else if(url.pathname.endsWith('/lab/view')){
      const body=request.postDataJSON();
      if(model.failClose&&body.closed)return route.fulfill({status:503,json:{detail:'Test storage unavailable'}});
      items[index].closed=body.closed;response={id,closed:body.closed};
    }else if(url.pathname===`/api/jobs/${id}`){
      if(model.blockSource){model.blockSource=false;await new Promise(r=>{model.sourceRelease=r;});return route.fulfill({status:404,json:{detail:'Delayed old-session error'}});}
      response={...items[index],worker_active:false};
    }else if(url.pathname.endsWith('/lab'))response={state:states[index],task:model.task,stems_available:false};
    else if(url.pathname.includes('/lab/assets/')){
      if(model.blockAudio){model.blockAudio=false;await new Promise(r=>{model.audioRelease=r;});}
      return route.fulfill({contentType:'audio/wav',body:bytes});
    }else throw new Error(`Unexpected request: ${method} ${url.pathname}`);
    await route.fulfill({json:structuredClone(response)});
  };
  return model;
}
(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.SOUNDSHREDDER_TEST_BROWSER||(process.platform==='win32'?'msedge':undefined)});
  try {
    const page=await browser.newPage({viewport:{width:1500,height:1000}}),model=fixture(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{const Native=window.AudioContext;window.qaContexts=[];window.AudioContext=class extends Native{constructor(...args){super(...args);window.qaContexts.push(this);}};});
    await page.route('**/api/**',route=>model.route(route));
    await page.goto(`${base}/lab?session=${ids[0]}`);await page.locator('#work').waitFor({state:'visible'});
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor();
    const original=structuredClone(model.states);
    await page.locator('#play').click();await page.waitForFunction(()=>document.querySelector('#playback-label').textContent==='Playing in sync');
    await page.locator('#close-session').click();
    await page.waitForFunction(()=>document.querySelector('#welcome').hidden===false&&!document.querySelector('#source-file').disabled);
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor({state:'detached'});
    await page.waitForFunction(()=>window.qaContexts.every(ctx=>ctx.state==='closed'));
    assert.equal(new URL(page.url()).search,'');assert.equal(await page.locator('#work').isVisible(),false);
    assert.equal(model.items[0].closed,true);
    await page.locator(`#sessions [data-session="${ids[1]}"] button`).click();
    await page.waitForFunction(()=>document.querySelector('#closed-count').textContent==='2');
    assert.equal(await page.locator('#sessions .session-row').count(),0);
    await page.reload();await page.waitForFunction(()=>document.querySelector('#closed-count').textContent==='2');
    assert.equal(await page.locator('#sessions .session-row').count(),0);
    await page.locator('#closed-sessions summary').click();
    await page.screenshot({path:path.join(out,'closed-sessions.png')});
    await page.locator(`#closed-session-list a[href$="${ids[0]}"]`).click();await page.locator('#work').waitFor({state:'visible'});
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor();
    assert.equal(model.items[0].closed,false);assert.deepEqual(model.states,original,'Closing must retain every saved track and edit');
    // Closing during buffering releases pending audio and cannot revive playback.
    model.blockAudio=true;await page.locator('#play').click();await waitFor(()=>model.audioRelease);
    await page.locator('#close-session').click();model.audioRelease();
    await page.waitForFunction(()=>window.qaContexts.every(ctx=>ctx.state==='closed'));
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor({state:'detached'});
    assert.equal(await page.locator('#work').isVisible(),false);
    // A close during extraction leaves uploads usable; it does not cancel work.
    model.task={id:'task',operation:'extract',active:true,status:'running',progress:.4,message:'Separating…'};
    model.states[0].tracks.music.asset=null;
    await page.goto(`${base}/lab?session=${ids[0]}`);await page.locator('#extraction-progress').waitFor({state:'visible'});
    assert.equal(await page.locator('#source-file').isDisabled(),true);
    await page.locator('#close-session').click();await page.locator('#welcome').waitFor({state:'visible'});
    assert.equal(await page.locator('#source-file').isEnabled(),true);
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor({state:'detached'});
    assert.equal(model.task.active,true);assert.equal(model.requests.some(r=>r.url.endsWith('/cancel')),false);
    // A delayed failure from an opening session must not overwrite a newer view.
    model.task=null;model.blockSource=true;
    await page.locator('#closed-sessions summary').click();
    await page.locator(`#closed-session-list a[href$="${ids[0]}"]`).click();await waitFor(()=>model.sourceRelease);
    await page.locator('#new-session').click();model.sourceRelease();
    await page.waitForResponse(r=>r.url().endsWith(`/api/jobs/${ids[0]}`)&&r.status()===404);
    await page.waitForFunction(()=>document.querySelector('#sessions .session-row'));
    assert.equal(await page.locator('#notice').isVisible(),false);
    assert.equal(await page.locator('#work').isVisible(),false);
    // Failed persistence must show an error and leave the session recoverable.
    model.failClose=true;await page.locator(`#sessions [data-session="${ids[0]}"] button`).click();
    await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Could not close'));
    assert.equal(model.items[0].closed,false);
    model.failClose=false;await page.locator(`#sessions [data-session="${ids[0]}"] button`).click();
    await page.locator(`#sessions [data-session="${ids[0]}"]`).waitFor({state:'detached'});
    assert.equal(model.items[0].closed,true);assert.deepEqual(errors,[]);
    assert.equal(model.requests.some(r=>r.method==='DELETE'),false);
    console.log('Lab session UI passed: close from workspace/sidebar, persistence, reopen, retained edits, released playback, buffering/processing close, late responses and storage failure.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
