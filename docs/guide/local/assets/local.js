// ローカル実行ガイドの共通スクリプト（利用ガイドの guide.js をもとにしている）：ナビゲーション、言語切り替え、テーマ切り替え、Mermaid、
// 端末の再生アニメーション、手順のアニメーション。
// ページは ja/・en/・zh/ に置き、<html lang> で表示言語を決め、<body data-page="ファイル名"> で自身を示す。
// モジュールではない通常のスクリプト（file:// で直接開いても動く）。Mermaid は CDN から読み込む（要ネット接続）。

const LANGS = [
  { code: "ja", label: "日本語" },
  { code: "en", label: "English" },
  { code: "zh", label: "中文" },
];

const UI = {
  ja: {
    brand: "EchoLab ローカル実行ガイド", theme: "ライト／ダーク", lang: "言語",
    play: "▶ 再生", replay: "もう一度", prev: "◀ 前へ", next: "次へ ▶", auto: "▶ 自動再生", pause: "一時停止",
  },
  en: {
    brand: "EchoLab Local Run Guide", theme: "Light / Dark", lang: "Language",
    play: "▶ Play", replay: "Replay", prev: "◀ Back", next: "Next ▶", auto: "▶ Auto-play", pause: "Pause",
  },
  zh: {
    brand: "EchoLab 本地运行指南", theme: "切换明暗", lang: "语言",
    play: "▶ 播放", replay: "重播", prev: "◀ 上一步", next: "下一步 ▶", auto: "▶ 自动播放", pause: "暂停",
  },
};

const GROUPS = {
  start: { ja: "はじめに", en: "Getting started", zh: "开始" },
  run: { ja: "<ruby class=\"furi\">動<rp>(</rp><rt>うご</rt><rp>)</rp></ruby>かす", en: "Run", zh: "运行" },
  more: { ja: "<ruby class=\"furi\">確<rp>(</rp><rt>たし</rt><rp>)</rp></ruby>かめる・<ruby class=\"furi\">困<rp>(</rp><rt>こま</rt><rp>)</rp></ruby>ったとき", en: "Verify & troubleshoot", zh: "验证与排错" },
};

