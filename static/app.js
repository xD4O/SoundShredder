"use strict";
const $ = (id) => document.getElementById(id);
const stems = ["speech", "music", "effects"];
const presets = {
  "no-music": [1, 0, 1], dialogue: [1, 0, 0], effects: [0, 0, 1],
  "no-effects": [1, 1, 0], "no-dialogue": [0, 1, 1],
};
let selectedFile = null, currentJob = null, jobData = null, busy = false;
let sourceURL = null, pollTimer = null, startedAt = null, lastMix = null;
let sourcePeaks = null, mixPeaks = null, mode = "stems", bubbleAvailable = false;
let multipassAvailable = false, rerunAvailable = false;
let updatesAvailable = false;
let listeningAvailable = false, listeningTimer = null, listeningData = null, listeningBusy = false, activeAudio = null;
let listeningAnchorPending = location.hash === "#listening-panel";
const listeningColors = {speech:"#79f6d3", music:"#8eaeff", effects:"#c2a0ff", removed:"#ffbe96"};
const trackAudio = (name) => $(name === "removed" ? "removed-audio" : "preview-" + name);

// Decorative signal motifs. These are illustrations, not measurements of a file.
document.querySelectorAll(".track-wave").forEach((element, index) => {
  for (let i = 0; i < 42; i++) {
    const bar = document.createElement("i");
    const envelope = Math.sin(Math.PI * (i + 1) / 43);
    const detail = Math.abs(Math.sin(i * (index + 1) * 0.7 + index * 2));
    bar.style.setProperty("--h", `${4 + envelope * (9 + detail * 22)}px`);
    bar.style.setProperty("--opacity", (0.24 + envelope * 0.57).toFixed(2));
    element.append(bar);
  }
});
$("hero-signal").setAttribute("d", Array.from({length: 47}, (_, i) => {
  const envelope = Math.exp(-Math.pow((i - 23) / 12, 2));
  const detail = .2 + .8 * Math.abs(Math.sin(i * .83) * Math.cos(i * .17));
  const height = 3 + 172 * envelope * detail;
  return `M${43 + i * 9} ${(125 - height / 2).toFixed(1)}v${height.toFixed(1)}`;
}).join(" "));

