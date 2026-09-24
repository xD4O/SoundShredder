/* One audio clock, bounded 20-second buffers, all active stems scheduled together. */
class LabPlayer {
  constructor(base, onTime, onStatus) {
    this.base=base; this.onTime=onTime; this.onStatus=onStatus;
    this.ctx=null; this.time=0; this.playing=false; this.serial=0; this.nodes=[]; this.channels={}; this.solo=null;
  }
  current() { return this.playing ? Math.max(this.first,Math.min(this.state.duration,this.first+this.ctx.currentTime-this.clock)) : this.time; }
  async start(time,state,audition=null) {
    this.stop(time); const serial=++this.serial;
    this.ctx ||= new AudioContext({sampleRate:48000});
    await this.ctx.resume();
    if(serial!==this.serial)return;
    this.state=structuredClone(state); this.audition=audition;
    this.abort=new AbortController(); this.onStatus('buffering');
    this.master=this.ctx.createGain(); this.master.gain.value=audition?1:LabMath.protection(state);
    this.masterMeter=this.ctx.createAnalyser(); this.masterMeter.fftSize=2048;
    this.master.connect(this.masterMeter).connect(this.ctx.destination);
    this.channels={};
    const selected=audition?{[state.assets[audition].track]:{asset:audition,regions:[]}}:state.tracks;
    for (const [name,track] of Object.entries(selected)) if (track.asset) {
      const gate=this.ctx.createGain(), analyser=this.ctx.createAnalyser(); analyser.fftSize=2048;
      gate.connect(analyser).connect(this.master);
      this.channels[name]={...track,gate,analyser,samples:new Float32Array(2048)};
    }
    if (!Object.keys(this.channels).length) { this.stop(time); this.onStatus('empty'); return; }
    this.first=Math.max(0,Math.min(time,state.duration-1/48000));
    try {
      const buffers=await this.load(this.first);
      if (serial!==this.serial) return;
      this.clock=this.ctx.currentTime+.08; this.queueEnd=this.first;
      this.playing=true; this.setSolo(this.solo); this.schedule(buffers,this.first);
      this.onStatus('playing'); this.tick();
      this.timer=setInterval(()=>this.prefetch(serial),150);
    } catch(error) { if (serial===this.serial) this.fail(error); }
  }
  async load(start) {
    const end=Math.min(this.state.duration,start+20);
    const pairs=await Promise.all(Object.entries(this.channels).map(async([name,track])=>{
      const response=await fetch(`${this.base}/assets/${track.asset}?start=${start}&seconds=${end-start}`,{signal:this.abort.signal});
      if (!response.ok) throw new Error('Could not buffer this stem. Pause and retry.');
      const buffer=await this.ctx.decodeAudioData(await response.arrayBuffer());
      return [name,buffer];
    }));
    return {end,pairs};
  }
  schedule({end,pairs},start) {
    const clock=this.clock+start-this.first;
    for (const [name,buffer] of pairs) {
      const channel=this.channels[name], node=this.ctx.createBufferSource(), gain=this.ctx.createGain();
      node.buffer=buffer; node.connect(gain).connect(channel.gate);
      LabMath.schedule(gain.gain,channel.regions,start,end,clock);
      node.start(clock); this.nodes.push(node);
      node.onended=()=>{ node.disconnect(); gain.disconnect(); this.nodes=this.nodes.filter(n=>n!==node); };
    }
    this.queueEnd=end;
  }
  async prefetch(serial) {
    if (!this.playing || this.fetching || this.queueEnd>=this.state.duration || this.queueEnd-this.current()>7) return;
    this.fetching=true;
    try {
      const start=this.queueEnd, buffers=await this.load(start);
      if (serial!==this.serial) return;
      if (this.current()>=start-.025) throw new Error('Playback paused while buffering. Press Play to continue in sync.');
      this.schedule(buffers,start);
    } catch(error) { if (serial===this.serial) this.fail(error); }
    finally { if (serial===this.serial) this.fetching=false; }
  }
  tick() {
    if (!this.playing) return;
    const time=this.current(); this.onTime(time);
    if (time>=this.state.duration) { this.stop(this.state.duration); this.onStatus('paused'); return; }
    this.animation=requestAnimationFrame(()=>this.tick());
  }
  peak(name) {
    const channel=this.channels[name];
    const analyser=name==='master'?this.masterMeter:channel?.analyser;
    if (!this.playing || !analyser) return 0;
    const samples=channel?.samples || (this.masterSamples ||=new Float32Array(2048));
    analyser.getFloatTimeDomainData(samples);
    let peak=0; for (const sample of samples) peak=Math.max(peak,Math.abs(sample)); return peak;
  }
  setSolo(name) {
    this.solo=name;
    for (const [key,channel] of Object.entries(this.channels)) channel.gate.gain.value=this.audition||!name||key===name?1:0;
  }
  fail(error) { const time=this.current(); this.stop(time); if (error.name!=='AbortError') this.onStatus('error',error.message); }
  stop(time) {
    this.time=time??this.current(); this.playing=false; ++this.serial;
    this.abort?.abort(); clearInterval(this.timer); cancelAnimationFrame(this.animation); this.fetching=false;
    for (const node of this.nodes) { try { node.stop(); node.disconnect(); } catch {} }
    this.nodes=[];
    for (const channel of Object.values(this.channels)) {channel.gate.disconnect(); channel.analyser.disconnect();}
    this.channels={}; this.master?.disconnect(); this.masterMeter?.disconnect();
  }
}
window.LabPlayer=LabPlayer;
