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
    for (const name of Object.keys(state.tracks)) {
      const assets=Object.values(state.assets).filter(a=>a.track===name&&a.role!=='removed');
      if(assets.length)bound += Math.max(...assets.map(a=>a.peak)) * linear(6);
    }
    return Math.min(1,.98/Math.max(bound,1e-12));
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
  const api = {FADE,linear,dbfs,valueAt,gainAt,insert,scope,protection,schedule};
  if (typeof module !== 'undefined') module.exports = api;
  root.LabMath = api;
})(typeof window !== 'undefined' ? window : globalThis);
