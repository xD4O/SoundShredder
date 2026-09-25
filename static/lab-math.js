/* Time edits use seconds; gain is dB relative to the selected asset. */
(function (root) {
  'use strict';
  const FADE = .005;
  const linear = db => db === null ? 0 : 10 ** (db / 20);
  const dbfs = value => value > 1e-6 ? 20 * Math.log10(value) : -120;
  function valueAt(regions, time) {
    return regions.find(r => r.start <= time && time < r.end)?.db ??
      (regions.some(r => r.start <= time && time < r.end && r.db === null) ? null : 0);
  }
  function gainAt(regions, time) {
    const r = regions.find(r => r.start <= time && time < r.end);
    if (!r) return 1;
    const fade = Math.min(FADE, (r.end - r.start) / 2);
    const weight = Math.max(0, Math.min(1, (time - r.start) / fade, (r.end - time) / fade));
    return 1 + (linear(r.db) - 1) * weight;
  }
  function insert(regions, start, end, db) {
    const next = [];
    for (const r of regions) {
      if (r.end <= start || r.start >= end) next.push({...r});
      else {
        if (r.start < start) next.push({...r, end:start});
        if (r.end > end) next.push({...r, start:end});
      }
    }
    if (db !== 0) next.push({start, end, db});
    return next.sort((a,b) => a.start - b.start);
  }
  function scope(time, mode, duration, fps, start, end) {
    if (mode === 'range') return [Math.max(0,start), Math.min(duration,end)];
    const unit = mode === 'frame' ? 1 / fps : 1;
    const first = Math.floor((Math.min(time,duration-1e-9) + 1e-10) / unit) * unit;
    return [first, Math.min(duration,first+unit)];
  }
  function protection(state) {
    let bound = 0;
    for (const name of Object.keys(Object.keys(state.layers||{}).length?activeTracks(state):state.tracks)) {
      const assets=Object.values(state.assets).filter(a=>a.track===name&&a.role!=='removed');
      if(assets.length)bound += Math.max(...assets.map(a=>a.peak)) * linear(6);
    }
    return Math.min(1,.98/Math.max(bound,1e-12));
  }
  const ROOTS=['speech','music','effects','ambience'];
  function activeLayer(state,name) {return Object.values(state.layers||{}).find(layer=>layer.parent_track===name&&layer.active);}
  function leafNames(state,name) {
    if(!state.tracks[name]?.asset)return [];
    const layer=activeLayer(state,name);
    return layer?layer.children.flatMap(child=>leafNames(state,child)):[name];
  }
  function activeTracks(state) {return Object.fromEntries(ROOTS.flatMap(name=>leafNames(state,name)).map(name=>[name,state.tracks[name]]));}
  function playbackTracks(state,layerId=null) {
    if(!layerId)return activeTracks(state);
    const layer=state.layers?.[layerId];
    if(!layer)return {};
    return Object.fromEntries(layer.children.flatMap(name=>leafNames(state,name)).map(name=>[name,state.tracks[name]]));
  }
  function playbackProtection(state,layerId=null) {
    const master=protection(state);if(!layerId)return master;
    // Keep an active branch at its Master level. A saved, inactive branch may
    // need additional headroom when auditioned on its own.
    let bound=0;
    for(const name of Object.keys(playbackTracks(state,layerId))){
      const assets=Object.values(state.assets).filter(a=>a.track===name&&a.role!=='removed');
      if(assets.length)bound+=Math.max(...assets.map(a=>a.peak))*linear(6);
    }
    return Math.min(master,.98/Math.max(bound,1e-12));
  }
  function reachableTracks(state) {
    const names=new Set();const visit=name=>{names.add(name);const layer=activeLayer(state,name);if(layer)layer.children.forEach(visit);};
    ROOTS.forEach(visit);return names;
  }
  function schedule(param, regions, first, last, contextFirst) {
    const points = new Set([first,last]);
    for (const r of regions) {
      const f = Math.min(FADE,(r.end-r.start)/2);
      for (const point of [r.start,r.start+f,r.end-f,r.end]) if (point>first && point<last) points.add(point);
    }
    const sorted = [...points].sort((a,b)=>a-b);
    param.setValueAtTime(gainAt(regions,first),contextFirst);
    for (const point of sorted.slice(1)) param.linearRampToValueAtTime(gainAt(regions,point),contextFirst+point-first);
  }
  const api = {FADE,linear,dbfs,valueAt,gainAt,insert,scope,protection,schedule,activeLayer,leafNames,activeTracks,reachableTracks,playbackTracks,playbackProtection};
  if (typeof module !== 'undefined') module.exports = api;
  root.LabMath = api;
})(typeof window !== 'undefined' ? window : globalThis);
