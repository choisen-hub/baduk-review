"""종합 리포트(대시보드 + 종합 진단 + 훈련장) HTML 렌더링.

훈련장 두 모드:
- 수읽기 문제: 실전 실수 장면에서 다음 수 찾기 + 이유 해설 + 변화 한 수씩 재생
- 형세판단 훈련: 중반 장면에서 형세 어림 → KataGo 집차이·소유권 지도로 채점
"""
import json
from datetime import datetime
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>바둑 종합 리포트</title>
<style>
:root {
  color-scheme: light dark;
  --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink2: #52514e;
  --muted: #898781; --grid: #e1e0d9; --axis: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --line: #2a78d6; --line2: #1baf7a;
  --good: #0ca30c; --warn: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --wood: #dcb35c; --wood-line: #7a5c28;
  --card: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --axis: #383835;
    --border: rgba(255,255,255,0.10);
    --line: #3987e5; --line2: #199e70;
    --wood: #b4914a; --wood-line: #4d3a17;
    --card: #21211f;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font-family: "Apple SD Gothic Neo", Pretendard, -apple-system, sans-serif;
  line-height: 1.65;
}
.wrap { max-width: 1340px; margin: 0 auto; padding: 28px 20px 80px; }
header h1 { font-size: 26px; margin: 0 0 6px; }
header .sub { color: var(--ink2); font-size: 14px; }
.oneliner {
  margin: 14px 0; padding: 14px 18px; background: var(--card);
  border: 1px solid var(--border); border-left: 4px solid var(--line);
  border-radius: 8px; font-size: 16px; font-weight: 600;
}
h2 { font-size: 19px; margin: 34px 0 12px; }
.card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 18px 20px; margin: 12px 0;
}
.cols { display: flex; gap: 28px; align-items: flex-start; margin-top: 20px; }
.left {
  position: sticky; top: 10px; flex: 0 0 auto; width: 508px;
  max-height: calc(100vh - 20px); overflow-y: auto; padding-right: 4px;
}
.right { flex: 1 1 0; min-width: 340px; }
@media (max-width: 1020px) {
  .cols { display: block; }
  .left { position: static; width: auto; max-height: none; overflow: visible; }
}
#qboard { display: block; cursor: crosshair; }
.qhead { font-size: 14px; margin: 8px 0 6px; min-height: 44px; }
.qhead b { font-size: 15px; }
.qbtns { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; align-items: center; }
.qbtns button, .glink {
  background: var(--card); color: var(--ink); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 12px; font-size: 13.5px; cursor: pointer;
  text-decoration: none;
}
.qbtns button:hover { border-color: var(--line); }
.qbtns button:disabled { opacity: 0.4; cursor: default; }
.qbtns button.jg { font-size: 12.5px; padding: 5px 9px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  border: 1px solid var(--border); background: var(--card); color: var(--ink2);
  border-radius: 999px; padding: 3px 12px; font-size: 13px; cursor: pointer;
}
.chip.on { border-color: var(--line); color: var(--ink); font-weight: 600; }
#verdict {
  margin-top: 10px; padding: 10px 14px; background: var(--card);
  border: 1px solid var(--border); border-radius: 8px; font-size: 13.5px; min-height: 42px;
}
#verdict .big { font-weight: 700; font-size: 14.5px; }
#verdict .why { margin-top: 8px; color: var(--ink2); }
#verdict .why b { color: var(--ink); }
#aiAnswer {
  display: none; margin-top: 10px; padding: 10px 14px; background: var(--card);
  border: 1px solid var(--line2); border-radius: 8px; font-size: 13.5px;
}
#aiAnswer .mvl { margin: 2px 0; }
#aiAnswer code { font-size: 12px; }
table.games { border-collapse: collapse; width: 100%; font-size: 13.5px; }
table.games th, table.games td {
  border: 1px solid var(--axis); padding: 6px 10px; text-align: left;
  background: var(--card); color: var(--ink);
}
table.games th { background: var(--page); font-weight: 700; }
table.games td.num { text-align: right; font-variant-numeric: tabular-nums; }
.bar { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 13px; }
.bar .lbl { flex: 0 0 64px; color: var(--ink2); }
#typeBars .lbl { flex-basis: 230px; }
.bar .track { flex: 1; background: var(--grid); border-radius: 4px; height: 14px; overflow: hidden; }
.bar .fill { height: 100%; background: var(--line); border-radius: 4px 0 0 4px; }
.bar .val { flex: 0 0 70px; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink2); }
.gradeChips { display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0; font-size: 13px; }
.gradeChips span { display: inline-flex; gap: 6px; align-items: center; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.wk { border-left: 4px solid var(--serious); }
.wk h3, .plan h3 { margin: 0 0 6px; font-size: 15.5px; }
.wk .ev { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
.plan { border-left: 4px solid var(--line2); }
.plan .cad { color: var(--muted); font-size: 12.5px; }
ul.compact li { margin: 7px 0; }
footer { margin-top: 60px; color: var(--muted); font-size: 12.5px; border-top: 1px solid var(--grid); padding-top: 14px; }
.note { color: var(--muted); font-size: 12.5px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>바둑 종합 리포트 · 훈련장</h1>
  <div class="sub">__SUBHEADER__</div>
  <div class="oneliner" id="oneliner"></div>
</header>

<div class="cols">
  <aside class="left">
    <div class="chips" id="modeChips" style="margin-bottom:8px">
      <button class="chip on" data-mode="quiz">수읽기 문제</button>
      <button class="chip" data-mode="ld">사활 문제</button>
      <button class="chip" data-mode="judge">형세판단 훈련</button>
    </div>
    <div class="qhead" id="qtitle"></div>
    <svg id="qboard"></svg>

    <div class="qbtns" id="quizNav">
      <button id="qPrev">◀ 이전</button>
      <button id="qNext">다음 ▶</button>
      <button id="qRetry">다시 풀기</button>
    </div>
    <div class="qbtns" id="pvBar" style="display:none">
      <span id="pvName" style="font-size:12.5px;color:var(--ink2)"></span>
      <button id="pvPrev">◀ 한 수 전</button>
      <button id="pvNext">한 수 진행 ▶</button>
      <button id="pvSwitch" style="display:none"></button>
    </div>
    <div class="qbtns" id="trialBar" style="display:none">
      <span id="trialLbl" style="font-size:12.5px;color:var(--line2);font-weight:600"></span>
      <button id="tUndo">◀ 한 수 무르기</button>
      <button id="tRedo">다시 진행 ▶</button>
      <button id="tAsk">AI에게 묻기</button>
      <button id="tClear">검토 지우기</button>
    </div>

    <div class="qbtns" id="judgeBtns" style="display:none">
      <button class="jg" data-b="B10">흑 크게 우세 (10집+)</button>
      <button class="jg" data-b="B3">흑 우세 (3~10집)</button>
      <button class="jg" data-b="EV">팽팽 (±3집)</button>
      <button class="jg" data-b="W3">백 우세 (3~10집)</button>
      <button class="jg" data-b="W10">백 크게 우세 (10집+)</button>
    </div>
    <div class="qbtns" id="judgeNav" style="display:none">
      <button id="jPrev">◀ 이전</button>
      <button id="jNext">다음 ▶</button>
      <button id="jRetry">다시</button>
    </div>

    <div id="verdict"></div>
    <div id="aiAnswer"></div>
  </aside>

  <main class="right">
    <h2 style="margin-top:0">전적 대시보드</h2>
    <div class="card" style="overflow-x:auto">
      <div class="note" id="recordLine" style="margin:0 0 8px"></div>
      <table class="games" id="gameTable"></table>
      <div class="note" id="skipNote" style="margin-top:8px"></div>
    </div>
    <div class="card">
      <h3 style="margin:0 0 8px;font-size:15px">내 수 등급 분포</h3>
      <div class="gradeChips" id="gradeChips"></div>
      <h3 style="margin:14px 0 8px;font-size:15px">단계별 손실 (집) <span class="note">승률 10~90% 경합 국면만 집계</span></h3>
      <div id="phaseBars"></div>
      <h3 style="margin:14px 0 8px;font-size:15px">실수 유형별 손실 (집) <span class="note">최선수가 실전수에서 5칸 이상 떨어져 있으면 "대세점 놓침"</span></h3>
      <div id="typeBars"></div>
    </div>

    <section id="secDiag"><h2>종합 진단</h2>
    <div class="card"><div id="overall" style="font-size:14.5px;color:var(--ink2)"></div></div>
    <div class="card">
      <h3 style="margin:0 0 6px;font-size:15px">유지할 강점</h3>
      <ul class="compact" id="strengths" style="font-size:14px;color:var(--ink2)"></ul>
    </div>
    <div id="weakList"></div>
    </section>

    <section id="secPlan"><h2>연습 플랜</h2>
    <div id="planList"></div>
    <div class="card">
      <h3 style="margin:0 0 6px;font-size:15px">대국 중 체크리스트</h3>
      <ul class="compact" id="checklist" style="font-size:14px"></ul>
    </div>
    </section>

    <footer>__FOOTER__</footer>
  </main>
</div>
</div>

<script>
const DATA = __DATA__;

const COLS = "ABCDEFGHJKLMNOPQRST";
const SZ = 19, CELL = 26, PAD = 30, BW = PAD * 2 + CELL * (SZ - 1);
const svg = document.getElementById("qboard");
svg.setAttribute("viewBox", `0 0 ${BW} ${BW}`);
svg.setAttribute("width", 500); svg.setAttribute("height", 500);
function px(x) { return PAD + x * CELL; }
function pyRow(r) { return PAD + r * CELL; } /* r = 화면 위에서부터의 행 */
function gtpToXY(v) {
  if (!v || v.toLowerCase() === "pass") return null;
  return { x: COLS.indexOf(v[0].toUpperCase()), y: parseInt(v.slice(1), 10) - 1 };
}
function stoneSvg(x, rTop, color, opts = {}) {
  const fill = color === "b" ? "#1a1a1a" : "#f4f4f2";
  const stroke = color === "b" ? "#000" : "#b9b8b2";
  let s = `<circle cx="${px(x)}" cy="${pyRow(rTop)}" r="${CELL * 0.47}" fill="${fill}" stroke="${stroke}" stroke-width="0.8" ${opts.ghost ? 'opacity="0.92"' : ""}/>`;
  if (opts.num !== undefined) {
    const tc = color === "b" ? "#fff" : "#111";
    s += `<text x="${px(x)}" y="${pyRow(rTop) + 3.8}" font-size="11" font-weight="700" text-anchor="middle" fill="${tc}">${opts.num}</text>`;
  }
  return s;
}
function boardBase(grid) {
  let s = `<rect x="0" y="0" width="${BW}" height="${BW}" rx="6" fill="var(--wood)"/>`;
  for (let i = 0; i < SZ; i++) {
    s += `<line x1="${px(0)}" y1="${pyRow(i)}" x2="${px(SZ-1)}" y2="${pyRow(i)}" stroke="var(--wood-line)" stroke-width="1"/>`;
    s += `<line x1="${px(i)}" y1="${pyRow(0)}" x2="${px(i)}" y2="${pyRow(SZ-1)}" stroke="var(--wood-line)" stroke-width="1"/>`;
  }
  for (const a of [3, 9, 15]) for (const b of [3, 9, 15])
    s += `<circle cx="${px(a)}" cy="${pyRow(b)}" r="2.6" fill="var(--wood-line)"/>`;
  for (let i = 0; i < SZ; i++) {
    s += `<text x="${px(i)}" y="${PAD - 14}" font-size="9.5" text-anchor="middle" fill="var(--wood-line)">${COLS[i]}</text>`;
    s += `<text x="${PAD - 16}" y="${pyRow(i) + 3.5}" font-size="9.5" text-anchor="middle" fill="var(--wood-line)">${SZ - i}</text>`;
  }
  grid.forEach((row, r) => {
    for (let x = 0; x < SZ; x++)
      if (row[x] !== ".") s += stoneSvg(x, r, row[x]);
  });
  return s;
}

/* ---------- 모드 ---------- */
let mode = "quiz";
document.getElementById("modeChips").addEventListener("click", e => {
  const c = e.target.closest("[data-mode]");
  if (!c) return;
  mode = c.dataset.mode;
  clearTrial();
  document.querySelectorAll("#modeChips .chip").forEach(x => x.classList.toggle("on", x === c));
  document.getElementById("quizNav").style.display = mode !== "judge" ? "flex" : "none";
  document.getElementById("pvBar").style.display = "none";
  document.getElementById("judgeBtns").style.display = mode === "judge" ? "flex" : "none";
  document.getElementById("judgeNav").style.display = mode === "judge" ? "flex" : "none";
  if (mode === "judge") goJudge(jCur); else goProb(qIdx[mode]);
});

/* ---------- 수읽기·사활 문제 (공용) ---------- */
const qIdx = { quiz: 0, ld: 0 };
let guess = null, revealed = false;
let pvLine = "best", pvStep = 0;
function curLine(p) {
  if (pvLine === "best") return p.bestPv;
  if (pvLine === "fight") return (p.fightMove && p.fightMove.pv) || [];
  return p.playedPv || [];
}
function nextPvLine(p) {
  const order = ["best"];
  if (p.playedPv && p.playedPv.length) order.push("played");
  if (p.fightMove && p.fightMove.pv && p.fightMove.pv.length) order.push("fight");
  return order[(order.indexOf(pvLine) + 1) % order.length];
}
let trial = null; /* {board(문자 2차원, 윗줄부터), seq:[{x,r,c,n}], next, redo:[{x,r}]} 직접 검토 */
function probs() { return mode === "ld" ? DATA.ldProblems : DATA.problems; }

/* 검토용 판 로직 (따냄 포함, 문자 배열: '.','b','w', r=윗줄부터) */
function nbRT(x, r) {
  const out = [];
  if (x > 0) out.push([x - 1, r]); if (x < SZ - 1) out.push([x + 1, r]);
  if (r > 0) out.push([x, r - 1]); if (r < SZ - 1) out.push([x, r + 1]);
  return out;
}
function groupRT(bd, x, r) {
  const color = bd[r][x], pts = [], seen = new Set(), st = [[x, r]];
  while (st.length) {
    const [cx, cr] = st.pop(), k = cx + "," + cr;
    if (seen.has(k)) continue;
    seen.add(k);
    if (bd[cr][cx] === color) { pts.push([cx, cr]); nbRT(cx, cr).forEach(p => st.push(p)); }
  }
  return pts;
}
function libsRT(bd, pts) {
  const l = new Set();
  for (const [x, r] of pts)
    for (const [nx, nr] of nbRT(x, r))
      if (bd[nr][nx] === ".") l.add(nx + "," + nr);
  return l.size;
}
function playRT(bd, x, r, c) {
  bd[r][x] = c;
  const opp = c === "b" ? "w" : "b";
  for (const [nx, nr] of nbRT(x, r)) {
    if (bd[nr][nx] === opp) {
      const g = groupRT(bd, nx, nr);
      if (libsRT(bd, g) === 0) for (const [gx, gr] of g) bd[gr][gx] = ".";
    }
  }
  const self = groupRT(bd, x, r);
  if (libsRT(bd, self) === 0) for (const [gx, gr] of self) bd[gr][gx] = ".";
}
function baseBoardNow(p) {
  /* 현재 표시 국면(문제 판 + 재생된 PV 수)의 문자 배열 */
  const bd = p.grid.map(row => row.split(""));
  if (revealed && pvStep > 0) {
    const line = curLine(p);
    let c = p.toMove;
    line.slice(0, pvStep).forEach(v => {
      const pt = gtpToXY(v);
      if (pt) playRT(bd, pt.x, SZ - 1 - pt.y, c);
      c = c === "b" ? "w" : "b";
    });
  }
  return bd;
}
function trialNextAt(p) {
  /* PV를 pvStep수 재생한 뒤 다음 차례 색 */
  let c = p.toMove;
  if (revealed && pvStep > 0) {
    for (let i = 0; i < pvStep; i++) c = c === "b" ? "w" : "b";
  }
  return c;
}
function clearTrial() {
  trial = null;
  document.getElementById("trialBar").style.display = "none";
  hideAi();
}
function hideAi() {
  const b = document.getElementById("aiAnswer");
  b.style.display = "none"; b.innerHTML = "";
}
function updateTrialBar() {
  const bar = document.getElementById("trialBar");
  if (!trial) { bar.style.display = "none"; return; }
  bar.style.display = "flex";
  document.getElementById("trialLbl").textContent =
    `검토 중 (${trial.seq.length}수) · 다음 ${trial.next === "b" ? "흑" : "백"} 차례`;
  document.getElementById("tUndo").disabled = !trial.seq.length;
  document.getElementById("tRedo").disabled = !(trial.redo && trial.redo.length);
  document.getElementById("tAsk").disabled = asking || !trial.seq.length;
}

function renderQuiz() {
  const p = probs()[qIdx[mode]];
  if (!p) {
    document.getElementById("qtitle").textContent = "이 유형의 문제가 없습니다.";
    svg.innerHTML = ""; return;
  }
  if (trial) {
    let s = boardBase(trial.board);
    for (const t of trial.seq)
      if (trial.board[t.r][t.x] === t.c)
        s += stoneSvg(t.x, t.r, t.c, { num: t.n, ghost: true });
    svg.innerHTML = s;
    document.getElementById("pvBar").style.display = "none";
    updateTrialBar();
    return;
  }
  let s = boardBase(p.grid);
  if (p.groupPts && !(revealed && pvStep > 0)) {
    for (const [gx, gy] of p.groupPts) {
      const cy = pyRow(SZ - 1 - gy);
      const stoneColor = p.groupColor === "b" ? "#fff" : "#111";
      s += `<path d="M ${px(gx)} ${cy - 6} L ${px(gx) - 5.5} ${cy + 4} L ${px(gx) + 5.5} ${cy + 4} Z" fill="none" stroke="${stoneColor}" stroke-width="1.8"/>`;
    }
  }
  const line = curLine(p);
  if (revealed && pvStep > 0) {
    let c = p.toMove;
    line.slice(0, pvStep).forEach((v, i) => {
      const pt = gtpToXY(v);
      if (pt) s += stoneSvg(pt.x, SZ - 1 - pt.y, c, { num: i + 1, ghost: true });
      c = c === "b" ? "w" : "b";
    });
  } else {
    if (guess) {
      const pt = gtpToXY(guess);
      s += `<circle cx="${px(pt.x)}" cy="${pyRow(SZ - 1 - pt.y)}" r="${CELL * 0.47}" fill="none" stroke="var(--line)" stroke-width="3"/>`;
      s += `<text x="${px(pt.x)}" y="${pyRow(SZ - 1 - pt.y) - 14}" font-size="10" font-weight="700" text-anchor="middle" fill="var(--line)">내 답</text>`;
    }
    if (revealed) {
      const b = gtpToXY(p.best), a = gtpToXY(p.played);
      if (b) {
        s += `<circle cx="${px(b.x)}" cy="${pyRow(SZ - 1 - b.y)}" r="${CELL * 0.36}" fill="none" stroke="var(--good)" stroke-width="3"/>`;
        s += `<text x="${px(b.x)}" y="${pyRow(SZ - 1 - b.y) - 13}" font-size="10" font-weight="700" text-anchor="middle" fill="var(--good)">최선</text>`;
      }
      if (a && p.played !== p.best) {
        s += `<line x1="${px(a.x)-7}" y1="${pyRow(SZ-1-a.y)-7}" x2="${px(a.x)+7}" y2="${pyRow(SZ-1-a.y)+7}" stroke="var(--critical)" stroke-width="3"/>`;
        s += `<line x1="${px(a.x)-7}" y1="${pyRow(SZ-1-a.y)+7}" x2="${px(a.x)+7}" y2="${pyRow(SZ-1-a.y)-7}" stroke="var(--critical)" stroke-width="3"/>`;
        s += `<text x="${px(a.x)}" y="${pyRow(SZ - 1 - a.y) - 13}" font-size="10" font-weight="700" text-anchor="middle" fill="var(--critical)">실전</text>`;
      }
    }
  }
  svg.innerHTML = s;
  const colorKr = p.toMove === "b" ? "흑" : "백";
  const label = mode === "ld" ? "사활" : "문제";
  const hint = p.qtext ? p.qtext : `(${p.region} 부근이 초점)`;
  document.getElementById("qtitle").innerHTML =
    `<b>${label} ${qIdx[mode] + 1}/${probs().length}</b> · ${p.game} ${p.moveNum}수 장면 · <b>${colorKr} 차례</b> ${hint}`;
  const bar = document.getElementById("pvBar");
  bar.style.display = revealed && p.bestPv.length ? "flex" : "none";
  if (revealed) {
    const name = pvLine === "best" ? "최선 변화" : (pvLine === "fight" ? "승부수 변화" : "실전 예상 진행");
    document.getElementById("pvName").textContent = `${name} ${pvStep}/${line.length}수`;
    const sw = document.getElementById("pvSwitch");
    const nx = nextPvLine(p);
    if (nx !== pvLine) {
      sw.style.display = "inline-block";
      sw.textContent = nx === "best" ? "최선 변화로" : (nx === "fight" ? "승부수 변화 보기" : "실전 진행과 비교");
    } else sw.style.display = "none";
  }
}
function quizVerdict(p, g) {
  if (g === p.best) return `<span class="big" style="color:var(--good)">정답입니다!</span> KataGo 1순위 ${p.best}.`;
  const ci = p.candidates.findIndex(c => c.move === g);
  const bestLead = p.candidates.length ? p.candidates[0].scoreLead : null;
  if (ci > 0) {
    const diff = Math.abs(bestLead - p.candidates[ci].scoreLead).toFixed(1);
    return `<span class="big" style="color:var(--line)">아깝습니다.</span> ${g}는 KataGo ${ci + 1}순위, 최선 ${p.best}보다 약 ${diff}집 손해입니다.`;
  }
  if (g === p.played) return `<span class="big" style="color:var(--critical)">실전과 같은 수입니다.</span> 이 수로 ${p.lossPts}집을 잃었습니다. 최선은 ${p.best}.`;
  return `<span class="big">${g}는 상위 후보에 없습니다.</span> 최선은 ${p.best}, 실전(${p.played})은 ${p.lossPts}집 손실이었습니다.`;
}
svg.addEventListener("click", ev => {
  if (mode === "judge") return;
  const p = probs()[qIdx[mode]];
  if (!p) return;
  const rect = svg.getBoundingClientRect();
  const sx = (ev.clientX - rect.left) * (BW / rect.width);
  const sy = (ev.clientY - rect.top) * (BW / rect.height);
  const x = Math.round((sx - PAD) / CELL), r = Math.round((sy - PAD) / CELL);
  if (x < 0 || x >= SZ || r < 0 || r >= SZ) return;
  if (revealed) {
    /* 채점 이후: 직접 돌을 놓아 변화 검토 (따냄 계산 포함) */
    if (!trial) trial = { board: baseBoardNow(p), seq: [], next: trialNextAt(p), redo: [] };
    if (trial.board[r][x] !== ".") return;
    playRT(trial.board, x, r, trial.next);
    trial.seq.push({ x, r, c: trial.next, n: trial.seq.length + 1 });
    trial.next = trial.next === "b" ? "w" : "b";
    trial.redo = []; /* 새 수를 두면 그 지점부터의 되돌리기 기록은 무효 */
    hideAi();
    updateTrialBar(); renderQuiz();
    return;
  }
  if (p.grid[r][x] !== ".") return;
  guess = COLS[x] + (SZ - r);
  revealed = true; pvStep = 0; pvLine = "best";
  let html = quizVerdict(p, guess);
  if (p.outcome) html += `<div class="why"><b>실전 결과:</b> ${p.outcome}</div>`;
  const why = p.why || p.reviewComment;
  if (why) html += `<div class="why"><b>왜?</b> ${why}</div>`;
  if (p.variation) html += `<div class="why"><b>이후 변화:</b> ${p.variation} <span class="note">(아래 "한 수 진행" 버튼으로 직접 따라가 보세요)</span></div>`;
  if (p.fightMove) html += `<div class="why"><b>승부수 후보:</b> ${p.fightMove.move}. 불리한 국면이라 KataGo 최선(${p.best})보다 승률은 약 ${p.fightMove.wrDrop}%p 낮지만 변화 폭이 훨씬 큽니다(집차이 표준편차 ${p.fightMove.stdev} 대 ${p.fightMove.bestStdev}). 사람 상대로 역전을 노린다면 이쪽이 껄끄럽습니다. <span class="note">("승부수 변화 보기" 버튼으로 진행 확인)</span></div>`;
  document.getElementById("verdict").innerHTML = html;
  renderQuiz();
});
function goProb(i) {
  const n = probs().length;
  if (n) qIdx[mode] = (i + n) % n;
  guess = null; revealed = false; pvStep = 0; pvLine = "best";
  clearTrial();
  document.getElementById("verdict").textContent = mode === "ld"
    ? "△ 무리의 사활 급소를 직접 놓아 보세요. 채점 후에는 판을 클릭해 변화를 검토할 수 있습니다: 방향키로 한 수씩 무르기·다시 진행, \"AI에게 묻기\"로 그 변화의 평가까지."
    : "판 위에 직접 다음 수를 놓아 보세요. 채점 후에는 판을 클릭해 변화를 검토할 수 있습니다: 방향키로 한 수씩 무르기·다시 진행, \"AI에게 묻기\"로 그 변화의 평가까지.";
  renderQuiz();
}
document.getElementById("qPrev").onclick = () => goProb(qIdx[mode] - 1);
document.getElementById("qNext").onclick = () => goProb(qIdx[mode] + 1);
document.getElementById("qRetry").onclick = () => goProb(qIdx[mode]);
document.getElementById("pvNext").onclick = () => {
  clearTrial();
  const p = probs()[qIdx[mode]];
  const line = curLine(p);
  if (pvStep < line.length) pvStep++;
  renderQuiz();
};
document.getElementById("pvPrev").onclick = () => { clearTrial(); if (pvStep > 0) pvStep--; renderQuiz(); };
document.getElementById("pvSwitch").onclick = () => {
  clearTrial(); pvLine = nextPvLine(probs()[qIdx[mode]]); pvStep = 0; renderQuiz();
};
function rebuildTrial(p, seq, redo) {
  trial = { board: baseBoardNow(p), seq: [], next: trialNextAt(p), redo: redo };
  for (const m of seq) {
    playRT(trial.board, m.x, m.r, trial.next);
    trial.seq.push({ x: m.x, r: m.r, c: trial.next, n: trial.seq.length + 1 });
    trial.next = trial.next === "b" ? "w" : "b";
  }
}
document.getElementById("tUndo").onclick = () => {
  if (!trial || !trial.seq.length) return;
  const p = probs()[qIdx[mode]];
  const last = trial.seq[trial.seq.length - 1];
  /* 한 수만 무르고, 무른 수는 redo에 쌓아 "다시 진행"으로 복원할 수 있게 한다 */
  rebuildTrial(p, trial.seq.slice(0, -1), [{ x: last.x, r: last.r }].concat(trial.redo || []));
  updateTrialBar(); renderQuiz();
};
document.getElementById("tRedo").onclick = () => {
  if (!trial || !trial.redo || !trial.redo.length) return;
  const m = trial.redo.shift();
  if (trial.board[m.r][m.x] === ".") {
    playRT(trial.board, m.x, m.r, trial.next);
    trial.seq.push({ x: m.x, r: m.r, c: trial.next, n: trial.seq.length + 1 });
    trial.next = trial.next === "b" ? "w" : "b";
  }
  updateTrialBar(); renderQuiz();
};
document.getElementById("tClear").onclick = () => { clearTrial(); renderQuiz(); };

/* ---------- 검토 변화도 AI 평가 ---------- */
const ASK_URL = "http://127.0.0.1:8791/eval";
let asking = false;
function fmtLead(v) { return v >= 0 ? `흑 +${v.toFixed(1)}집` : `백 +${(-v).toFixed(1)}집`; }
function gradeOf(pts, wr) {
  if (pts >= 6 || wr >= 0.15) return "대악수";
  if (pts >= 3 || wr >= 0.08) return "실수";
  if (pts >= 1.5 || wr >= 0.04) return "완착";
  if (pts <= 0.3) return "호착";
  return "보통";
}
const askGradeColor = { "호착": "var(--good)", "보통": "var(--muted)", "완착": "var(--warn)",
                        "실수": "var(--serious)", "대악수": "var(--critical)" };
document.getElementById("tAsk").onclick = async () => {
  if (!trial || !trial.seq.length || asking) return;
  const p = probs()[qIdx[mode]];
  const base = baseBoardNow(p);
  const initial = [];
  for (let r = 0; r < SZ; r++)
    for (let x = 0; x < SZ; x++)
      if (base[r][x] !== ".") initial.push([base[r][x] === "b" ? "B" : "W", COLS[x] + (SZ - r)]);
  const seq = trial.seq.map(m => ({ c: m.c, gtp: COLS[m.x] + (SZ - m.r) }));
  const moves = seq.map(m => [m.c === "b" ? "B" : "W", m.gtp]);
  const box = document.getElementById("aiAnswer");
  box.style.display = "block";
  box.innerHTML = "KataGo가 이 변화를 검토하는 중입니다… (수순이 길수록 오래 걸립니다)";
  asking = true; updateTrialBar();
  try {
    const res = await fetch(ASK_URL, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ komi: 6.5, initial, moves }) });
    const d = await res.json();
    if (!res.ok || d.error) throw new Error(d.error || "HTTP " + res.status);
    box.innerHTML = aiAnswerHtml(d.turns, seq);
  } catch (err) {
    box.innerHTML = `<b>AI 평가 서버에 연결하지 못했습니다.</b>
      <div style="margin-top:6px;color:var(--ink2)">터미널에서 서버를 켠 뒤 다시 눌러 주세요 (45분 무사용 시 자동 종료됩니다):</div>
      <code>cd "$HOME/Desktop/7 예술/바둑/baduk-review" && ./ask</code>`;
  }
  asking = false;
  if (trial) updateTrialBar();
};
function aiAnswerHtml(T, seq) {
  const n = seq.length;
  let h = `<b>KataGo가 본 이 변화</b> <span style="color:var(--muted)">(손실은 그 수를 둔 쪽 기준)</span>`;
  for (let i = 1; i <= n; i++) {
    const m = seq[i - 1], sign = m.c === "b" ? 1 : -1;
    const pts = sign * (T[i - 1].scoreLead - T[i].scoreLead);
    const wr = sign * (T[i - 1].winrate - T[i].winrate);
    const g = gradeOf(pts, wr);
    const who = m.c === "b" ? "흑" : "백";
    const lossTxt = pts >= 0.5 ? `${pts.toFixed(1)}집 손해`
      : (pts <= -0.5 ? `상대 실수로 ${(-pts).toFixed(1)}집 이득` : "손실 거의 없음");
    const star = T[i - 1].best === m.gtp ? ` · <span style="color:var(--good)">KataGo 1순위!</span>` : "";
    h += `<div class="mvl">${i}. ${who} ${m.gtp} <b style="color:${askGradeColor[g]}">${g}</b> · ${lossTxt}${star}</div>`;
  }
  h += `<div style="margin-top:8px">형세: ${fmtLead(T[0].scoreLead)} → <b>${fmtLead(T[n].scoreLead)}</b> (흑 승률 ${(T[n].winrate * 100).toFixed(0)}%)</div>`;
  const pv = (T[n].pv && T[n].pv.length ? T[n].pv : (T[n].best ? [T[n].best] : [])).slice(0, 6);
  if (pv.length) {
    const nextKr = trial && trial.next === "b" ? "흑" : "백";
    h += `<div style="color:var(--ink2)">이 다음 ${nextKr}부터의 KataGo 추천 진행: ${pv.join(" → ")}</div>`;
  }
  return h;
}

