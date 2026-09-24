const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../../static/lab-math.js');

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