const PAGES = [
  { file: "index.html", group: "start", ja: "<ruby class=\"furi eng\">トップ<rp>(</rp><rt lang=\"en\">top</rt><rp>)</rp></ruby>・<ruby class=\"furi\">動<rp>(</rp><rt>うご</rt><rp>)</rp></ruby>かし<ruby class=\"furi\">方<rp>(</rp><rt>かた</rt><rp>)</rp></ruby>を<ruby class=\"furi\">選<rp>(</rp><rt>えら</rt><rp>)</rp></ruby>ぶ", en: "Home: choose how to run", zh: "首页・选择运行方式" },
  { file: "01-prerequisites.html", group: "start", ja: "<ruby class=\"furi\">必<rp>(</rp><rt>ひつ</rt><rp>)</rp></ruby><ruby class=\"furi\">要<rp>(</rp><rt>よう</rt><rp>)</rp></ruby>なもの", en: "Prerequisites", zh: "准备环境" },
  { file: "01b-windows-wsl.html", group: "start", ja: "Windows で WSL を<ruby class=\"furi\">準<rp>(</rp><rt>じゅん</rt><rp>)</rp></ruby><ruby class=\"furi\">備<rp>(</rp><rt>び</rt><rp>)</rp></ruby>する", en: "Set up WSL on Windows", zh: "在 Windows 上安装设置 WSL" },
  { file: "02-setup.html", group: "start", ja: "<ruby class=\"furi eng\">セットアップ<rp>(</rp><rt lang=\"en\">setup</rt><rp>)</rp></ruby>", en: "Setup", zh: "安装与设置" },
  { file: "03-scripted.html", group: "run", ja: "<ruby class=\"furi\">台<rp>(</rp><rt>だい</rt><rp>)</rp></ruby><ruby class=\"furi\">本<rp>(</rp><rt>ほん</rt><rp>)</rp></ruby><ruby class=\"furi eng\">モード<rp>(</rp><rt lang=\"en\">mode</rt><rp>)</rp></ruby>で<ruby class=\"furi\">動<rp>(</rp><rt>うご</rt><rp>)</rp></ruby>かす（API <ruby class=\"furi eng\">キー<rp>(</rp><rt lang=\"en\">key</rt><rp>)</rp></ruby><ruby class=\"furi\">不<rp>(</rp><rt>ふ</rt><rp>)</rp></ruby><ruby class=\"furi\">要<rp>(</rp><rt>よう</rt><rp>)</rp></ruby>）", en: "Run in scripted mode (no API key)", zh: "用脚本模式运行（无需 API 密钥）" },
  { file: "04-java-service.html", group: "run", ja: "Java の<ruby class=\"furi\">計<rp>(</rp><rt>けい</rt><rp>)</rp></ruby><ruby class=\"furi\">算<rp>(</rp><rt>さん</rt><rp>)</rp></ruby><ruby class=\"furi eng\">サービス<rp>(</rp><rt lang=\"en\">service</rt><rp>)</rp></ruby>で<ruby class=\"furi\">動<rp>(</rp><rt>うご</rt><rp>)</rp></ruby>かす", en: "Run with the Java calc service", zh: "使用 Java 计算服务运行" },
  { file: "05-real-claude.html", group: "run", ja: "<ruby class=\"furi\">実<rp>(</rp><rt>じつ</rt><rp>)</rp></ruby><ruby class=\"furi\">物<rp>(</rp><rt>ぶつ</rt><rp>)</rp></ruby>の Claude で<ruby class=\"furi\">動<rp>(</rp><rt>うご</rt><rp>)</rp></ruby>かす", en: "Run with real Claude", zh: "使用真实 Claude 运行" },
  { file: "06-tests-evals.html", group: "more", ja: "<ruby class=\"furi eng\">テスト<rp>(</rp><rt lang=\"en\">test</rt><rp>)</rp></ruby>と<ruby class=\"furi\">評<rp>(</rp><rt>ひょう</rt><rp>)</rp></ruby><ruby class=\"furi\">価<rp>(</rp><rt>か</rt><rp>)</rp></ruby>を<ruby class=\"furi\">実<rp>(</rp><rt>じっ</rt><rp>)</rp></ruby><ruby class=\"furi\">行<rp>(</rp><rt>こう</rt><rp>)</rp></ruby>する", en: "Run tests & evals", zh: "运行测试与评估" },
  { file: "07-troubleshooting.html", group: "more", ja: "<ruby class=\"furi eng\">ローカル<rp>(</rp><rt lang=\"en\">local</rt><rp>)</rp></ruby><ruby class=\"furi\">実<rp>(</rp><rt>じっ</rt><rp>)</rp></ruby><ruby class=\"furi\">行<rp>(</rp><rt>こう</rt><rp>)</rp></ruby>の<ruby class=\"furi eng\">トラブルシューティング<rp>(</rp><rt lang=\"en\">troubleshooting</rt><rp>)</rp></ruby>", en: "Troubleshooting local runs", zh: "本地运行的故障排除" },
];

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

function pageLang() {
  const l = (document.documentElement.lang || "ja").toLowerCase();
  if (l.startsWith("zh")) return "zh";
  if (l.startsWith("en")) return "en";
  return "ja";
}
const LANG = pageLang();
const T = UI[LANG];


