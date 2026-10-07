// 利用ガイドの共通スクリプト：ナビゲーション、言語切り替え、テーマ切り替え、Mermaid、
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
    brand: "EchoLab 利用ガイド", theme: "ライト／ダーク", lang: "言語",
    play: "▶ 再生", replay: "もう一度", prev: "◀ 前へ", next: "次へ ▶", auto: "▶ 自動再生", pause: "一時停止",
    menu: "目次", closeMenu: "閉じる",
  },
  en: {
    brand: "EchoLab User Guide", theme: "Light / Dark", lang: "Language",
    play: "▶ Play", replay: "Replay", prev: "◀ Back", next: "Next ▶", auto: "▶ Auto-play", pause: "Pause",
    menu: "Menu", closeMenu: "Close",
  },
  zh: {
    brand: "EchoLab 使用说明", theme: "切换明暗", lang: "语言",
    play: "▶ 播放", replay: "重播", prev: "◀ 上一步", next: "下一步 ▶", auto: "▶ 自动播放", pause: "暂停",
    menu: "目录", closeMenu: "关闭",
  },
};

const GROUPS = {
  start: { ja: "はじめに", en: "Getting started", zh: "开始" },
  use: { ja: "<ruby class=\"furi\">使<rp>(</rp><rt>つか</rt><rp>)</rp></ruby>い<ruby class=\"furi\">方<rp>(</rp><rt>かた</rt><rp>)</rp></ruby>", en: "Using EchoLab", zh: "使用" },
  understand: { ja: "しくみ", en: "How it works", zh: "理解" },
  advanced: { ja: "<ruby class=\"furi\">応<rp>(</rp><rt>おう</rt><rp>)</rp></ruby><ruby class=\"furi\">用<rp>(</rp><rt>よう</rt><rp>)</rp></ruby>", en: "Advanced", zh: "进阶" },
};

