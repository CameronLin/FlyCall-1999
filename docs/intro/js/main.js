
(function () {
  "use strict";
  const root = document.documentElement;
  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(root).getPropertyValue(name).trim();
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } },
  };

  /* ---------------- theme ---------------- */
  const THEMES = ["auto", "light", "dark"];
  const THEME_LABEL = { auto: "◐ 自動", light: "☀ 淺色", dark: "☾ 深色" };
  let theme = store.get("flycall-intro-theme") || "auto";
  const listeners = [];
  function applyTheme() {
    if (theme === "auto") delete root.dataset.theme; else root.dataset.theme = theme;
    const btn = $("theme-btn");
    if (btn) btn.textContent = THEME_LABEL[theme];
    listeners.forEach((fn) => fn());
  }
  if ($("theme-btn")) $("theme-btn").addEventListener("click", () => {
    theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    store.set("flycall-intro-theme", theme);
    applyTheme();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => listeners.forEach((fn) => fn()));

  /* ---------------- tabs ---------------- */
  const panels = Array.from(document.querySelectorAll(".tabpanel"));
  const tabLinks = Array.from(document.querySelectorAll(".tabs a"));
  function activate(id, target) {
    const panel = panels.find((p) => p.id === id) || panels[0];
    panels.forEach((p) => p.classList.toggle("active", p === panel));
    tabLinks.forEach((a) => a.setAttribute("aria-selected", String(a.dataset.tab === panel.id)));
    store.set("flycall-intro-tab", panel.id);
    if (target && target !== panel) target.scrollIntoView({ behavior: "auto", block: "start" });
    else window.scrollTo(0, 0);
    panel.dispatchEvent(new CustomEvent("tabshown"));
  }
  function route() {
    const id = decodeURIComponent(location.hash.slice(1));
    const el = id && document.getElementById(id);
    if (el) {
      const panel = el.classList.contains("tabpanel") ? el : el.closest(".tabpanel");
      if (panel) { activate(panel.id, el); return; }
    }
    activate(store.get("flycall-intro-tab") || panels[0].id);
  }
  window.addEventListener("hashchange", route);

  /* ---------------- BFS animation ---------------- */
  const BFS = JSON.parse($("bfs-data").textContent);
  const cv = $("bfs-canvas");
  const ctx = cv.getContext("2d");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let graph = "G0", glu = "inh", showAll = false, start = 0, playing = false, raf = 0, W = 900, H = 560;
  let schedule = null;

  function buildSchedule() {
    const g = BFS[graph];
    const times = new Array(g.nodes.length);
    const layerStart = {}, layerEnd = {};
    let t = 0.4;
    const maxL = Math.max(...g.nodes.map((n) => n[2]));
    for (let L = 0; L <= maxL; L++) {
      const idx = g.nodes.map((n, i) => (n[2] === L ? i : -1)).filter((i) => i >= 0);
      const dur = L === 0 ? 0.2 : Math.min(4.5, Math.max(1.6, idx.length * 0.012));
      layerStart[L] = t;
      idx.forEach((i, j) => { times[i] = t + (dur * j) / Math.max(1, idx.length); });
      t += dur;
      layerEnd[L] = t;
      t += 0.7;
    }
    const rng = mulberry(7);
    const ghosts = [];
    const g1 = (g.ghosts && g.ghosts["1"]) || 0;
    for (let k = 0; k < g1; k++) {
      const a = rng() * Math.PI * 2, r = 0.22 + rng() * 0.16;
      ghosts.push({ x: 0.5 + 0.47 * r * Math.cos(a), y: 0.5 + 0.47 * r * Math.sin(a), t: layerStart[1] + rng() * (layerEnd[1] - layerStart[1]) });
    }
    schedule = { times, layerStart, layerEnd, total: t, ghosts, maxL };
  }
  function mulberry(a) { return function () { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

  function resize() {
    const w = cv.clientWidth || 900;
    const h = Math.round(Math.min(620, Math.max(340, w * 0.62)));
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    W = w; H = h;
  }
  function px(n) { const s = Math.min(W, H); return [W / 2 + (n[0] - 0.5) * s, H / 2 + (n[1] - 0.5) * s]; }
  function nodeSign(n) { if (graph === "G0") return 0; if (glu === "exc" && n[5]) return 1; return n[4]; }
  function colorOf(n) { const s = nodeSign(n); return s > 0 ? css("--exc") : s < 0 ? css("--inh") : css("--neutral"); }

  function draw(now) {
    const g = BFS[graph];
    const t = playing ? (now - start) / 1000 : schedule.total + 1;
    const done = t >= schedule.total;
    ctx.clearRect(0, 0, W, H);
    const s = Math.min(W, H);
    // layer guide rings
    ctx.strokeStyle = css("--rule"); ctx.lineWidth = 1; ctx.setLineDash([3, 5]);
    [0.30, 0.75].forEach((r, i) => {
      if (i + 1 > schedule.maxL) return;
      ctx.beginPath(); ctx.arc(W / 2, H / 2, s * 0.47 * r, 0, Math.PI * 2); ctx.stroke();
    });
    ctx.setLineDash([]);
    // all edges (faint)
    if (showAll || done) {
      ctx.strokeStyle = css("--ink-3"); ctx.globalAlpha = showAll ? 0.10 : 0.05; ctx.lineWidth = 0.6;
      ctx.beginPath();
      for (const [a, b] of g.edges) {
        if (schedule.times[a] > t || schedule.times[b] > t) continue;
        const [x1, y1] = px(g.nodes[a]), [x2, y2] = px(g.nodes[b]);
        ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
      }
      ctx.stroke(); ctx.globalAlpha = 1;
    }
    // ghosts (skipped unsigned candidates, layer 1)
    for (const gh of schedule.ghosts) {
      const age = t - gh.t;
      if (age < 0 || age > 0.9) continue;
      ctx.globalAlpha = 0.55 * (1 - age / 0.9);
      ctx.fillStyle = css("--ink-3");
      ctx.beginPath(); ctx.arc(W / 2 + (gh.x - 0.5) * s, H / 2 + (gh.y - 0.5) * s, 1.8, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    // tree edges
    ctx.lineWidth = 0.9;
    g.nodes.forEach((n, i) => {
      if (n[3] < 0 || schedule.times[i] > t) return;
      const [x1, y1] = px(g.nodes[n[3]]), [x2, y2] = px(n);
      ctx.strokeStyle = colorOf(n); ctx.globalAlpha = 0.28;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    });
    ctx.globalAlpha = 1;
    // nodes
    let counts = { exc: 0, inh: 0, n: 0, layer: 0 };
    g.nodes.forEach((n, i) => {
      const ti = schedule.times[i];
      if (ti > t) return;
      counts.n++; counts.layer = Math.max(counts.layer, n[2]);
      const sg = nodeSign(n); if (sg > 0) counts.exc++; else if (sg < 0) counts.inh++;
      const [x, y] = px(n);
      const r = n[2] === 0 ? 7 : n[2] === 1 ? (graph === "G0" ? 6 : 3.4) : 2.6;
      ctx.fillStyle = colorOf(n);
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      if (graph === "SIGNED" && n[5]) { ctx.strokeStyle = css("--glu"); ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(x, y, r + 2, 0, Math.PI * 2); ctx.stroke(); }
      if (done && n[6]) {
        ctx.strokeStyle = css("--ink"); ctx.lineWidth = 1.2;
        if (n[6] === 1) { ctx.strokeRect(x - r - 2, y - r - 2, 2 * r + 4, 2 * r + 4); }
        else { ctx.beginPath(); ctx.moveTo(x, y - r - 3); ctx.lineTo(x + r + 3, y); ctx.lineTo(x, y + r + 3); ctx.lineTo(x - r - 3, y); ctx.closePath(); ctx.stroke(); }
      }
      const age = t - ti;
      if (playing && age < 0.6) { ctx.strokeStyle = colorOf(n); ctx.globalAlpha = 1 - age / 0.6; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, r + 3 + age * 14, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1; }
    });
    // seed label
    const seedN = g.nodes[0]; const [sx, sy] = px(seedN);
    ctx.fillStyle = css("--ink"); ctx.font = "600 12px " + css("--f");
    ctx.textAlign = "center"; ctx.fillText("起點 " + g.seed, sx, sy - 12);
    // HUD
    let skipped = 0;
    if (graph === "SIGNED") {
      skipped = schedule.ghosts.filter((gh) => gh.t <= t).length;
      const L2 = schedule.layerStart[2], E2 = schedule.layerEnd[2];
      if (t > L2) skipped += Math.round(g.ghosts["2"] * Math.min(1, (t - L2) / (E2 - L2)));
    }
    const layerName = counts.n ? "第 " + counts.layer + " 層" : "準備中";
    let hud = `<div>${layerName}｜已收 <b>${counts.n}</b>／500 點</div>`;
    if (graph === "SIGNED") {
      hud += `<div><span class="sg exc">增強 <b>${counts.exc}</b>${glu === "inh" ? "／300" : ""}</span>　<span class="sg inh">抑制 <b>${counts.inh}</b>${glu === "inh" ? "／200" : ""}</span></div>`;
      hud += `<div>跳過（沒有正負號）<b>${skipped.toLocaleString()}</b></div>`;
      if (glu === "exc" && done) hud += `<div>麩胺酸改當增強：56 點換邊（G2-glu+）</div>`;
    } else {
      hud += `<div>沒有正負號資訊（模型裡全部當增強）</div>`;
    }
    if (done) hud += `<div>${g.edges.length.toLocaleString()} 條有向邊${showAll ? "" : "（淡線）"}</div>`;
    $("bfs-hud").innerHTML = hud;
    if (playing && !done) raf = requestAnimationFrame(draw);
    else if (playing && done) { playing = false; $("bfs-play").textContent = "↻ 重播"; draw(); }
  }
  function legend() {
    const items = graph === "G0"
      ? [["var(--neutral)", "G0 的點（沒有正負號）"], ["", "□ 輸入點　◇ 輸出點（播放結束後顯示）"]]
      : [["var(--exc)", "增強（乙醯膽鹼" + (glu === "exc" ? "、麩胺酸" : "") + "）"], ["var(--inh)", "抑制（GABA" + (glu === "inh" ? "、麩胺酸" : "") + "）"],
         ["var(--glu)", "紫色外框：56 個麩胺酸點"], ["var(--ink-3)", "一閃即逝的灰點：被跳過的無符號點（示意）"], ["", "□ 輸入點　◇ 輸出點"]];
    $("bfs-legend").innerHTML = items.map(([c, t]) => c ? `<span style="--c:${c}">${t}</span>` : `<em>${t}</em>`).join("");
  }
  function play(auto) {
    cancelAnimationFrame(raf);
    buildSchedule();
    if (reduce && auto) { playing = false; draw(); return; }  // reduced motion: no autoplay, but a click still plays
    playing = true; start = performance.now();
    $("bfs-play").textContent = "⏸ 播放中";
    raf = requestAnimationFrame(draw);
  }
  function redraw() { resize(); if (!playing) draw(); }
  document.querySelectorAll(".bfs-tools [data-g]").forEach((b) => b.addEventListener("click", () => {
    graph = b.dataset.g;
    document.querySelectorAll(".bfs-tools [data-g]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    document.querySelector(".glu-seg").hidden = graph !== "SIGNED";
    legend(); play();
  }));
  document.querySelectorAll(".glu-seg [data-glu]").forEach((b) => b.addEventListener("click", () => {
    glu = b.dataset.glu;
    document.querySelectorAll(".glu-seg [data-glu]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    legend(); if (!playing) draw();
  }));
  $("bfs-play").addEventListener("click", () => { if (!playing) play(); });
  $("bfs-alledges").addEventListener("change", (e) => { showAll = e.target.checked; if (!playing) draw(); });
  window.addEventListener("resize", redraw);
  listeners.push(() => { if (!playing) draw(); });
  buildSchedule(); legend();
  let autoplayed = false;
  const flyPanel = $("tab-fly");
  function maybeAutoplay() {
    if (autoplayed || !flyPanel.classList.contains("active")) return;
    resize();
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && !autoplayed) { autoplayed = true; play(true); io.disconnect(); }
    }, { threshold: 0.35 });
    io.observe(cv);
  }
  flyPanel.addEventListener("tabshown", () => { resize(); if (!playing) draw(); maybeAutoplay(); loadSignal(); });

  /* ---------------- embedded signal page ---------------- */
  let signalLoaded = false;
  function loadSignal() {
    if (signalLoaded) return;
    signalLoaded = true;
    const frame = $("signal-frame");
    try {
      const b64 = JSON.parse($("signal-data").textContent);
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      frame.srcdoc = new TextDecoder("utf-8").decode(bytes);
    } catch (e) { return; }
    frame.addEventListener("load", () => {
      syncFrame();
      try {
        const doc = frame.contentDocument;
        const fit = () => { frame.style.height = Math.max(600, doc.documentElement.scrollHeight + 4) + "px"; };
        fit();
        new ResizeObserver(fit).observe(doc.body);
      } catch (e) { /* cross-origin: keep the CSS height */ }
    });
  }
  function syncFrame() {
    try {
      const d = $("signal-frame").contentDocument.documentElement;
      const dark = theme === "dark" || (theme === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
      d.dataset.theme = dark ? "dark" : "light";
    } catch (e) { /* not reachable */ }
  }
  listeners.push(syncFrame);

  /* ---------------- figure gallery ---------------- */
  const FIG = JSON.parse($("fig-data").textContent);
  const cards = Array.from(document.querySelectorAll("#figs .fig"));
  const filters = { graph: "all", objective: "all", kind: "all" };
  // data version × T shown in 3.2 and 3.3 (cards and table panes carry data-set="v1-t4" etc.)
  const abState = { data: "v1", t: "t4" };
  let abSet = "v1-t4";
  let abTabShown = false;
  function loadImages() {
    abTabShown = true;
    cards.forEach((c) => {
      if (c.dataset.set !== abSet) return;
      const img = c.querySelector("img");
      if (!img.src && FIG[img.dataset.fig]) img.src = FIG[img.dataset.fig];
    });
  }
  function applyFilters() {
    cards.forEach((c) => {
      if (c.dataset.set !== abSet) { c.hidden = true; return; }
      const okG = filters.graph === "all" || c.dataset.graph === filters.graph;
      const okO = filters.objective === "all" || c.dataset.objective === filters.objective;
      const okK = filters.kind === "all" || c.dataset.kind === filters.kind;
      c.hidden = !(okG && okO && okK);
    });
  }
  document.querySelectorAll(".fig-filters .seg").forEach((seg) => seg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    filters[seg.dataset.filter] = b.dataset.v;
    seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    applyFilters();
  }));
  document.querySelectorAll(".ab-ver .seg").forEach((seg) => seg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    abState[seg.dataset.abver] = b.dataset.v;
    seg.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    abSet = `${abState.data}-${abState.t}`;
    const label = `資料 ${abState.data}・T=${abState.t.slice(1)}`;
    document.querySelectorAll(".ab-pane").forEach((p) => { p.hidden = p.dataset.set !== abSet; });
    document.querySelectorAll(".ab-cur").forEach((x) => { x.textContent = label; });
    document.querySelectorAll(".ab-ver-now").forEach((x) => { x.textContent = `目前：${label}`; });
    applyFilters();
    if (abTabShown) loadImages();
  }));
  $("tab-ab").addEventListener("tabshown", loadImages);
  // lightbox
  const lb = document.createElement("div");
  lb.className = "lightbox"; lb.setAttribute("role", "dialog"); lb.setAttribute("aria-modal", "true"); lb.setAttribute("aria-label", "放大檢視");
  lb.innerHTML = '<button type="button" class="lb-close" aria-label="關閉">✕</button><button type="button" class="lb-btn lb-prev" aria-label="上一張">‹</button><figure><img alt=""><figcaption></figcaption></figure><button type="button" class="lb-btn lb-next" aria-label="下一張">›</button>';
  document.body.appendChild(lb);
  let lbIndex = -1, lbList = [];
  function openLb(card) { lbList = cards.filter((c) => !c.hidden); lbIndex = lbList.indexOf(card); showLb(); lb.classList.add("open"); lb.querySelector(".lb-close").focus(); }
  function showLb() {
    const c = lbList[lbIndex]; const img = c.querySelector("img");
    lb.querySelector("img").src = img.src; lb.querySelector("img").alt = img.alt;
    lb.querySelector("figcaption").textContent = img.alt + `（${lbIndex + 1}／${lbList.length}）`;
  }
  function closeLb() { lb.classList.remove("open"); const c = lbList[lbIndex]; if (c) c.querySelector(".thumb").focus(); }
  cards.forEach((c) => c.querySelector(".thumb").addEventListener("click", () => openLb(c)));
  lb.querySelector(".lb-close").addEventListener("click", closeLb);
  lb.querySelector(".lb-prev").addEventListener("click", () => { lbIndex = (lbIndex - 1 + lbList.length) % lbList.length; showLb(); });
  lb.querySelector(".lb-next").addEventListener("click", () => { lbIndex = (lbIndex + 1) % lbList.length; showLb(); });
  lb.addEventListener("click", (e) => { if (e.target === lb) closeLb(); });
  document.addEventListener("keydown", (e) => {
    if (!lb.classList.contains("open")) return;
    if (e.key === "Escape") closeLb();
    if (e.key === "ArrowLeft") lb.querySelector(".lb-prev").click();
    if (e.key === "ArrowRight") lb.querySelector(".lb-next").click();
  });

  /* ---------------- start ---------------- */
  applyTheme();
  route();
})();