function buildNav(current) {
  const nav = document.querySelector("nav.side");
  if (nav) {
    const back = { ja: "← <ruby class=\"furi\">利<rp>(</rp><rt>り</rt><rp>)</rp></ruby><ruby class=\"furi\">用<rp>(</rp><rt>よう</rt><rp>)</rp></ruby><ruby class=\"furi eng\">ガイド<rp>(</rp><rt lang=\"en\">guide</rt><rp>)</rp></ruby>へ", en: "← User guide", zh: "← 使用说明" }[LANG];
    const menuLabel = { ja: "<ruby class=\"furi\">目<rp>(</rp><rt>もく</rt><rp>)</rp></ruby><ruby class=\"furi\">次<rp>(</rp><rt>じ</rt><rp>)</rp></ruby>", en: "Menu", zh: "目录" }[LANG];
    const closeLabel = { ja: "<ruby class=\"furi\">閉<rp>(</rp><rt>と</rt><rp>)</rp></ruby>じる", en: "Close", zh: "关闭" }[LANG];
    let html =
      `<div class="nav-bar">` +
      `<a class="brand" href="index.html">${T.brand}</a>` +
      `<button type="button" class="nav-toggle" aria-expanded="false" aria-controls="nav-content" aria-label="${menuLabel}">` +
      `<span class="nav-toggle-icon" aria-hidden="true">☰</span> <span class="nav-toggle-text">${menuLabel}</span>` +
      `</button>` +
      `</div>` +
      `<div class="nav-content" id="nav-content">` +
      `<a class="back-guide" href="../../${LANG}/index.html">${back}</a>`;
    // 分組は折りたたむ（アコーディオン）：開くのは 1 つだけ。最初は今のページの分組を開く
    const currentGroup = (PAGES.find((p) => p.file === current) || {}).group;
    let group = null;
    for (const p of PAGES) {
      if (p.group !== group) {
        if (group !== null) html += "</ul>";
        group = p.group;
        const open = group === currentGroup;
        html +=
          `<h3><button type="button" class="nav-group" data-group="${group}" aria-expanded="${open}">` +
          `<span class="caret" aria-hidden="true"></span>${GROUPS[group][LANG]}</button></h3>` +
          `<ul${open ? "" : " hidden"}>`;
      }
      const cls = p.file === current ? ' class="current"' : "";
      html += `<li><a href="${p.file}"${cls}>${p[LANG]}</a></li>`;
    }
    nav.innerHTML = html + "</ul></div>";

    const navToggle = nav.querySelector(".nav-toggle");
    const closeNav = () => {
      if (!navToggle) return;
      navToggle.setAttribute("aria-expanded", "false");
      nav.classList.remove("open");
      const icon = navToggle.querySelector(".nav-toggle-icon");
      const txt = navToggle.querySelector(".nav-toggle-text");
      if (icon) icon.textContent = "☰";
      if (txt) txt.textContent = menuLabel;
    };
    if (navToggle) {
      navToggle.addEventListener("click", () => {
        const expanded = navToggle.getAttribute("aria-expanded") === "true";
        const next = !expanded;
        navToggle.setAttribute("aria-expanded", String(next));
        nav.classList.toggle("open", next);
        const icon = navToggle.querySelector(".nav-toggle-icon");
        const txt = navToggle.querySelector(".nav-toggle-text");
        if (icon) icon.textContent = next ? "✕" : "☰";
        if (txt) txt.textContent = next ? closeLabel : menuLabel;
      });
      nav.querySelectorAll(".nav-content a").forEach((a) => {
        a.addEventListener("click", () => {
          if (window.innerWidth <= 860) closeNav();
        });
      });
      document.addEventListener("click", (e) => {
        if (window.innerWidth <= 860 && nav.classList.contains("open") && !nav.contains(e.target)) {
          closeNav();
        }
      });
    }

    const buttons = nav.querySelectorAll("button.nav-group");
    const setOpen = (btn, open) => {
      btn.setAttribute("aria-expanded", String(open));
      const list = btn.parentElement.nextElementSibling;
      if (list) list.hidden = !open;
    };
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const open = btn.getAttribute("aria-expanded") !== "true";
        // 1 つを開くと、ほかの分組（今のページの分組も）は閉じる
        if (open) buttons.forEach((other) => other !== btn && setOpen(other, false));
        setOpen(btn, open);
      });
    });
  }
  const i = PAGES.findIndex((p) => p.file === current);
  const pager = document.querySelector(".pager");
  if (pager && i >= 0) {
    const prev = PAGES[i - 1], next = PAGES[i + 1];
    pager.innerHTML =
      (prev ? `<a href="${prev.file}">← ${prev[LANG]}</a>` : "<span></span>") +
      (next ? `<a href="${next.file}">${next[LANG]} →</a>` : "<span></span>");
  }
}