/* 방향키: 검토 중이면 무르기/다시 진행, 아니면 변화 재생 이동 */
document.addEventListener("keydown", e => {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  if (mode === "judge") return;
  if (trial) {
    document.getElementById(e.key === "ArrowLeft" ? "tUndo" : "tRedo").click();
    e.preventDefault();
  } else if (revealed && document.getElementById("pvBar").style.display !== "none") {
    document.getElementById(e.key === "ArrowLeft" ? "pvPrev" : "pvNext").click();
    e.preventDefault();
  }
});

/* ---------- 형세판단 훈련 ---------- */
let jCur = 0, jGuess = null;
function bucketOf(lead) {
  if (lead >= 10) return "B10";
  if (lead >= 3) return "B3";
  if (lead > -3) return "EV";
  if (lead > -10) return "W3";
  return "W10";
}
const bucketKr = { B10: "흑 크게 우세", B3: "흑 우세", EV: "팽팽", W3: "백 우세", W10: "백 크게 우세" };
function renderJudge() {
  if (!DATA.judgments.length) {
    document.getElementById("qtitle").textContent = "형세판단 문제가 없습니다.";
    svg.innerHTML = ""; return;
  }
  const p = DATA.judgments[jCur];
  let s = boardBase(p.grid);
  if (jGuess !== null) {
    /* 소유권 지도: 빈 점은 사각 음영, 반대색 소유의 돌은 ✕(사실상 죽은 돌) */
    for (let i = 0; i < p.ownership.length; i++) {
      const v = p.ownership[i];              /* 흑 기준 -1~1 */
      const x = i % SZ, r = Math.floor(i / SZ);
      const cell = p.grid[r][x];
      if (cell === ".") {
        if (Math.abs(v) < 0.25) continue;
        const size = 4 + Math.abs(v) * 8;
        const fill = v > 0 ? "#1a1a1a" : "#f4f4f2";
        s += `<rect x="${px(x) - size / 2}" y="${pyRow(r) - size / 2}" width="${size}" height="${size}" fill="${fill}" opacity="0.75" stroke="${v > 0 ? "#000" : "#999"}" stroke-width="0.5"/>`;
      } else {
        const stoneSign = cell === "b" ? 1 : -1;
        if (v * stoneSign < -0.5) {
          const mc = cell === "b" ? "#ff5555" : "#cc2222";
          s += `<line x1="${px(x)-6}" y1="${pyRow(r)-6}" x2="${px(x)+6}" y2="${pyRow(r)+6}" stroke="${mc}" stroke-width="2.5"/>`;
          s += `<line x1="${px(x)-6}" y1="${pyRow(r)+6}" x2="${px(x)+6}" y2="${pyRow(r)-6}" stroke="${mc}" stroke-width="2.5"/>`;
        }
      }
    }
  }
  svg.innerHTML = s;
  document.getElementById("qtitle").innerHTML =
    `<b>형세판단 ${jCur + 1}/${DATA.judgments.length}</b> · ${p.game} · <b>${p.turn}수 시점</b> (전체 ${p.nMoves}수 중) · 지금 형세는?`;
}
document.getElementById("judgeBtns").addEventListener("click", e => {
  const b = e.target.closest("[data-b]");
  if (!b || jGuess !== null) return;
  jGuess = b.dataset.b;
  const p = DATA.judgments[jCur];
  const actual = bucketOf(p.scoreLead);
  const ok = jGuess === actual;
  const leadKr = p.scoreLead >= 0 ? `흑 +${p.scoreLead}집` : `백 +${Math.abs(p.scoreLead)}집`;
  let html = ok
    ? `<span class="big" style="color:var(--good)">정답!</span> `
    : `<span class="big" style="color:var(--critical)">오답.</span> 님의 판단: ${bucketKr[jGuess]} → `;
  html += `실제 형세: <b>${leadKr}</b> (${bucketKr[actual]}, 흑 승률 ${(p.winrate * 100).toFixed(0)}%)`;
  html += `<div class="why">판 위 음영이 KataGo가 보는 소유권입니다: 진한 사각형일수록 확정에 가까운 집, ✕ 표시는 사실상 죽은 돌입니다. 음영을 눈으로 2집씩 짝지어 세는 연습을 하면 형세판단이 빨리 늡니다.</div>`;
  document.getElementById("verdict").innerHTML = html;
  renderJudge();
});
function goJudge(i) {
  if (!DATA.judgments.length) { renderJudge(); return; }
  jCur = (i + DATA.judgments.length) % DATA.judgments.length;
  jGuess = null;
  document.getElementById("verdict").textContent =
    "장면을 보고 아래 버튼으로 형세를 판단해 보세요. 채점 후 KataGo 소유권 지도가 표시됩니다.";
  renderJudge();
}
document.getElementById("jPrev").onclick = () => goJudge(jCur - 1);
document.getElementById("jNext").onclick = () => goJudge(jCur + 1);
document.getElementById("jRetry").onclick = () => goJudge(jCur);

