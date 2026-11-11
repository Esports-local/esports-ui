// 회차 검수 스튜디오: 장면 목록 · 영상 · 인스펙터 + 타임라인(장면 트랙, 선택 장면의 대사 레인)
(() => {
  const D = JSON.parse(document.getElementById("studio-data").textContent);
  const scenes = D.scenes;
  const dur = D.episode.duration || Math.max(1, ...scenes.map((s) => s.end));
  const $ = (id) => document.getElementById(id);
  const video = $("player");
  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";

  const LABEL = { ok: "맞음", wrong: "틀림", fixed: "수정", pending: "대기" };
  const RATES = [0.5, 1, 1.5, 2];
  const st = {
    scene: scenes[0]?.id ?? null, line: scenes[0]?.lines.length ? 0 : null,
    status: "all", type: "all", q: "", editing: false, stopAt: null,
  };

  // ---- 유틸
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pad = (n) => String(n).padStart(2, "0");
  function fmt(t, frac = false) {
    t = Math.max(0, t || 0);
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = Math.floor(t % 60);
    const base = (h ? `${h}:${pad(m)}` : pad(m)) + `:${pad(s)}`;
    return frac ? `${base}.${Math.floor((t % 1) * 10)}` : base;
  }
  const secs = (a, b) => `${Math.max(0, b - a).toFixed(1).replace(/\.0$/, "")}s`;
  const verdictOf = (l) => l.review?.verdict || "pending";
  const textOf = (l) => (l.review?.verdict === "fixed" ? l.review.text : l.text);
  const speakerOf = (l) => l.speaker || "화자 미상";
  const sceneOf = (id) => scenes.find((s) => s.id === id);
  const curScene = () => sceneOf(st.scene);
  const curLine = () => (st.line == null ? null : curScene()?.lines[st.line] ?? null);
  function sceneState(s) {
    if (!s.lines.length) return "empty";
    const v = s.lines.map(verdictOf);
    if (v.includes("wrong")) return "wrong";
    if (v.every((x) => x === "pending")) return "pending";
    return v.includes("pending") ? "partial" : "done";
  }
  function toast(msg) {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    document.body.append(el);
    setTimeout(() => el.remove(), 2500);
  }

  // ---- 필터
  function passes(s) {
    if (st.type !== "all" && s.type !== st.type) return false;
    if (st.status !== "all" && !s.lines.some((l) => verdictOf(l) === st.status)) return false;
    if (st.q) {
      const q = st.q.toLowerCase();
      const hay = [s.summary, ...s.keywords, ...s.lines.map(textOf)].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  // ---- 렌더
  function renderTally() {
    const all = scenes.flatMap((s) => s.lines);
    const n = (v) => all.filter((l) => verdictOf(l) === v).length;
    $("tally").textContent = `대기 ${n("pending")} · 맞음 ${n("ok")} · 수정 ${n("fixed")} · 틀림 ${n("wrong")}`;
    $("browser-count").textContent = `${all.length - n("pending")}/${all.length}줄`;
    return n;
  }

  function renderFilters(n) {
    const statuses = [["all", "전체"], ["pending", "대기"], ["wrong", "틀림"], ["fixed", "수정"], ["ok", "맞음"]];
    $("status-filter").innerHTML = statuses.map(([v, label]) =>
      `<button type="button" data-status="${v}" aria-pressed="${st.status === v}">${label}${v === "all" ? "" : ` <small>${n(v)}</small>`}</button>`).join("");
    const types = {};
    scenes.forEach((s) => { types[s.type] = types[s.type] || { label: s.type_label, count: 0 }; types[s.type].count++; });
    $("type-filter").innerHTML = Object.entries(types).map(([t, { label, count }]) =>
      `<button type="button" data-type="${t}" aria-pressed="${st.type === t}">${esc(label)} <small>${count}</small></button>`).join("");
  }

  function renderBrowser() {
    const items = scenes.filter(passes);
    $("scene-list").innerHTML = items.map((s) => {
      const done = s.lines.filter((l) => verdictOf(l) !== "pending").length;
      return `<li><button type="button" class="scene-item${s.id === st.scene ? " is-sel" : ""}" data-scene="${s.id}">
        <span class="dot is-${sceneState(s)}"></span><span class="mono dim">#${s.id}</span>
        <span class="si-body"><span class="si-title">${esc(s.summary)}</span>
        <span class="si-sub">${fmt(s.start)} · ${secs(s.start, s.end)} · ${esc(s.type_label)} · ${s.lines.length ? `검수 ${done}/${s.lines.length}` : "대사 없음"}</span></span>
      </button></li>`;
    }).join("") || `<li class="dim empty">조건에 맞는 장면이 없습니다.</li>`;
    $("scene-list").querySelector(".is-sel")?.scrollIntoView({ block: "nearest" });
  }

  function renderRuler() {
    const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800];
    const step = steps.find((s) => dur / s <= 12) || 3600;
    let html = "";
    for (let t = 0; t <= dur; t += step) html += `<span style="left:${(t / dur) * 100}%">${fmt(t)}</span>`;
    $("ruler").innerHTML = html;
  }

  function renderSceneTrack() {
    const track = $("scene-track");
    track.querySelectorAll(".clip2").forEach((el) => el.remove());
    scenes.forEach((s) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = `clip2 is-${sceneState(s)}${s.id === st.scene ? " is-sel" : ""}${passes(s) ? "" : " is-dim"}`;
      el.style.left = `${(s.start / dur) * 100}%`;
      el.style.width = `${((s.end - s.start) / dur) * 100}%`;
      el.dataset.scene = s.id;
      el.title = `S#${s.id} ${fmt(s.start)} – ${fmt(s.end)} · ${s.type_label}`;
      el.textContent = `#${s.id}`;
      track.append(el);
    });
    const s = curScene();
    if (s) {
      const x1 = (s.start / dur) * 100, x2 = (s.end / dur) * 100;
      $("zoom-path").setAttribute("d", `M${x1} 0 L0 10 M${x2} 0 L100 10`);
    }
  }

  function renderLane() {
    const s = curScene();
    const lane = $("line-lane");
    lane.querySelectorAll(".ln, .lane-empty").forEach((el) => el.remove());
    if (!s) return;
    $("lane-info").innerHTML = `<span class="dot is-${sceneState(s)}"></span><b>#${s.id}</b> 장면 내부 ${fmt(s.start)} – ${fmt(s.end)} · ${secs(s.start, s.end)} · ${esc(s.type_label)}${s.black_before ? " · 암전 후" : ""}<span class="dim right">대사 ${s.lines.length}줄</span>`;
    const span = Math.max(0.001, s.end - s.start);
    if (!s.lines.length) {
      lane.insertAdjacentHTML("beforeend", `<div class="lane-empty">대사 없는 장면 — 지문: ${esc(s.summary)}</div>`);
      return;
    }
    s.lines.forEach((l, i) => {
      const el = document.createElement("button");
      el.type = "button";
      el.className = `ln is-${verdictOf(l)}${i === st.line ? " is-sel" : ""}`;
      el.style.left = `${((l.start - s.start) / span) * 100}%`;
      el.style.width = `${((l.end - l.start) / span) * 100}%`;
      el.dataset.line = i;
      el.title = `${speakerOf(l)} ${fmt(l.start)} · ${textOf(l)}`;
      el.innerHTML = `<b>${esc(speakerOf(l))}</b><span>${esc(textOf(l))}</span><small>${secs(l.start, l.end)} · ${LABEL[verdictOf(l)]}</small>`;
      lane.append(el);
    });
  }

  function renderInspector() {
    const s = curScene(), l = curLine(), box = $("inspector");
    if (!s) { box.innerHTML = ""; return; }
    const v = l ? verdictOf(l) : null;
    box.innerHTML = `
      <div class="pane-head"><span>인스펙터 — ${l ? `S#${s.id} 대사 ${st.line + 1}` : `S#${s.id}`}</span></div>
      <dl class="props">
        <div><dt>장면</dt><dd>S#${s.id} · ${esc(s.type_label)}</dd></div>
        ${l ? `<div><dt>화자</dt><dd>${esc(speakerOf(l))}</dd></div>
        <div><dt>구간</dt><dd class="mono">${fmt(l.start, true)} – ${fmt(l.end, true)}</dd></div>
        <div><dt>상태</dt><dd><span class="pill is-${v}">${LABEL[v]}</span></dd></div>` : `<div><dt>구간</dt><dd class="mono">${fmt(s.start)} – ${fmt(s.end)}</dd></div>`}
      </dl>
      ${l ? `<div class="quote">
        <p class="quote-text">${esc(textOf(l))}</p>
        ${v === "fixed" ? `<p class="quote-orig">원문 <s>${esc(l.text)}</s></p>` : ""}
        ${st.editing ? `<form class="fix-form" id="fix-form">
          <textarea id="fix-text" rows="3" aria-label="고친 대사">${esc(textOf(l))}</textarea>
          <div class="fix-btns"><button type="submit" class="vb vb-fix"><kbd>Enter</kbd>저장</button><button type="button" class="vb" data-act="cancel"><kbd>Esc</kbd>취소</button></div>
        </form>` : ""}
      </div>` : ""}
      <div class="scene-note">
        <p class="sn-label">지문</p><p>${esc(s.summary)}</p>
        ${s.keywords.length ? `<p class="sn-label">키워드</p><p class="dim">${s.keywords.map(esc).join(", ")}</p>` : ""}
        ${s.faces.length ? `<p class="sn-label">얼굴</p><p class="dim">${s.faces.map(esc).join(", ")}</p>` : ""}
      </div>`;
    if (st.editing) {
      const ta = $("fix-text");
      ta.focus();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    }
    const s2 = curScene();
    $("video-label").textContent = l ? `S#${s2.id} · 대사 ${st.line + 1}/${s2.lines.length} · ${speakerOf(l)}` : `S#${s2.id} · ${s2.type_label}`;
    document.querySelectorAll("#verdict-bar button").forEach((b) => {
      b.disabled = !l;
      b.setAttribute("aria-pressed", String(!!l && (b.dataset.verdict === v || (b.dataset.act === "edit" && v === "fixed"))));
    });
  }

  function renderAll() {
    const n = renderTally();
    renderFilters(n);
    renderBrowser();
    renderSceneTrack();
    renderLane();
    renderInspector();
    $("tl-info").textContent = `회차 ${fmt(dur)} · 장면 ${scenes.length}개`;
  }

  // ---- 재생
  function seek(t, play = false) {
    if (!video) return;
    const go = () => { video.currentTime = t; if (play) video.play().catch(() => {}); };
    if (video.readyState >= 1) go(); else video.addEventListener("loadedmetadata", go, { once: true });
  }
  function playLine() {
    const l = curLine();
    if (!l) return;
    st.stopAt = l.end;
    seek(l.start, true);
  }
  function tick() {
    if (!video) return;
    const t = video.currentTime;
    $("tc").textContent = fmt(t, true);
    $("ph-scenes").style.left = `${(t / dur) * 100}%`;
    const s = curScene(), ph = $("ph-lines");
    if (s && t >= s.start && t <= s.end) {
      ph.hidden = false;
      ph.style.left = `${((t - s.start) / Math.max(0.001, s.end - s.start)) * 100}%`;
    } else ph.hidden = true;
    document.querySelectorAll(".ln").forEach((el) => {
      const l = s?.lines[+el.dataset.line];
      el.classList.toggle("is-playing", !!l && t >= l.start && t < l.end);
    });
    if (st.stopAt != null && t >= st.stopAt) { video.pause(); st.stopAt = null; }
    $("play-btn").textContent = video.paused ? "▶" : "❚❚";
    if (!video.paused) requestAnimationFrame(tick);
  }

  // ---- 선택
  function select(sceneId, lineIdx, { doSeek = true } = {}) {
    const s = sceneOf(sceneId);
    if (!s) return;
    st.scene = sceneId;
    st.line = lineIdx ?? (s.lines.length ? 0 : null);
    st.editing = false;
    renderAll();
    if (doSeek) seek(st.line != null ? s.lines[st.line].start : s.start);
    tick();
  }
  function stepLine(delta) {
    const flat = scenes.filter(passes).flatMap((s) => (s.lines.length ? s.lines.map((_, i) => [s.id, i]) : [[s.id, null]]));
    const i = flat.findIndex(([sid, li]) => sid === st.scene && li === st.line);
    const next = flat[Math.min(flat.length - 1, Math.max(0, i + delta))];
    if (next) select(next[0], next[1]);
  }
  function stepScene(delta) {
    const list = scenes.filter(passes);
    const i = list.findIndex((s) => s.id === st.scene);
    const next = list[Math.min(list.length - 1, Math.max(0, i + delta))];
    if (next) select(next.id, null);
  }

  // ---- 판정 저장
  async function judge(verdict, text = "") {
    const s = curScene(), l = curLine();
    if (!l) return;
    const body = new URLSearchParams({ verdict, text });
    try {
      const resp = await fetch(`${D.review_url}${s.id}/${st.line}/`, {
        method: "POST", body, headers: { "X-CSRFToken": csrf },
      });
      const data = await resp.json();
      if (!resp.ok) { toast(data.error || "저장하지 못했습니다"); return; }
      l.review = data.review;
      st.editing = false;
      if (verdict === "clear") renderAll(); else stepLine(1);
    } catch {
      toast("서버에 연결하지 못했습니다");
    }
  }
  function startEdit() {
    if (!curLine()) return;
    st.editing = true;
    renderInspector();
  }

  // ---- 이벤트
  document.addEventListener("click", (e) => {
    const t = e.target;
    const scene = t.closest("[data-scene]");
    if (scene) return select(+scene.dataset.scene, null);
    const ln = t.closest(".ln");
    if (ln) return select(st.scene, +ln.dataset.line);
    const status = t.closest("[data-status]");
    if (status) { st.status = status.dataset.status; return renderAll(); }
    const type = t.closest("[data-type]");
    if (type) { st.type = st.type === type.dataset.type ? "all" : type.dataset.type; return renderAll(); }
    const v = t.closest("[data-verdict]");
    if (v) return judge(v.dataset.verdict);
    const act = t.closest("[data-act]")?.dataset.act;
    if (act) return action(act);
    if (t.closest("#ruler, #scene-track") && video) {
      const r = $("scene-track").getBoundingClientRect();
      seek(((e.clientX - r.left) / r.width) * dur);
    }
  });

  document.addEventListener("submit", (e) => {
    if (e.target.id !== "fix-form") return;
    e.preventDefault();
    judge("fixed", $("fix-text").value.trim());
  });

  $("search").addEventListener("input", (e) => { st.q = e.target.value.trim(); renderAll(); });

  function action(act) {
    if (act === "edit") return startEdit();
    if (act === "cancel") { st.editing = false; return renderInspector(); }
    if (!video) return;
    if (act === "play") { st.stopAt = null; video.paused ? video.play() : video.pause(); }
    if (act === "back") seek(video.currentTime - 2);
    if (act === "fwd") seek(video.currentTime + 2);
    if (act === "line") playLine();
    const i = RATES.indexOf(video.playbackRate);
    if (act === "rate") video.playbackRate = RATES[(i + 1) % RATES.length];
    if (act === "slower") video.playbackRate = RATES[Math.max(0, i - 1)];
    if (act === "faster") video.playbackRate = RATES[Math.min(RATES.length - 1, i + 1)];
    $("rate-btn").textContent = `${video.playbackRate}×`;
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.id === "fix-text") {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); judge("fixed", e.target.value.trim()); }
      if (e.key === "Escape") { st.editing = false; renderInspector(); }
      return;
    }
    if (e.target.matches("input, textarea, select")) {
      if (e.key === "Escape") e.target.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const keys = {
      "1": () => judge("ok"), "2": () => judge("wrong"), "4": startEdit, e: startEdit,
      Backspace: () => judge("clear"), Delete: () => judge("clear"),
      ArrowDown: () => stepLine(1), ArrowUp: () => stepLine(-1), j: () => stepLine(1), k: () => stepLine(-1),
      "]": () => stepScene(1), "[": () => stepScene(-1),
      r: playLine, ArrowLeft: () => action("back"), ArrowRight: () => action("fwd"),
      " ": () => action("play"), s: () => action("rate"), "/": () => $("search").focus(),
    };
    const fn = keys[e.key.length === 1 ? e.key.toLowerCase() : e.key];
    if (fn) { e.preventDefault(); fn(); }
  });

  if (video) {
    window.vodLoad?.(video, D.episode.play_url);
    video.addEventListener("click", () => action("play"));
    ["play", "pause", "seeked", "timeupdate", "loadedmetadata"].forEach((ev) => video.addEventListener(ev, tick));
  }
  renderRuler();
  renderAll();
  tick();
})();