// ページ上部の右側：言語切り替え（同じページへ）とテーマボタンの文言
function buildHeader(current) {
  const header = document.querySelector("header.top");
  if (!header) return;
  const sw = document.createElement("span");
  sw.className = "lang-switch";
  sw.setAttribute("aria-label", T.lang);
  sw.innerHTML = LANGS.map((l) =>
    l.code === LANG ? `<strong>${l.label}</strong>` : `<a href="../${l.code}/${current}" hreflang="${l.code}">${l.label}</a>`,
  ).join(" ｜ ");
  const btn = header.querySelector("#theme-toggle");
  if (btn) {
    btn.textContent = T.theme;
    header.insertBefore(sw, btn);
  } else {
    header.appendChild(sw);
  }
}

// 日本語版：ふりがなの表示切り替え（既定は表示。選択は保存する）
function setupFurigana() {
  if (LANG !== "ja") return;
  let off = false;
  try { off = localStorage.getItem("furigana") === "off"; } catch {}
  document.documentElement.classList.toggle("no-furi", off);
  const header = document.querySelector("header.top");
  const theme = document.querySelector("#theme-toggle");
  if (!header || !theme) return;
  const btn = document.createElement("button");
  btn.id = "furi-toggle";
  btn.type = "button";
  const label = () => (btn.textContent = off ? "ふりがな：なし" : "ふりがな：あり");
  label();
  btn.addEventListener("click", () => {
    off = !off;
    document.documentElement.classList.toggle("no-furi", off);
    try { localStorage.setItem("furigana", off ? "off" : "on"); } catch {}
    label();
    spaceRuby();
  });
  header.insertBefore(btn, theme);
}

// ルビは CSS で文字の真上に浮かせている。同じ行の隣り合うルビが実際の位置で重なるときだけ、後ろの文字の前を必要な分だけ空ける。
// 仮名の上にはみ出すのはかまわない。位置はまとめて測ってまとめて書き込む。空けたことで改行が変わることがあるので、もう 1 回だけ確かめる。
function spaceRuby(root = document) {
  const rubies = [...root.querySelectorAll("ruby.furi")];
  rubies.forEach((r) => (r.style.marginLeft = ""));
  for (let pass = 0; pass < 2; pass++) {
    const rt = rubies.map((r) => r.querySelector("rt")?.getBoundingClientRect());
    const base = rubies.map((r) => r.getBoundingClientRect());
    const add = new Array(rubies.length).fill(0);
    let line = null, shift = 0, prevRight = null;
    rubies.forEach((r, i) => {
      const q = rt[i];
      if (!q || !q.width) return; // 非表示のルビ
      if (line === null || Math.abs(base[i].top - line) > 4) { line = base[i].top; shift = 0; prevRight = null; }
      const left = q.left + shift;
      if (prevRight !== null && left < prevRight + 1) {
        add[i] = prevRight + 1 - left;
        shift += add[i];
      }
      prevRight = q.right + shift;
    });
    let changed = false;
    rubies.forEach((r, i) => {
      if (add[i] > 0) { changed = true; r.style.marginLeft = `${(parseFloat(r.style.marginLeft) || 0) + add[i]}px`; }
    });
    if (!changed) break;
  }
  // ルビ（特に英語）がセル・カードなどの幅より広くはみ出すときは、内側へずらして枠に収める
  const boxes = "td, th, .card, .callout, .node, .badge, .tags span, details, .caption-box";
  const rts = [...root.querySelectorAll("ruby.furi rt")];
  rts.forEach((rt) => (rt.style.transform = ""));
  const moves = rts.map((rt) => {
    const box = rt.closest(boxes);
    const q = rt.getBoundingClientRect();
    if (!box || !q.width) return null;
    const b = box.getBoundingClientRect();
    const pad = 2;
    if (q.left < b.left + pad) return [rt, b.left + pad - q.left];
    if (q.right > b.right - pad) return [rt, b.right - pad - q.right];
    return null;
  });
  moves.forEach((m) => m && (m[0].style.transform = `translateX(calc(-50% + ${m[1]}px))`));
}