const PAGES = [
  { file: "index.html", group: "start", ja: "<ruby class=\"furi eng\">トップ<rp>(</rp><rt lang=\"en\">top</rt><rp>)</rp></ruby>・EchoLab とは", en: "Home: what is EchoLab", zh: "首页・EchoLab 是什么" },
  { file: "01-quickstart.html", group: "start", ja: "<ruby class=\"furi eng\">インストール<rp>(</rp><rt lang=\"en\">install</rt><rp>)</rp></ruby>と<ruby class=\"furi\">最<rp>(</rp><rt>さい</rt><rp>)</rp></ruby><ruby class=\"furi\">初<rp>(</rp><rt>しょ</rt><rp>)</rp></ruby>の<ruby class=\"furi\">質<rp>(</rp><rt>しつ</rt><rp>)</rp></ruby><ruby class=\"furi\">問<rp>(</rp><rt>もん</rt><rp>)</rp></ruby>", en: "Install & first question", zh: "安装与第一次提问" },
  { file: "02-what-to-ask.html", group: "use", ja: "<ruby class=\"furi\">何<rp>(</rp><rt>なん</rt><rp>)</rp></ruby>を<ruby class=\"furi\">聞<rp>(</rp><rt>き</rt><rp>)</rp></ruby>けるか：<ruby class=\"furi\">機<rp>(</rp><rt>き</rt><rp>)</rp></ruby><ruby class=\"furi\">能<rp>(</rp><rt>のう</rt><rp>)</rp></ruby><ruby class=\"furi\">一<rp>(</rp><rt>いち</rt><rp>)</rp></ruby><ruby class=\"furi\">覧<rp>(</rp><rt>らん</rt><rp>)</rp></ruby>", en: "What you can ask", zh: "能问什么：功能一览" },
  { file: "03-reading-answers.html", group: "use", ja: "<ruby class=\"furi\">回<rp>(</rp><rt>かい</rt><rp>)</rp></ruby><ruby class=\"furi\">答<rp>(</rp><rt>とう</rt><rp>)</rp></ruby>の<ruby class=\"furi\">読<rp>(</rp><rt>よ</rt><rp>)</rp></ruby>み<ruby class=\"furi\">方<rp>(</rp><rt>かた</rt><rp>)</rp></ruby>", en: "Reading the answers", zh: "回答怎么读" },
  { file: "04-cli-reference.html", group: "use", ja: "<ruby class=\"furi eng\">コマンドリファレンス<rp>(</rp><rt lang=\"en\">command reference</rt><rp>)</rp></ruby>", en: "CLI reference", zh: "命令参考" },
  { file: "05-how-it-works.html", group: "understand", ja: "<ruby class=\"furi\">裏<rp>(</rp><rt>うら</rt><rp>)</rp></ruby><ruby class=\"furi\">側<rp>(</rp><rt>がわ</rt><rp>)</rp></ruby>で<ruby class=\"furi\">起<rp>(</rp><rt>お</rt><rp>)</rp></ruby>きていること（<ruby class=\"furi eng\">アニメーション<rp>(</rp><rt lang=\"en\">animation</rt><rp>)</rp></ruby>）", en: "What happens behind the scenes (animated)", zh: "背后发生了什么（动画）" },
  { file: "06-cost-and-safety.html", group: "understand", ja: "<ruby class=\"furi eng\">コスト<rp>(</rp><rt lang=\"en\">cost</rt><rp>)</rp></ruby>の<ruby class=\"furi\">上<rp>(</rp><rt>じょう</rt><rp>)</rp></ruby><ruby class=\"furi\">限<rp>(</rp><rt>げん</rt><rp>)</rp></ruby>と<ruby class=\"furi eng\">データ<rp>(</rp><rt lang=\"en\">data</rt><rp>)</rp></ruby>の<ruby class=\"furi\">確<rp>(</rp><rt>たし</rt><rp>)</rp></ruby>かさ", en: "Cost caps & data trust", zh: "成本上限与数据可信度" },
  { file: "07-traces-evals.html", group: "advanced", ja: "<ruby class=\"furi\">実<rp>(</rp><rt>じっ</rt><rp>)</rp></ruby><ruby class=\"furi\">行<rp>(</rp><rt>こう</rt><rp>)</rp></ruby><ruby class=\"furi eng\">トレース<rp>(</rp><rt lang=\"en\">trace</rt><rp>)</rp></ruby>と<ruby class=\"furi\">評<rp>(</rp><rt>ひょう</rt><rp>)</rp></ruby><ruby class=\"furi\">価<rp>(</rp><rt>か</rt><rp>)</rp></ruby>", en: "Traces & evals", zh: "执行轨迹与评估" },
  { file: "08-troubleshooting.html", group: "advanced", ja: "<ruby class=\"furi eng\">トラブルシューティング<rp>(</rp><rt lang=\"en\">troubleshooting</rt><rp>)</rp></ruby>と FAQ", en: "Troubleshooting & FAQ", zh: "故障排除与 FAQ" },
  { file: "09-roadmap.html", group: "advanced", ja: "<ruby class=\"furi\">今<rp>(</rp><rt>こん</rt><rp>)</rp></ruby><ruby class=\"furi\">後<rp>(</rp><rt>ご</rt><rp>)</rp></ruby>の<ruby class=\"furi\">機<rp>(</rp><rt>き</rt><rp>)</rp></ruby><ruby class=\"furi\">能<rp>(</rp><rt>のう</rt><rp>)</rp></ruby>（<ruby class=\"furi eng\">ロードマップ<rp>(</rp><rt lang=\"en\">roadmap</rt><rp>)</rp></ruby>）", en: "Roadmap", zh: "今后的功能（路线图）" },
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
    let html =
      `<div class="nav-bar">` +
      `<a class="brand" href="index.html">${T.brand}</a>` +
      `<div class="nav-tools">` +
      `<button type="button" class="nav-toggle" aria-expanded="false" aria-controls="nav-content" aria-label="${T.menu}">` +
      `<span class="nav-toggle-icon" aria-hidden="true">☰</span> <span class="nav-toggle-text">${T.menu}</span>` +
      `</button>` +
      `</div>` +
      `</div>` +
      `<div class="nav-content" id="nav-content">`;
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
      if (txt) txt.textContent = T.menu;
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
        if (txt) txt.textContent = next ? T.closeMenu : T.menu;
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

// 日本語版：ふりがなとカタカナ英語の表示切り替え（既定は表示。選択は保存し、モバイルではナビバーに配置）
function setupRubyToggles() {
  if (LANG !== "ja") return;
  let furiOff = false;
  let engOff = false;
  try { furiOff = localStorage.getItem("furigana") === "off"; } catch {}
  try { engOff = localStorage.getItem("eng-ruby") === "off"; } catch {}
  document.documentElement.classList.toggle("no-furi", furiOff);
  document.documentElement.classList.toggle("no-eng", engOff);

  const container = document.createElement("span");
  container.className = "ruby-toggles";

  const furiBtn = document.createElement("button");
  furiBtn.id = "furi-toggle";
  furiBtn.type = "button";
  const updateFuri = () => {
    furiBtn.textContent = furiOff ? "ふりがな：なし" : "ふりがな：あり";
    furiBtn.classList.toggle("on", !furiOff);
  };
  updateFuri();
  furiBtn.addEventListener("click", () => {
    furiOff = !furiOff;
    document.documentElement.classList.toggle("no-furi", furiOff);
    try { localStorage.setItem("furigana", furiOff ? "off" : "on"); } catch {}
    updateFuri();
    spaceRuby();
  });

  const engBtn = document.createElement("button");
  engBtn.id = "eng-toggle";
  engBtn.type = "button";
  const updateEng = () => {
    engBtn.textContent = engOff ? "英語：なし" : "英語：あり";
    engBtn.classList.toggle("on", !engOff);
  };
  updateEng();
  engBtn.addEventListener("click", () => {
    engOff = !engOff;
    document.documentElement.classList.toggle("no-eng", engOff);
    try { localStorage.setItem("eng-ruby", engOff ? "off" : "on"); } catch {}
    updateEng();
    spaceRuby();
  });

  container.appendChild(furiBtn);
  container.appendChild(engBtn);

  const place = () => {
    const navTools = document.querySelector("nav.side .nav-tools");
    const header = document.querySelector("header.top");
    const theme = document.querySelector("#theme-toggle");
    if (window.innerWidth <= 860 && navTools) {
      if (!navTools.contains(container)) {
        navTools.insertBefore(container, navTools.firstChild);
      }
    } else if (header && theme) {
      if (!header.contains(container)) {
        header.insertBefore(container, theme);
      }
    }
  };

  place();
  window.addEventListener("resize", place);
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
buildNav(document.body.dataset.page);
setupRubyToggles();
if (LANG === "ja") (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => spaceRuby());
setupTerminals();
setupFlows();
renderMermaid();
