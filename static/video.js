"use strict";
// Audio is the playback clock. The footage never contributes a second soundtrack.
const videoPreview = (() => {
  const el = id => document.getElementById(id);
  const video = el("footage"), toggle = el("show-video"), select = el("video-track");
  const players = [...document.querySelectorAll("audio")];
  let source = null, selected = el("original-audio"), frame = null, failed = false;
  try { toggle.checked = localStorage.getItem("soundshredder.showVideo") !== "false"; } catch { /* Storage may be disabled. */ }
  const time = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
  const available = player => !!player.getAttribute("src");
  const visible = () => !!source && toggle.checked && !failed;
  function refresh() {
    for (const option of select.options) option.disabled = !available(el(option.value));
    el("video-play").disabled = !available(selected) || failed;
    const duration = Number.isFinite(selected.duration) ? selected.duration : 0;
    el("video-seek").max = duration;
    el("video-seek").value = selected.currentTime || 0;
    el("video-seek").disabled = !duration || failed;
    el("video-time").textContent = `${time(selected.currentTime || 0)} / ${time(duration)}`;
    el("video-play").textContent = selected.paused ? "Play" : "Pause";
  }
  function align(force = false) {
    if (!visible() || video.readyState < 1) return;
    const target = Math.min(selected.currentTime || 0, Number.isFinite(video.duration) ? video.duration : Infinity);
    if (force || Math.abs(video.currentTime - target) > .12) video.currentTime = target;
    video.playbackRate = selected.playbackRate;
    video.muted = true;
  }
  function stopFrames() { cancelAnimationFrame(frame); frame = null; }
  function tick() {
    frame = null;
    align(); refresh();
    if (visible() && !selected.paused) frame = requestAnimationFrame(tick);
  }
  function follow() {
    stopFrames(); align(true); refresh();
    if (visible() && !selected.paused && !selected.ended) {
      video.play().catch(error => {
        if (error.name !== "AbortError" && visible() && !selected.paused) el("video-help").textContent = "Video playback could not start. Pause and press Play to retry; audio is still available.";
      });
      frame = requestAnimationFrame(tick);
    } else video.pause();
  }
  function choose(player) {
    selected = player; select.value = player.id; follow();
  }
  players.forEach(player => {
    player.addEventListener("play", () => choose(player));
    for (const event of ["pause", "ended", "seeking", "seeked", "ratechange", "loadedmetadata", "emptied"])
      player.addEventListener(event, () => { if (selected === player) follow(); else refresh(); });
    player.addEventListener("waiting", () => { if (selected === player) { video.pause(); stopFrames(); } });
    player.addEventListener("playing", () => { if (selected === player) follow(); });
    player.addEventListener("timeupdate", () => { if (selected === player) { align(); refresh(); } });
  });
  new MutationObserver(refresh).observe(document.body, {subtree:true, attributes:true, attributeFilter:["src"]});
  select.addEventListener("change", () => {
    const next = el(select.value), position = selected.currentTime, resume = !selected.paused;
    selected.pause(); choose(next);
    if (Number.isFinite(next.duration)) next.currentTime = Math.min(position, Math.max(0, next.duration - .01));
    if (resume) next.play().catch(() => {});
    follow();
  });
  el("video-play").addEventListener("click", () => {
    if (selected.paused) selected.play().catch(() => {
      el("video-help").textContent = "This audio cannot play in your browser yet. Try a prepared audio track after processing.";
    });
    else selected.pause();
  });
  el("video-seek").addEventListener("input", event => {
    if (Number.isFinite(selected.duration)) selected.currentTime = Number(event.target.value);
    align(true); refresh();
  });
  toggle.addEventListener("change", () => {
    try { localStorage.setItem("soundshredder.showVideo", String(toggle.checked)); } catch { /* Optional preference. */ }
    el("video-body").hidden = !toggle.checked; follow();
  });
  video.addEventListener("loadedmetadata", () => {
    if (!video.videoWidth) {
      failed = true;
      el("video-help").textContent = "No playable video stream found. Audio cleanup is still available.";
      refresh(); return;
    }
    follow();
  });
  video.addEventListener("error", () => {
    if (!source) return;
    failed = true; stopFrames();
    el("video-help").textContent = "Your browser cannot preview this video codec. Try an H.264 MP4 for preview; audio cleanup is still available.";
    refresh();
  });
  video.addEventListener("playing", () => {
    if (!failed) el("video-help").textContent = "Footage follows the selected audio. Preview only; downloads remain audio files.";
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) { video.pause(); stopFrames(); } else follow(); });
  return {
    setSource(url) {
      if (source === url) return;
      source = url; failed = false; stopFrames(); video.pause();
      el("video-panel").hidden = !url;
      el("video-body").hidden = !toggle.checked;
      el("video-help").textContent = "Footage follows the selected audio. Preview only; downloads remain audio files.";
      if (url) video.src = url;
      else { video.removeAttribute("src"); selected = el("original-audio"); select.value = selected.id; }
      video.load(); refresh();
    },
  };
})();