// カタカナの上の英語の表示切り替え（既定は表示。選択は保存する）
function setupEnglish() {
  if (LANG !== "ja") return;
  let off = false;
  try { off = localStorage.getItem("eng-ruby") === "off"; } catch {}
  document.documentElement.classList.toggle("no-eng", off);
  const header = document.querySelector("header.top");
  const theme = document.querySelector("#theme-toggle");
  if (!header || !theme) return;
  const btn = document.createElement("button");
  btn.id = "eng-toggle";
  btn.type = "button";
  const label = () => (btn.textContent = off ? "英語：なし" : "英語：あり");
  label();
  btn.addEventListener("click", () => {
    off = !off;
    document.documentElement.classList.toggle("no-eng", off);
    try { localStorage.setItem("eng-ruby", off ? "off" : "on"); } catch {}
    label();
    spaceRuby();
  });
  header.insertBefore(btn, theme);
}

function currentTheme() {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setupThemeToggle() {
  try {
    const saved = localStorage.getItem("theme");
    if (saved) document.documentElement.dataset.theme = saved;
  } catch {}
  const btn = document.querySelector("#theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch {}
    location.reload(); // Mermaid を新しいテーマで描き直すため
  });
}

async function renderMermaid() {
  if (!document.querySelector(".mermaid")) return;
  const { default: mermaid } = await import(
    "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
  );
  // 節点の幅の計算と表示に同じフォントを使う（違うと CJK のラベルが切れる）。本文のフォント（言語ごと）に合わせる。
  const font = getComputedStyle(document.body).fontFamily;
  mermaid.initialize({
    fontFamily: font,
    themeVariables: { fontFamily: font },
    startOnLoad: false,
    theme: currentTheme() === "dark" ? "dark" : "default",
    securityLevel: "loose",
  });
  await mermaid.run({ querySelector: ".mermaid" });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, reduceMotion ? 0 : ms));
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);

/*
 * 端末の再生アニメーション。使い方：
 * <div class="term" data-title="bash">
 *   <script type="application/json">[
 *     {"cmd": "python -m core.agent \"…\""},          ← 1 文字ずつ入力されるコマンド
 *     {"out": "出力 1 行", "cls": "hl", "delay": 300},  ← 出力行（cls: out/dim/hl/warn/err、delay はミリ秒）
 *     {"pause": 800}                                   ← 一時停止
 *   ]</script>
 * </div>
 */
function setupTerminals() {
  document.querySelectorAll(".term").forEach((term) => {
    const data = term.querySelector('script[type="application/json"]');
    if (!data) return;
    const script = JSON.parse(data.textContent);
    term.innerHTML =
      `<div class="bar"><i></i><i></i><i></i><span class="title">${esc(term.dataset.title || "bash")}</span>` +
      `<button type="button" class="replay">${T.play}</button></div><div class="screen"></div>`;
    const screen = term.querySelector(".screen");
    const btn = term.querySelector(".replay");
    let run = 0;
    async function play() {
      const id = ++run;
      screen.innerHTML = "";
      btn.textContent = T.replay;
      for (const step of script) {
        if (id !== run) return;
        if (step.cmd !== undefined) {
          const line = document.createElement("div");
          line.innerHTML = '<span class="prompt">$ </span><span class="cmd"></span><span class="cursor"></span>';
          screen.appendChild(line);
          const cmd = line.querySelector(".cmd");
          for (const ch of step.cmd) {
            if (id !== run) return;
            cmd.textContent += ch;
            await sleep(step.speed || 28);
          }
          await sleep(350);
          line.querySelector(".cursor").remove();
        } else if (step.out !== undefined) {
          await sleep(step.delay ?? 90);
          const line = document.createElement("div");
          line.className = step.cls || "out";
          line.textContent = step.out === "" ? "\u00a0" : step.out; // 空行も 1 行分の高さを取る
          screen.appendChild(line);
        } else if (step.pause) {
          await sleep(step.pause);
        }
        screen.scrollTop = screen.scrollHeight;
      }
    }
    btn.addEventListener("click", play);
    // 画面に入ったら 1 回だけ自動で再生する
    new IntersectionObserver((entries, obs) => {
      if (entries.some((e) => e.isIntersecting)) { obs.disconnect(); play(); }
    }, { threshold: 0.4 }).observe(term);
  });
}