/* ---------- 대시보드 ---------- */
const gt = document.getElementById("gameTable");
gt.innerHTML = `<tr><th>대국</th><th>구분</th><th>결과</th><th>내 색</th><th>수</th><th>경합 국면 문제 수</th><th>경합 손실(집)</th><th>실수·대악수/100수</th></tr>` +
  DATA.games.map(g =>
    `<tr><td><a class="glink" style="border:none;padding:0" href="file://${encodeURI(g.report)}">${g.name}</a></td>
     <td>${g.kind || ""}</td><td>${g.result}</td><td>${g.myColor === "b" ? "흑" : "백"}</td>
     <td class="num">${g.nMoves}</td><td class="num">${g.nBad}</td><td class="num">${g.totalLoss}</td><td class="num">${g.per100}</td></tr>`).join("");
if (DATA.agg.record) {
  const rec = DATA.agg.record;
  document.getElementById("recordLine").textContent = Object.keys(rec).map(k => {
    const r = rec[k];
    return `${k} ${r.games}국 ${r.wins}승 ${r.games - r.wins}패 (흑 ${r.b[1]}/${r.b[0]}, 백 ${r.w[1]}/${r.w[0]})`;
  }).join(" · ");
}
if (DATA.skipped.length)
  document.getElementById("skipNote").textContent =
    "제외: " + DATA.skipped.join(", ") + " (선수가 어느 색인지 폴더명에 표기가 없는 대국)";