function showError(message) { $("error").textContent = message; $("error").hidden = false; }
function clearError() { $("error").hidden = true; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Please check the selected settings and try again.");
  return data;
}
function gains() { return Object.fromEntries(stems.map(s => [s, Number($("level-" + s).value) / 100])); }
function sameGains(a, b) { return a && b && stems.every(s => Math.abs(a[s] - b[s]) < 0.001); }
function cleanupSettings() {
  const ranged = $("bubble-range").checked;
  return {kind: $("bubble-type").value, strength: Number($("bubble-strength").value) / 100,
    passes: multipassAvailable && $("bubble-type").value === "water" && $("bubble-multipass").checked ? Number($("bubble-passes").value) : 1,
    start: ranged ? Number($("bubble-start").value) : 0, end: ranged ? Number($("bubble-end").value) : null};
}
function checkCleanup() {
  const value = cleanupSettings();
  if (!Number.isFinite(value.start) || value.start < 0 ||
      (value.end !== null && (!$("bubble-start").value || !$("bubble-end").value || !Number.isFinite(value.end) || value.end <= value.start)))
    throw new Error("Enter a valid time range in seconds, with the end after the start.");
  return value;
}
function setCleanup(value) {
  $("bubble-type").value = value.kind;
  $("bubble-strength").value = Math.round(value.strength * 100);
  $("bubble-range").checked = value.start > 0 || value.end !== null;
  $("bubble-start").value = value.start;
  $("bubble-end").value = value.end ?? "";
  $("bubble-multipass").checked = (value.passes || 1) > 1;
  $("bubble-passes").value = String(Math.max(2, value.passes || 1));
}
function setMode(value) {
  mode = value;
  $("bubble-settings").hidden = mode !== "bubble";
  document.querySelector(".tracks").hidden = mode === "bubble";
  document.querySelector(".mix-foot").hidden = mode === "bubble";
  $("separate").innerHTML = mode === "bubble" ? "Clean up bubbles <span>↗</span>" : "Separate audio <span>↗</span>";
  updateControls();
}
function formatTime(value) { const seconds = Math.floor(value); return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`; }
function fileURL(name) { return `/api/jobs/${currentJob}/files/${encodeURIComponent(name)}`; }
function previewURL(name) { return fileURL(name) + "?preview=true"; }
function setBusy(value) {
  busy = value;
  document.body.classList.toggle("busy", value);
  for (const id of ["file-input", "change-file", "device", "cpu-fallback", "new-session", "delete-session", "prepare-listening", "bubble-type", "bubble-range", "bubble-start", "bubble-end"])
    $(id).disabled = value;
  document.querySelectorAll(".level,.toggle input,.preset").forEach(el => { el.disabled = value; });
  updateControls();
  $("action-title").textContent = value ? "Finding the sound beneath the noise." :
    jobData?.status === "complete" ? "Your sound is ready for its next scene." :
    selectedFile ? "Your file is in. Let’s find the good stuff." : "A little less noise. A lot more you.";
}
function updateControls() {
  const values = gains();
  stems.forEach(s => {
    const on = values[s] > 0;
    $("keep-" + s).checked = on;
    $("value-" + s).value = `${Math.round(values[s] * 100)}%`;
    const card = document.querySelector(`[data-stem="${s}"]`);
    card.classList.toggle("removed", !on);
    card.querySelector(".track-state").textContent = !on ? "REMOVE" : values[s] < 1 ? "REDUCED" : "KEEP";
    card.querySelector(".level-label label").textContent = !on ? "REMOVE FROM MIX" : values[s] < 1 ? "REDUCE IN MIX" : "KEEP IN MIX";
    $("level-" + s).style.setProperty("--level", `${values[s] * 100}%`);
  });
  document.querySelectorAll(".preset").forEach(button => {
    const match = button.dataset.preset === "bubble" ? mode === "bubble" : mode === "stems" && presets[button.dataset.preset].every((v, i) => v === values[stems[i]]);
    if (button.dataset.preset === "bubble") button.disabled = busy || !bubbleAvailable;
    button.classList.toggle("active", match); button.setAttribute("aria-pressed", match);
  });
  const kept = stems.filter(s => values[s] > 0).map(s => s === "speech" ? "dialogue" : s === "effects" ? "effects" : "music");
  const description = kept.length ? `Keep ${kept.join(" + ")}. Adjust each layer to taste.` : "All layers removed. Your cleaned mix will be silent.";
  $("mix-description").textContent = description;
  $("bubble-strength-value").value = `${$("bubble-strength").value}%`;
  $("bubble-strength").style.setProperty("--level", `${$("bubble-strength").value}%`);
  $("bubble-multipass-panel").hidden = $("bubble-type").value !== "water";
  $("bubble-multipass").disabled = busy || !multipassAvailable;
  $("bubble-passes").disabled = busy || !multipassAvailable || !$("bubble-multipass").checked;
  $("bubble-pass-help").textContent = multipassAvailable ?
    "Catch stubborn bubbles by analyzing the cleaned audio again. Each pass applies your reduction level. Extra passes take longer and may reduce wanted effects." :
    "Restart the updated SoundShredder app to enable multi-pass cleanup.";
  $("separate").disabled = busy || !(selectedFile || (rerunAvailable && currentJob && jobData?.status === "complete"));
  for (const id of ["bubble-start", "bubble-end"]) $(id).disabled = busy || !$("bubble-range").checked;
  if (lastMix && jobData?.status === "complete") {
    const settings = cleanupSettings();
    const priorPasses = lastMix.cleanup?.passes || 1;
    const changedCleanup = mode === "bubble" && ["strength", "start", "end"].some(key => settings[key] !== lastMix.cleanup?.[key]);
    const needsSeparation = mode !== (lastMix.mode || "stems") || (mode === "bubble" &&
      (settings.kind !== lastMix.cleanup?.kind || settings.passes !== priorPasses || (changedCleanup && Math.max(settings.passes, priorPasses) > 1)));
    const dirty = needsSeparation || (mode === "bubble" ?
      changedCleanup : !sameGains(values, lastMix.gains));
    $("render-mix").hidden = !dirty || needsSeparation;
    for (const id of ["download-mix", "download-bundle", "download-report"]) $(id).hidden = dirty;
    $("download-removed").hidden = dirty || !listeningData?.tracks.removed.file;
    $("listening-notice").hidden = !dirty;
    $("listening-notice").textContent = "Removed sounds is from your previous export. Apply your settings to refresh that track.";
    $("result-notice").hidden = !dirty && !(jobData.report?.warnings?.length);
    $("result-notice").textContent = needsSeparation ? (rerunAvailable ?
      "These settings need a fresh cleanup. Click Clean up again to reuse the saved source in a new session. The preview is your previous result." :
      "These settings need a new separation. Choose the source file again. The preview is your previous result.") :
      dirty ? "Settings changed. Update the mix to hear and download these settings. The preview below is the previous mix." : (jobData.report?.warnings || []).join(" ");
  }
}

function setGains(values) { stems.forEach((s, i) => { $("level-" + s).value = Math.round((Array.isArray(values) ? values[i] : values[s]) * 100); }); updateControls(); }

function drawWave(canvas, peaks, color) {
  const rect = canvas.getBoundingClientRect(); if (!rect.width) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const width = rect.width, height = rect.height;
  ctx.strokeStyle = "#304856"; ctx.beginPath(); ctx.moveTo(0, height / 2); ctx.lineTo(width, height / 2); ctx.stroke();
  if (!peaks) return;
  const peak = Math.max(...peaks, 0.02);
  const step = width / peaks.length;
  ctx.fillStyle = color;
  peaks.forEach((v, i) => { const h = Math.max(2, v / peak * height * 0.83); ctx.fillRect(i * step, (height - h) / 2, Math.max(1, step - 1.5), h); });
}
function redraw() {
  drawWave($("source-wave"), sourcePeaks, "#78ceca"); drawWave($("result-wave"), mixPeaks, "#79f6d3");
  for (const name of [...stems, "removed"]) drawWave($("listen-wave-" + name), listeningData?.tracks[name]?.waveform, listeningColors[name]);
}
window.addEventListener("resize", redraw);

function reset() {
  if (busy) return;
  videoPreview.setSource(null);
  clearTimeout(listeningTimer); listeningData = null; listeningBusy = false; activeAudio = null; $("listening-panel").hidden = true;
  clearTimeout(pollTimer); currentJob = null; jobData = null; lastMix = null; selectedFile = null;
  if (sourceURL) URL.revokeObjectURL(sourceURL); sourceURL = null;
  $("file-input").value = ""; $("dropzone").hidden = false; $("source-selected").hidden = true;
  $("results").hidden = true; $("progress-panel").hidden = true;
  $("action-help").textContent = "Add your file to start separating.";
  document.querySelectorAll("audio").forEach(a => { a.pause(); a.removeAttribute("src"); a.load(); });
  clearError(); setCleanup({kind:"water", strength:.85, start:7, end:11}); $("bubble-range").checked = false; setMode("stems"); setGains(presets["no-music"]); setBusy(false);
  $("separate").innerHTML = "Separate audio <span>↗</span>";
}
function selectFile(file) {
  if (!file || busy) return;
  if (file.size > 500 * 1024 * 1024) { showError("Choose a file smaller than 500 MB."); return; }
  if (!file.size) { showError("That file is empty. Choose an audio file with some sound."); return; }
  const selectedMode = mode, selectedGains = gains(), selectedCleanup = cleanupSettings();
  reset(); selectedFile = file;
  setCleanup(selectedCleanup); setMode(selectedMode); setGains(selectedGains);
  $("dropzone").hidden = true; $("source-selected").hidden = false;
  $("file-name").textContent = file.name;
  $("file-meta").textContent = `${(file.size / 1048576).toFixed(1)} MB · ready to separate`;
  sourceURL = URL.createObjectURL(file); $("original-audio").src = sourceURL;
  videoPreview.setSource(/\.(mp4|mov|mkv|webm)$/i.test(file.name) ? sourceURL : null);
  sourcePeaks = null; $("wave-label").hidden = false;
  requestAnimationFrame(redraw); setBusy(false);
  $("action-help").textContent = mode === "bubble" ? "Choose the bubble type and time range, then clean up your clip." : "Choose your layers, then separate. Your original stays untouched.";
}
$("file-input").addEventListener("change", e => selectFile(e.target.files[0]));
$("change-file").addEventListener("click", () => $("file-input").click());
$("new-session").addEventListener("click", reset);
for (const type of ["dragenter", "dragover"]) $("dropzone").addEventListener(type, e => { e.preventDefault(); if (!busy) $("dropzone").classList.add("drag-over"); });
for (const type of ["dragleave", "drop"]) $("dropzone").addEventListener(type, e => { e.preventDefault(); $("dropzone").classList.remove("drag-over"); });
$("dropzone").addEventListener("drop", e => { if (e.dataTransfer.files.length !== 1) showError("Drop one file at a time."); else selectFile(e.dataTransfer.files[0]); });
stems.forEach(s => {
  $("level-" + s).addEventListener("input", updateControls);
  $("keep-" + s).addEventListener("change", () => { $("level-" + s).value = $("keep-" + s).checked ? 100 : 0; updateControls(); });
});
document.querySelectorAll(".preset").forEach(button => button.addEventListener("click", () => {
  setMode(button.dataset.preset === "bubble" ? "bubble" : "stems");
  setGains(mode === "bubble" ? [1, 1, 1] : presets[button.dataset.preset]);
}));
for (const id of ["bubble-type", "bubble-strength", "bubble-range", "bubble-start", "bubble-end", "bubble-multipass", "bubble-passes"]) {
  $(id).addEventListener("input", updateControls);
  $(id).addEventListener("change", updateControls);
}

$("device").addEventListener("change", () => {
  $("hardware-help").textContent = $("device").value === "cpu" ? "CPU selected. This can take several minutes per clip." : "Auto prefers NVIDIA GPU when available.";
});

function applyMix(mix) {
  lastMix = mix; mixPeaks = mix.waveform;
  $("mix-audio").src = previewURL(mix.mix);
  $("download-mix").href = fileURL(mix.mix);
  $("download-bundle").href = fileURL(mix.bundle);
  $("download-report").href = fileURL(mix.report);
  refreshListening(currentJob);
  updateControls(); requestAnimationFrame(redraw);
}
function showResult(data) {
  $("progress-panel").hidden = true; $("results").hidden = false;
  const bubble = data.report.mode === "bubble";
  $("download-bundle").textContent = bubble ? "Cleaned + removed (.zip) ↓" : "All tracks + mix (.zip) ↓";
  $("result-device").textContent = `${data.report.device === "cuda" ? "GPU" : "CPU"}${bubble ? ` · ${data.report.passes || 1} PASS${data.report.passes > 1 ? "ES" : ""}` : ""} · COMPLETE`;
  $("result-meta").textContent = `${data.report.output_format || "24-bit WAV"} · ${data.report.sample_rate / 1000} kHz · ${data.report.channels === 2 ? "Stereo" : "Mono"} · ${formatTime(data.report.duration)} · Timing verified`;
  applyMix(data.mix);
  $("action-help").textContent = bubble ? "Check Removed sounds for everything taken out. Multi-pass changes need a fresh cleanup; Clean up again reuses your saved source." : "Your tracks are ready. Adjust the levels above, then update your mix.";
  $("separate").innerHTML = bubble ? "Clean up again <span>↗</span>" : "Separate again <span>↗</span>";
}
function updateSource(data) {
  if (data.video_preview !== undefined) videoPreview.setSource(data.video_preview ? `/api/jobs/${currentJob}/video` : null);
  if (!data.source) return;
  sourcePeaks = data.source.waveform;
  $("file-name").textContent = data.filename;
  $("file-meta").textContent = `${formatTime(data.source.duration)} · ${data.source.sample_rate / 1000} kHz · ${data.source.channels === 2 ? "Stereo" : "Mono"}`;
  $("dropzone").hidden = true; $("source-selected").hidden = false; $("wave-label").hidden = true;
  const target = previewURL("original.wav");
  // Use the decoded track for A/B: video-container duration may include extra padding.
  if ($("original-audio").getAttribute("src") !== target) {
    $("original-audio").src = target;
    if (sourceURL) URL.revokeObjectURL(sourceURL);
    sourceURL = null;
  }
  requestAnimationFrame(redraw);
}
async function poll(id) {
  if (id !== currentJob) return;
  try {
    const data = await api(`/api/jobs/${id}`); if (id !== currentJob) return;
    jobData = data; updateSource(data);
    $("progress-message").textContent = data.message;
    $("progress").value = data.progress;
    $("progress-percent").textContent = `${Math.round(data.progress * 100)}%`;
    $("elapsed").textContent = startedAt ? `${formatTime((Date.now() - startedAt) / 1000)} elapsed` : "Session restored";
    if (data.status === "running") { pollTimer = setTimeout(() => poll(id), 1400); return; }
    setBusy(false); $("cancel").disabled = false;
    if (data.status === "complete") showResult(data);
    else { $("progress-panel").hidden = true; showError(data.message); }
    await refreshHistory();
  } catch (error) {
    if (id !== currentJob) return;
    $("progress-message").textContent = "Connection interrupted. Reconnecting… Keep the app window open.";
    pollTimer = setTimeout(() => poll(id), 3500);
  }
}
$("separate").addEventListener("click", async () => {
  if (busy || !(selectedFile || (rerunAvailable && currentJob && jobData?.status === "complete"))) return;
  clearError();
  try { if (mode === "bubble") checkCleanup(); } catch (error) { showError(error.message); return; }
  setBusy(true); startedAt = Date.now();
  $("results").hidden = true; $("listening-panel").hidden = true; clearTimeout(listeningTimer); $("progress-panel").hidden = false;
  $("progress-message").textContent = selectedFile ? "Uploading to your local workspace…" : "Reusing your saved source in a new session…"; $("progress").value = 0;
  $("cancel").disabled = true;
  const settingsToSend = {...gains(), device:$("device").value, cpu_fallback:$("cpu-fallback").checked, mode};
  if (mode === "bubble") {
    const settings = cleanupSettings();
    Object.assign(settingsToSend, {bubble_type:settings.kind, bubble_strength:settings.strength,
      range_start:settings.start, range_end:settings.end});
    if (multipassAvailable) settingsToSend.bubble_passes = settings.passes;
  }
  try {
    let data;
    if (selectedFile) {
      const form = new FormData(); form.append("file", selectedFile);
      Object.entries(settingsToSend).forEach(([key, value]) => { if (value !== null) form.append(key, value); });
      data = await api("/api/jobs", {method:"POST", body:form});
    } else {
      data = await api(`/api/jobs/${currentJob}/rerun`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(settingsToSend)});
    }
    currentJob = data.id; lastMix = null; $("cancel").disabled = false;
    history.replaceState(null, "", `?session=${currentJob}`);
    document.querySelectorAll("audio").forEach(a => a.pause());
    await poll(currentJob); await refreshHistory();
  } catch (error) { showError(error.message); $("progress-panel").hidden = true; setBusy(false); if (jobData?.status === "complete") showResult(jobData); }
});
$("cancel").addEventListener("click", async () => {
  if (!currentJob) return;
  $("cancel").disabled = true;
  try { await api(`/api/jobs/${currentJob}/cancel`, {method:"POST"}); clearTimeout(pollTimer); await poll(currentJob); }
  catch (error) { showError(error.message); $("cancel").disabled = false; }
});
$("render-mix").addEventListener("click", async () => {
  if (!currentJob) return;
  const id = currentJob; $("render-mix").disabled = true; clearError(); setBusy(true);
  try {
    const levels = gains();
    if (mode === "bubble") {
      const settings = checkCleanup();
      Object.assign(levels, {bubble_strength:settings.strength, range_start:settings.start, range_end:settings.end});
      if (multipassAvailable) levels.bubble_passes = settings.passes;
    }
    const mix = await api(`/api/jobs/${id}/mix`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(levels)});
    if (currentJob === id) { jobData.mix = mix; applyMix(mix); }
  } catch (error) { showError(error.message); }
  finally { $("render-mix").disabled = false; setBusy(false); }
});
async function openSession(id) {
  if (busy && id !== currentJob) { showError("Finish or cancel the current separation before opening another session."); return; }
  if (busy) return;
  reset(); currentJob = id;
  try {
    const data = await api(`/api/jobs/${id}`); jobData = data;
    if (data.settings?.mode === "bubble") { setCleanup(data.mix?.cleanup || data.settings.cleanup); setMode("bubble"); }
    setGains(data.mix?.gains || data.settings?.gains || presets["no-music"]);
    if (data.settings) { $("device").value = data.settings.device; $("cpu-fallback").checked = data.settings.cpu_fallback; }
    updateSource(data);
    if (data.status === "complete") showResult(data);
    else if (data.status === "running") { setBusy(true); $("progress-panel").hidden = false; await poll(id); }
    else showError(data.message);
  } catch (error) { showError(error.message); }
}
async function refreshHistory() {
  try {
    const history = await api("/api/jobs"); $("history").replaceChildren();
    if (!history.length) { const p = document.createElement("p"); p.className="muted small"; p.textContent="Your sessions will appear here."; $("history").append(p); }
    history.forEach(item => {
      const button=document.createElement("button"); button.className="history-item";
      const title=document.createElement("strong"); title.textContent=item.filename;
      const status=document.createElement("small"); status.textContent=item.status === "complete" ? "✓ Ready to mix" : item.status;
      button.append(title,status); button.addEventListener("click",()=>openSession(item.id));
      const row = document.createElement("div"); row.className = "history-row";
      const remove = document.createElement("button"); remove.className = "history-delete";
      remove.textContent = "×"; remove.setAttribute("aria-label", `Delete session ${item.filename}`);
      remove.disabled = item.status === "running";
      remove.addEventListener("click", async () => {
        if (!confirm(`Delete the local session for ${item.filename}, including generated files? The original stays unchanged.`)) return;
        try { await api(`/api/jobs/${item.id}`, {method:"DELETE"}); if (currentJob === item.id) reset(); await refreshHistory(); }
        catch (error) { showError(error.message); }
      });
      row.append(button, remove); $("history").append(row);
    });
  } catch (error) { showError("Could not load sessions. Make sure SoundShredder is running."); }
}
$("refresh-history").addEventListener("click", refreshHistory);
$("delete-session").addEventListener("click", async () => {
  if (!currentJob || !confirm("Delete this local session, its uploaded copy, and all generated tracks? Your original file stays unchanged.")) return;
  try { await api(`/api/jobs/${currentJob}`, {method:"DELETE"}); reset(); await refreshHistory(); }
  catch (error) { showError(error.message); }
});
function showListening(data) {
  listeningData = data; $("listening-panel").hidden = false;
  const running = data.status === "running";
  if (running !== listeningBusy) { listeningBusy = running; setBusy(running); }
  $("listening-progress").hidden = !running;
  $("listening-meter").value = data.progress || 0;
  $("listening-message").textContent = data.message || "Preparing tracks…";
  $("cancel-listening").hidden = !running; $("cancel-listening").disabled = false;
  $("prepare-listening").hidden = running || !data.missing.length;
  $("prepare-listening").disabled = busy || !listeningAvailable;
  $("listening-count").textContent = `${4 - data.missing.length} / 4 TRACKS READY`;
  $("listening-help").textContent = !listeningAvailable && data.missing.length ?
    "Restart the updated SoundShredder app to prepare missing tracks in this session." :
    data.status === "failed" || data.status === "cancelled" ? data.message :
    data.missing.some(name => name !== "removed") ?
    "Prepare dialogue, music, and effects from the original audio. This is a separate processing step; your cleaned mix stays unchanged. CPU takes longer." :
    "Dialogue, music, and effects are isolated from your original audio. Listen to each track independently; preview volume does not change your exported mix.";
  $("removed-description").textContent = data.removed_definition;
  for (const name of [...stems, "removed"]) {
    const track = data.tracks[name], player = trackAudio(name), link = $("download-" + name);
    player.hidden = !track.file; link.hidden = !track.file; $("listen-empty-" + name).hidden = !!track.file;
    if (track.file) {
      const url = previewURL(track.file);
      if (player.getAttribute("src") !== url) { player.pause(); player.src = url; }
      link.href = fileURL(track.file);
    } else { player.pause(); player.removeAttribute("src"); player.load(); link.removeAttribute("href"); }
  }
  updateControls(); requestAnimationFrame(redraw);
}
async function refreshListening(id) {
  clearTimeout(listeningTimer);
  if (!id || id !== currentJob || !lastMix) return;
  const revision = lastMix.revision;
  try {
    let data;
    if (listeningAvailable) data = await api(`/api/jobs/${id}/listening`);
    else {
      const tracks = Object.fromEntries(stems.map(name => [name, {file:jobData.report.mode === "bubble" ? null : name + ".wav", waveform:jobData.report.stem_waveforms?.[name]}]));
      tracks.removed = {file:lastMix.removed || null, waveform:lastMix.removed_waveform};
      data = {status:"idle", tracks, missing:Object.keys(tracks).filter(name => !tracks[name].file), removed_definition:jobData.report.mode === "bubble" ? "Estimated bubble sound removed from your original." : "Excluded portions of your separated tracks."};
    }
    if (id !== currentJob || revision !== lastMix?.revision) return;
    showListening(data);
    if (listeningAnchorPending) {
      listeningAnchorPending = false;
      requestAnimationFrame(() => $("listening-panel").scrollIntoView({block:"start"}));
    }
    if (data.status === "running") listeningTimer = setTimeout(() => refreshListening(id), 1200);
  } catch (error) {
    if (id !== currentJob) return;
    $("listening-panel").hidden = false;
    $("listening-help").textContent = `Could not refresh listening tracks: ${error.message}`;
    if (listeningBusy) listeningTimer = setTimeout(() => refreshListening(id), 2500);
  }
}
$("prepare-listening").addEventListener("click", async () => {
  if (!currentJob || busy || !listeningAvailable) return;
  const id = currentJob; clearError(); setBusy(true);
  try {
    const data = await api(`/api/jobs/${id}/listening`, {method:"POST"});
    if (id === currentJob) { setBusy(false); showListening(data); if (data.status === "running") listeningTimer = setTimeout(() => refreshListening(id), 1200); }
  } catch (error) { setBusy(false); showError(error.message); }
});
$("cancel-listening").addEventListener("click", async () => {
  if (!currentJob) return;
  const id = currentJob; $("cancel-listening").disabled = true;
  try { await api(`/api/jobs/${id}/listening/cancel`, {method:"POST"}); if (id === currentJob) await refreshListening(id); }
  catch (error) { showError(error.message); $("cancel-listening").disabled = false; }
});
// A/B switching solos one track. Optional cursor sync never changes exported levels.
$("video-track").addEventListener("change", () => {
  // The monitor already transfers the cursor; preserve subsequent paused seeks.
  activeAudio = $($("video-track").value);
});
document.querySelectorAll("audio").forEach(player => player.addEventListener("play", () => {
  if (activeAudio && activeAudio !== player && $("sync-listening").checked && Number.isFinite(player.duration)) {
    player.currentTime = Math.min(activeAudio.currentTime, Math.max(0, player.duration - 0.01));
  }
  document.querySelectorAll("audio").forEach(other => { if (player !== other) other.pause(); });
  document.querySelectorAll(".listen-track").forEach(row => row.classList.toggle("is-playing", row.contains(player)));
  activeAudio = player;
}));
document.querySelectorAll("audio").forEach(player => {
  for (const event of ["pause", "ended"]) player.addEventListener(event, () => player.closest(".listen-track")?.classList.remove("is-playing"));
});
// Keep one set of controls and its state when the desktop sidebar collapses.
const compactProjectLayout = window.matchMedia("(max-width: 1000px)");
function placeProjectTools() {
  const host = $(compactProjectLayout.matches ? "compact-project" : "sidebar-project");
  host.append($("project-updates"));
}
compactProjectLayout.addEventListener("change", placeProjectTools);
placeProjectTools();
$("check-updates").addEventListener("click", async () => {
  if (!updatesAvailable || $("check-updates").disabled) return;
  const button = $("check-updates"); button.disabled = true; button.setAttribute("aria-busy", "true");
  button.querySelector("span").textContent = "Checking…";
  $("update-result").hidden = false; $("update-result").dataset.state = "checking";
  $("update-status").textContent = "Checking the latest GitHub release…";
  $("update-release").hidden = true; $("update-checked").hidden = true;
  try {
    const result = await api("/api/updates/check", {method:"POST"});
    $("update-status").textContent = result.message;
    $("update-result").dataset.state = result.status;
    const link = $("update-release");
    // Only link to this project's GitHub releases, including when a check fails.
    const destination = new URL(result.release_url);
    link.href = destination.origin === "https://github.com" && /^\/xD4O\/SoundShredder\/releases(?:\/tag\/[v0-9.]+)?$/.test(destination.pathname) ?
      destination.href : "https://github.com/xD4O/SoundShredder/releases";
    link.textContent = result.status === "available" ? `Get v${result.latest_version} ↗` : "View releases ↗";
    const checked = new Date(result.checked_at);
    if (!Number.isNaN(checked.getTime())) {
      $("update-checked").textContent = `${result.status === "unavailable" ? "Attempted" : "Checked"} ${checked.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}${result.cached ? " · recent check" : ""}`;
      $("update-checked").hidden = false;
    }
  } catch {
    $("update-status").textContent = "Couldn't check for updates. Keep the app running and try again, or open Releases.";
    $("update-result").dataset.state = "unavailable";
    $("update-release").href = "https://github.com/xD4O/SoundShredder/releases";
    $("update-release").textContent = "View releases ↗";
  } finally {
    $("update-release").hidden = false; button.disabled = false; button.removeAttribute("aria-busy");
    button.querySelector("span").textContent = "Check for updates";
  }
});
async function boot() {
  try {
    const info = await api("/api/system");
    bubbleAvailable = !!info.features?.bubble_cleanup;
    listeningAvailable = !!info.features?.listening_tracks;
    multipassAvailable = !!info.features?.bubble_multipass;
    rerunAvailable = !!info.features?.rerun_source;
    updatesAvailable = !!info.features?.update_check;
    document.querySelectorAll("[data-app-version]").forEach(el => { el.textContent = info.version ? `v${info.version}` : ""; });
    $("check-updates").disabled = !updatesAvailable;
    if (!updatesAvailable) $("update-help").textContent = "Restart the updated SoundShredder app to enable update checks. Releases are available on GitHub.";
    updateControls();
    if (!bubbleAvailable) document.querySelector("[data-preset=bubble]").title = "Restart SoundShredder to enable the new preset.";
    $("hardware-name").textContent = info.gpu_name || "CPU processing available";
    $("hardware-help").textContent = info.gpu_available ? "GPU detected. Auto will use NVIDIA acceleration." : "Choose CPU or Auto. No compatible NVIDIA GPU detected.";
    $("device").querySelector('[value="cuda"]').disabled = !info.gpu_available;
    await refreshHistory();
    if (info.active_jobs.length) await openSession(info.active_jobs[0]);
    else {
      const session = new URLSearchParams(location.search).get("session");
      if (session && /^[a-f0-9]{32}$/.test(session)) await openSession(session);
    }
  } catch (error) { showError("Could not connect to SoundShredder. Keep the launcher window open and refresh this page."); }
}
updateControls();
boot();