/*
 * 手順のアニメーション。使い方：
 * <div class="flow-anim" data-cols="5">
 *   <div class="stage">
 *     <div class="node" data-id="user">利用者<small>質問</small></div>
 *     <div class="arrow" data-id="a1">→</div> ...
 *   </div>
 *   <script type="application/json">[
 *     {"on": ["user"], "done": [], "fail": [], "packet": {"at": "user", "text": "質問"}, "text": "説明文（<code> も可）"}
 *   ]</script>
 * </div>
 * on：この手順で強調する節点・矢印の id、done：完了の印、fail：失敗の印、packet：節点の下に出す「データ」のラベル。
 */
function setupFlows() {
  document.querySelectorAll(".flow-anim").forEach((flow) => {
    const data = flow.querySelector('script[type="application/json"]');
    if (!data) return;
    const steps = JSON.parse(data.textContent);
    const stage = flow.querySelector(".stage");
    if (flow.dataset.cols) stage.style.gridTemplateColumns = `repeat(${flow.dataset.cols}, auto)`;
    flow.insertAdjacentHTML("beforeend",
      '<div class="caption-box"></div><div class="controls">' +
      `<button type="button" data-a="prev">${T.prev}</button><button type="button" data-a="play">${T.auto}</button>` +
      `<button type="button" data-a="next">${T.next}</button><div class="progress"><div></div></div></div>`);
    const cap = flow.querySelector(".caption-box");
    const bar = flow.querySelector(".progress > div");
    const playBtn = flow.querySelector('[data-a="play"]');
    let i = 0, timer = null;
    function show(n) {
      i = Math.max(0, Math.min(steps.length - 1, n));
      const s = steps[i];
      flow.querySelectorAll("[data-id]").forEach((el) => {
        const id = el.dataset.id;
        el.classList.toggle("active", (s.on || []).includes(id));
        el.classList.toggle("done", (s.done || []).includes(id));
        el.classList.toggle("fail", (s.fail || []).includes(id));
        el.querySelectorAll(".packet").forEach((p) => p.remove());
      });
      if (s.packet) {
        const at = flow.querySelector(`.node[data-id="${s.packet.at}"]`);
        if (at) at.insertAdjacentHTML("beforeend", `<span class="packet">${esc(s.packet.text)}</span>`);
      }
      cap.innerHTML = `<span class="step-no">${i + 1} / ${steps.length}</span>${s.text}`;
      if (LANG === "ja") spaceRuby(cap); // 説明文のルビの間隔を整える
      bar.style.width = `${((i + 1) / steps.length) * 100}%`;
    }
    function stop() { clearInterval(timer); timer = null; playBtn.textContent = T.auto; }
    flow.querySelector(".controls").addEventListener("click", (e) => {
      const a = e.target.dataset.a;
      if (a === "prev") { stop(); show(i - 1); }
      if (a === "next") { stop(); show(i + 1); }
      if (a === "play") {
        if (timer) return stop();
        if (i === steps.length - 1) show(0);
        playBtn.textContent = T.pause;
        timer = setInterval(() => (i < steps.length - 1 ? show(i + 1) : stop()), 2200);
      }
    });
    show(0);
  });
}

setupThemeToggle();
buildHeader(document.body.dataset.page);
setupFurigana();
setupEnglish();
if (LANG === "ja") (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => spaceRuby());
buildNav(document.body.dataset.page);
setupTerminals();
setupFlows();
renderMermaid();
