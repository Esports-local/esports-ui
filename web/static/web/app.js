// 영상 재생(hls.js), 장면 클릭 → currentTime 이동, 대사 검수 단축키
(() => {
  let hls = null;

  function load(video, url) {
    if (!url || video.dataset.loaded === url) return;
    video.dataset.loaded = url;
    if (hls) { hls.destroy(); hls = null; }
    if (window.Hls && Hls.isSupported()) {
      hls = new Hls();
      hls.loadSource(url);
      hls.attachMedia(video);
    } else {
      video.src = url; // Safari 는 HLS 기본 지원
    }
  }

  window.vodLoad = load; // 검수 스튜디오(studio.js)도 같은 로더를 쓴다

  function seekTo(seconds, src) {
    const video = document.getElementById("player");
    if (!video) return;
    if (src) load(video, src);
    const go = () => { video.currentTime = seconds; video.play().catch(() => {}); };
    if (video.readyState >= 1) go(); else video.addEventListener("loadedmetadata", go, { once: true });
  }

  function toast(message) {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    document.body.append(el);
    setTimeout(() => el.remove(), 2500);
  }

  // ---- 검수: 활성 대사 + 집계
  const lines = () => [...document.querySelectorAll(".line")];
  const active = () => document.querySelector(".line.is-active");

  function activate(line, scroll = true) {
    if (!line) return;
    active()?.classList.remove("is-active");
    line.classList.add("is-active");
    if (scroll) line.scrollIntoView({ block: "nearest" });
  }

  function step(delta) {
    const all = lines();
    const i = all.indexOf(active());
    activate(all[Math.min(all.length - 1, Math.max(0, i + delta))]);
  }

  function retally() {
    const all = lines();
    if (!all.length) return;
    const count = (v) => all.filter((l) => l.classList.contains(`is-${v}`)).length;
    for (const v of ["ok", "wrong", "fixed", "pending"]) {
      const el = document.getElementById(`count-${v}`);
      if (el) el.textContent = count(v);
    }
    const reviewed = document.getElementById("count-reviewed");
    if (reviewed) reviewed.textContent = all.length - count("pending");
    document.querySelectorAll(".clip[data-scene]").forEach((clip) => {
      const ls = [...document.querySelectorAll(`#scene-${clip.dataset.scene} .line`)];
      if (!ls.length) return;
      const has = (v) => ls.some((l) => l.classList.contains(`is-${v}`));
      const state = has("wrong") ? "wrong" : has("pending") ? (ls.every((l) => l.classList.contains("is-pending")) ? "pending" : "partial") : "done";
      clip.className = `clip is-${state}`;
    });
  }

  function openEdit(line) {
    const form = line?.querySelector(".line-edit");
    if (!form) return;
    form.hidden = false;
    const input = form.querySelector("input[name=text]");
    input.focus();
    input.select();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const video = document.getElementById("player");
    if (video?.dataset.src) load(video, video.dataset.src);

    // 재생 위치 → 타임라인 막대, 지금 나오는 대사 표시
    video?.addEventListener("timeupdate", () => {
      const t = video.currentTime;
      const head = document.getElementById("playhead");
      if (head && video.duration) head.style.left = `${(t / video.duration) * 100}%`;
      lines().forEach((l) => l.classList.toggle("is-playing", t >= +l.dataset.start && t < +l.dataset.end));
    });
  });

  document.addEventListener("click", (e) => {
    const seek = e.target.closest("[data-seek]");
    if (seek) {
      e.preventDefault();
      seekTo(parseFloat(seek.dataset.seek), seek.dataset.src);
      // 예측 화면: 근거 장면의 지문·대사를 영상 아래에 보여 준다
      if (seek.classList.contains("ev")) {
        document.querySelectorAll(".ev.is-current").forEach((el) => el.classList.remove("is-current"));
        seek.classList.add("is-current");
        const label = document.getElementById("now-label");
        if (label) label.textContent = seek.dataset.src ? `${seek.dataset.label} 재생 중` : `${seek.dataset.label} (이 회차는 영상이 없습니다)`;
        const tpl = document.getElementById(seek.dataset.scene);
        const box = document.getElementById("now-scene");
        if (box) box.replaceChildren(tpl ? tpl.content.cloneNode(true) : "");
      }
      const line = seek.closest(".line");
      if (line) activate(line, false);
      return;
    }
    if (e.target.closest("[data-edit]")) openEdit(e.target.closest(".line"));
    if (e.target.closest("[data-cancel-edit]")) e.target.closest(".line-edit").hidden = true;
    const line = e.target.closest(".line");
    if (line) activate(line, false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea")) {
      if (e.key === "Escape") { e.target.closest(".line-edit")?.setAttribute("hidden", ""); active()?.focus(); }
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey || !document.querySelector(".line")) return;
    const video = document.getElementById("player");
    const line = active();
    const press = (cls) => line?.querySelector(cls)?.click();
    switch (e.key.toLowerCase()) {
      case "j": step(1); break;
      case "k": step(-1); break;
      case "r": if (line) seekTo(+line.dataset.start); break;
      case "1": press(".v-ok"); break;
      case "2": press(".v-wrong"); break;
      case "e": openEdit(line); break;
      case " ": if (video) { video.paused ? video.play() : video.pause(); } break;
      default: return;
    }
    e.preventDefault();
  });

  // 판정 저장 후: 바뀐 줄을 다시 활성화하고, 단축키로 판정했으면 다음 줄로
  // (outerHTML 교체라 target 은 떨어져 나간 옛 줄 — data-start 로 새 줄을 찾는다)
  document.addEventListener("htmx:afterSwap", (e) => {
    retally();
    const swapped = document.querySelector(`.line[data-start="${e.detail.target.dataset?.start}"]`);
    if (swapped) { activate(swapped, false); if (!swapped.classList.contains("is-pending")) step(1); }
  });

  document.addEventListener("htmx:responseError", (e) => toast(e.detail.xhr.responseText || "저장하지 못했습니다"));
  document.addEventListener("htmx:sendError", () => toast("서버에 연결하지 못했습니다"));
})();
