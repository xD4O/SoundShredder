const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../../static/lab-math.js');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

test('closing while audio is waking up releases its context without a late playback error',async()=>{
  let context,rejectResume;const statuses=[];
  class AudioContext {
    constructor(){this.state='suspended';context=this;}
    resume(){return new Promise((_,reject)=>{rejectResume=reject;});}
    close(){this.state='closed';rejectResume(new Error('Audio context closed'));return Promise.resolve();}
  }
  const sandbox={window:{},AudioContext,LabMath:M,clearInterval,cancelAnimationFrame(){}};
  vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../static/lab-player.js'),'utf8'),sandbox);
  const player=new sandbox.window.LabPlayer('/qa',()=>{},status=>statuses.push(status));
  const starting=player.start(0,{duration:3});player.dispose();await starting;
  assert.equal(context.state,'closed');assert.equal(player.ctx,null);
  assert.equal(player.playing,false);assert.deepEqual(statuses,[]);
});

test('time edits restore baseline and preserve previous non-overlapping edits',()=>{
  let regions=M.insert([],7,8,-9);
  assert.equal(M.valueAt(regions,7.5),-9);assert.equal(M.valueAt(regions,8),0);
  regions=M.insert(regions,7.25,7.5,-12);
  assert.deepEqual(regions,[{start:7,end:7.25,db:-9},{start:7.25,end:7.5,db:-12},{start:7.5,end:8,db:-9}]);
  regions=M.insert(regions,7.3,7.7,0);
  assert.equal(M.valueAt(regions,7.6),0);assert.equal(M.valueAt(regions,7.8),-9);
});
test('frame edits last one nominal frame and scoped mute is true silence inside its fades',()=>{
  const [start,end]=M.scope(7.3,'frame',15,24);
  assert.ok(Math.abs(end-start-1/24)<1e-10);
  const r=M.insert([],start,end,null);
  assert.equal(M.gainAt(r,start+.02),0);assert.equal(M.gainAt(r,end+.01),1);
  assert.equal(M.gainAt(r,start),1);
  assert.equal(M.valueAt(r,start+.02),null);
  assert.deepEqual(M.scope(8,'second',15,24),[8,9]);
});
test('audio gain scheduling uses the same edge fades as export',()=>{
  const events=[];const param={setValueAtTime:(v,t)=>events.push([v,t]),linearRampToValueAtTime:(v,t)=>events.push([v,t])};
  M.schedule(param,[{start:1,end:2,db:-6}],0,3,10);
  [10,11,11.005,11.995,12,13].forEach((time,i)=>assert.ok(Math.abs(events[i][1]-time)<1e-10));
  assert.ok(Math.abs(events[2][0]-10**(-6/20))<1e-12);
  assert.equal(events.at(-1)[0],1);
});
test('reserved output headroom stays fixed when a timed edit or channel selection changes',()=>{
  const state={tracks:{speech:{asset:'a',regions:[]},music:{asset:'b',regions:[]}},
    assets:{a:{track:'speech',role:'original',peak:.5},b:{track:'music',role:'imported',peak:.4}}};
  const trim=M.protection(state);assert.ok(trim<1);
  state.tracks.music.regions=[{start:7,end:8,db:6}];
  assert.equal(M.protection(state),trim);
  state.tracks.music.asset=null;
  assert.equal(M.protection(state),trim);
});

test('nested layers play and export leaves without their parent being counted again',()=>{
  const track=asset=>({asset,regions:[]});
  const state={tracks:{speech:track('a'),music:track('b'),effects:track('c'),ambience:track(null),child:track('d'),rest:track('e'),deep:track('f')},
    assets:Object.fromEntries(['speech','music','effects','child','rest','deep'].map((name,i)=>[String.fromCharCode(97+i),{track:name,role:'split',peak:.1}])),
    layers:{L2:{id:'L2',parent_track:'effects',children:['child','rest'],active:true},L3:{id:'L3',parent_track:'child',children:['deep'],active:true}}};
  assert.deepEqual(Object.keys(M.activeTracks(state)),['speech','music','deep','rest']);
  assert.deepEqual(M.leafNames(state,'effects'),['deep','rest']);
  assert.deepEqual(Object.keys(M.playbackTracks(state,'L2')),['deep','rest']);
  assert.deepEqual(Object.keys(M.playbackTracks(state,'L3')),['deep']);
  assert.deepEqual(M.playbackTracks(state),M.activeTracks(state));
  assert.deepEqual(M.playbackTracks(state,'missing'),{});
  assert.equal(M.playbackProtection(state,'L2'),M.protection(state));
  const gain=M.protection(state);state.tracks.deep.regions=[{start:0,end:1,db:6}];assert.equal(M.protection(state),gain);
  state.layers.L2.active=false;
  assert.deepEqual(Object.keys(M.activeTracks(state)),['speech','music','effects']);
  assert.equal(M.reachableTracks(state).has('deep'),false);
  assert.deepEqual(Object.keys(M.playbackTracks(state,'L2')),['deep','rest'],'a saved layer can be previewed without changing Master');
  state.layers.L2.active=true;assert.equal(M.reachableTracks(state).has('deep'),true);
  state.tracks.deep.asset=null;state.tracks.rest.asset=null;
  assert.deepEqual(M.playbackTracks(state,'L2'),{},'an empty layer must never fall back to unrelated stems');
});

test('inactive layer preview reserves its own headroom without boosting above Master',()=>{
  const state={tracks:{music:{asset:'a',regions:[]},child:{asset:'b',regions:[]}},
    assets:{a:{track:'music',role:'original',peak:.01},b:{track:'child',role:'split',peak:1}},
    layers:{L2:{id:'L2',parent_track:'music',children:['child'],active:false}}};
  assert.equal(M.protection(state),1);
  const trim=M.playbackProtection(state,'L2');assert.ok(trim<1);
  assert.ok(trim*M.linear(6)<=.98);
  state.tracks.child.regions=[{start:0,end:1,db:6}];
  assert.equal(M.playbackProtection(state,'L2'),trim);
});