const gradeColor = { "호착": "var(--good)", "보통": "var(--muted)", "완착": "var(--warn)", "실수": "var(--serious)", "대악수": "var(--critical)" };
document.getElementById("gradeChips").innerHTML =
  ["호착", "보통", "완착", "실수", "대악수"].map(g =>
    `<span><span class="dot" style="background:${gradeColor[g]}"></span>${g} ${DATA.agg.grade[g] || 0}수</span>`).join("");
function bars(elId, obj) {
  const entries = Object.entries(obj);
  const max = Math.max(...entries.map(e => e[1]), 1);
  document.getElementById(elId).innerHTML = entries.map(([k, v]) =>
    `<div class="bar"><span class="lbl">${k}</span>
     <div class="track"><div class="fill" style="width:${v / max * 100}%"></div></div>
     <span class="val">${v}집</span></div>`).join("");
}
bars("phaseBars", DATA.agg.phase);
bars("typeBars", DATA.agg.mtype);

/* ---------- 종합 진단 ---------- */
const S = DATA.synthesis || {};
document.getElementById("oneliner").textContent = S.oneLiner || "";
if (!S.oneLiner) document.getElementById("oneliner").style.display = "none";
if (!S.overall) {
  document.getElementById("secDiag").style.display = "none";
  document.getElementById("secPlan").style.display = "none";
} else {
  document.getElementById("overall").textContent = S.overall;
  document.getElementById("strengths").innerHTML = (S.strengths || []).map(s => `<li>${s}</li>`).join("");
  document.getElementById("weakList").innerHTML = (S.weaknesses || []).map(w =>
    `<div class="card wk"><h3>${w.pattern}</h3>
     <div style="font-size:14px;color:var(--ink2)">${w.fix}</div>
     <div class="ev">근거: ${w.evidence}</div></div>`).join("");
  document.getElementById("planList").innerHTML = (S.practicePlan || []).map(p =>
    `<div class="card plan"><h3>${p.focus} <span class="cad">· ${p.cadence}</span></h3>
     <div style="font-size:14px;color:var(--ink2)">${p.how}</div></div>`).join("");
  document.getElementById("checklist").innerHTML = (S.checklist || []).map(c => `<li>${c}</li>`).join("");
}
goProb(0);
</script>
</body>
</html>
"""


def render(per_game, problems, agg, synthesis, skipped, out_path,
           judgments=None, ld_problems=None):
    data = {
        "games": per_game,
        "problems": problems,
        "agg": agg,
        "synthesis": synthesis,
        "skipped": skipped,
        "judgments": judgments or [],
        "ldProblems": ld_problems or [],
    }
    n_games = len(per_game)
    sub = (f"{n_games}판 종합 · 수읽기 {len(problems)}문제 · 사활 {len(ld_problems or [])}문제 · "
           f"형세판단 {len(judgments or [])}장면 · "
           f"생성 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    footer = "판별 상세는 대시보드의 대국 이름을 클릭 · KataGo + Claude 종합 진단"
    html = (TEMPLATE
            .replace("__SUBHEADER__", sub)
            .replace("__FOOTER__", footer)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    Path(out_path).write_text(html, encoding="utf-8")
