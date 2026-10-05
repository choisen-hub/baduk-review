"""분석 + 해설을 단일 HTML 리포트로 렌더링."""
import json
from datetime import datetime
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
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
  margin: 18px 0 0; padding: 14px 18px; background: var(--card);
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
.right h2:first-child { margin-top: 0; }
@media (max-width: 1020px) {
  .cols { display: block; }
  .left { position: static; width: auto; max-height: none; overflow: visible; }
}
#board { display: block; touch-action: manipulation; }
.controls { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.controls button {
  background: var(--card); color: var(--ink); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 12px; font-size: 14px; cursor: pointer;
}
.controls button:hover { border-color: var(--line); }
.controls input[type=range] { flex: 1; min-width: 120px; accent-color: var(--line); }
#moveLabel { font-variant-numeric: tabular-nums; font-size: 14px; color: var(--ink2); min-width: 110px; }
.varBanner {
  display: none; margin-top: 8px; padding: 8px 12px; border-radius: 6px;
  background: var(--card); border: 1px solid var(--line); font-size: 13.5px;
}
.varBanner.on { display: block; }
#trialBar {
  display: none; margin-top: 8px; padding: 8px 12px; border-radius: 6px;
  background: var(--card); border: 1px solid var(--line2); font-size: 13px;
  align-items: center; gap: 8px;
}
#trialBar.on { display: flex; }
#trialBar button {
  background: none; border: 1px solid var(--border); color: var(--line);
  border-radius: 6px; padding: 2px 9px; font-size: 12px; cursor: pointer;
}
#trialBar button:disabled { opacity: 0.4; cursor: default; }
#aiAnswer {
  display: none; margin-top: 8px; padding: 10px 14px; background: var(--card);
  border: 1px solid var(--line2); border-radius: 8px; font-size: 13.5px; max-width: 500px;
}
#aiAnswer .mvl { margin: 2px 0; }
#aiAnswer code { font-size: 12px; }
#board { cursor: crosshair; }
.chips { display: flex; gap: 6px; margin-bottom: 8px; }
.chip {
  border: 1px solid var(--border); background: var(--card); color: var(--ink2);
  border-radius: 999px; padding: 3px 12px; font-size: 13px; cursor: pointer;
}
.chip.on { border-color: var(--line); color: var(--ink); font-weight: 600; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; font-size: 12.5px; color: var(--ink2); }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
#chartBox { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px; position: relative; }
#tooltip {
  position: absolute; pointer-events: none; display: none; z-index: 5;
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 6px 10px; font-size: 12.5px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  white-space: nowrap;
}
.storyGrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.story h3, .tp h3 { margin: 0 0 6px; font-size: 15.5px; }
.story .range { color: var(--muted); font-size: 12.5px; margin-left: 6px; font-weight: 400; }
.tp { border-left: 4px solid var(--critical); }
.tp .btns { margin-top: 10px; display: flex; gap: 8px; }
.tp .btns button, .mv button {
  background: none; border: 1px solid var(--border); color: var(--line);
  border-radius: 6px; padding: 3px 10px; font-size: 12.5px; cursor: pointer;
}
.tp .var { margin-top: 10px; padding: 10px 12px; background: var(--page); border-radius: 6px; font-size: 13.5px; }
.mv { display: flex; gap: 10px; align-items: baseline; padding: 9px 0; border-bottom: 1px solid var(--grid); }
.mv:last-child { border-bottom: none; }
.badge {
  flex: 0 0 auto; font-size: 11.5px; font-weight: 700; border-radius: 4px;
  padding: 1px 7px; color: #fff;
}
.badge.호착 { background: var(--good); }
.badge.완착 { background: var(--warn); color: #3a2c00; }
.badge.실수 { background: var(--serious); color: #401505; }
.badge.대악수 { background: var(--critical); }
.mv .who { font-weight: 600; white-space: nowrap; }
.mv .txt { color: var(--ink2); font-size: 14px; }
.lessons li { margin: 8px 0; }
footer { margin-top: 60px; color: var(--muted); font-size: 12.5px; border-top: 1px solid var(--grid); padding-top: 14px; }
table.dataTable { border-collapse: collapse; font-size: 13.5px; width: 100%; font-variant-numeric: tabular-nums; }
table.dataTable th {
  background: var(--page); color: var(--ink); font-weight: 700;
  border: 1px solid var(--axis); padding: 6px 10px; text-align: right;
}
table.dataTable td {
  background: var(--card); color: var(--ink);
  border: 1px solid var(--axis); padding: 5px 10px; text-align: right;
}
table.dataTable tr:nth-child(even) td { background: var(--page); }
.gradeTag { font-size: 11.5px; font-weight: 700; border-radius: 4px; padding: 1px 7px; color: #fff; }
.gradeTag.호착 { background: var(--good); }
.gradeTag.완착 { background: var(--warn); color: #3a2c00; }
.gradeTag.실수 { background: var(--serious); color: #401505; }
.gradeTag.대악수 { background: var(--critical); }
.gradeTag.보통 { background: var(--muted); }
#moveEval {
  margin-top: 10px; padding: 10px 14px; background: var(--card);
  border: 1px solid var(--border); border-radius: 8px; font-size: 13.5px;
  min-height: 44px; max-width: 500px;
}
#moveEval .rec { margin-top: 4px; color: var(--ink2); }
#moveEval button {
  background: none; border: 1px solid var(--border); color: var(--line);
  border-radius: 6px; padding: 2px 9px; font-size: 12px; cursor: pointer; margin-left: 6px;
}
details summary { cursor: pointer; color: var(--ink2); font-size: 13.5px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>__HEADER__</h1>
  <div class="sub">__SUBHEADER__</div>
</header>

<div class="cols">
  <aside class="left">
    <svg id="board"></svg>
    <div class="controls">
      <button id="btnStart" title="처음">⏮</button>
      <button id="btnPrev" title="이전 수">◀</button>
      <button id="btnNext" title="다음 수">▶</button>
      <button id="btnEnd" title="마지막">⏭</button>
      <input type="range" id="slider" min="0" value="0">
      <span id="moveLabel"></span>
    </div>
    <div class="varBanner" id="varBanner"></div>
    <div id="trialBar">
      <span id="trialLabel"></span>
      <button id="trialUndo">◀ 한 수 무르기</button>
      <button id="trialRedo">다시 진행 ▶</button>
      <button id="trialAsk">AI에게 묻기</button>
      <button id="trialClear">시험 수 지우기</button>
    </div>
    <div id="aiAnswer"></div>
    <div id="moveEval"></div>
    <div class="chips" style="margin-top:14px">
      <button class="chip on" data-metric="winrate">흑 승률</button>
      <button class="chip" data-metric="score">집차이 (흑 기준)</button>
    </div>
    <div id="chartBox">
      <svg id="chart" width="100%" height="220"></svg>
      <div id="tooltip"></div>
    </div>
    <div class="legend">
      <span><span class="dot" style="background:var(--good)"></span>호착</span>
      <span><span class="dot" style="background:var(--warn)"></span>완착</span>
      <span><span class="dot" style="background:var(--serious)"></span>실수</span>
      <span><span class="dot" style="background:var(--critical)"></span>대악수</span>
      <span style="color:var(--muted)">마커 클릭 = 장면 이동 · 판 클릭 = 직접 놓아보기</span>
    </div>
  </aside>

  <main class="right">
    <div class="oneliner" id="oneliner" style="margin:0 0 14px"></div>
    <div class="card" style="margin-top:0" id="overallCard">
      <h3 style="margin:0 0 6px;font-size:15px">총평</h3>
      <div id="overall" style="font-size:14.5px;color:var(--ink2)"></div>
    </div>

    <section id="secStory"><h2>대국 스토리</h2>
    <div class="storyGrid" id="storyGrid"></div></section>

    <section id="secTp"><h2>승부처</h2>
    <div id="tpList"></div></section>

    <section id="secGood"><h2>잘 둔 수</h2>
    <div class="card" id="goodList"></div></section>

    <section id="secBad"><h2>아쉬운 수</h2>
    <div class="card" id="badList"></div></section>

    <section id="secLessons"><h2>이 판에서 배워갈 것</h2>
    <div class="card"><ul class="lessons" id="lessonList"></ul></div></section>

    <section id="secStrengths"><h2>이 판에서 드러난 강점</h2>
    <div class="card"><ul class="lessons" id="strengthList"></ul></div></section>

    <section id="secWeak"><h2>이 판에서 드러난 약점과 보완</h2>
    <div class="card" id="weakList"></div></section>

    <details style="margin-top:30px"><summary>전체 수 평가 데이터 (표)</summary>
    <div class="card" style="overflow-x:auto"><table class="dataTable" id="rawTable"></table></div>
    </details>

    <footer>__FOOTER__</footer>
  </main>
</div>
</div>

<script>
const DATA = __DATA__;

/* ---------- 좌표 유틸 ---------- */
const COLS = "ABCDEFGHJKLMNOPQRST";
const SZ = DATA.meta.size;
function gtpToXY(v) {
  if (!v || v.toLowerCase() === "pass") return null;
  return { x: COLS.indexOf(v[0].toUpperCase()), y: parseInt(v.slice(1), 10) - 1 };
}

/* ---------- 판 재생 (따냄 포함) ---------- */
function emptyBoard() { return Array.from({length: SZ}, () => new Array(SZ).fill(0)); }
function neighbors(x, y) {
  const r = [];
  if (x > 0) r.push([x-1, y]); if (x < SZ-1) r.push([x+1, y]);
  if (y > 0) r.push([x, y-1]); if (y < SZ-1) r.push([x, y+1]);
  return r;
}
function groupAndLibs(bd, x, y) {
  const color = bd[y][x], stones = [], seen = new Set(), libs = new Set();
  const stack = [[x, y]];
  while (stack.length) {
    const [cx, cy] = stack.pop(), key = cx + "," + cy;
    if (seen.has(key)) continue;
    seen.add(key); stones.push([cx, cy]);
    for (const [nx, ny] of neighbors(cx, cy)) {
      if (bd[ny][nx] === 0) libs.add(nx + "," + ny);
      else if (bd[ny][nx] === color) stack.push([nx, ny]);
    }
  }
  return { stones, libs };
}
function playMove(bd, x, y, color) {
  bd[y][x] = color;
  const opp = 3 - color;
  for (const [nx, ny] of neighbors(x, y)) {
    if (bd[ny][nx] === opp) {
      const g = groupAndLibs(bd, nx, ny);
      if (g.libs.size === 0) for (const [sx, sy] of g.stones) bd[sy][sx] = 0;
    }
  }
  const self = groupAndLibs(bd, x, y);
  if (self.libs.size === 0) for (const [sx, sy] of self.stones) bd[sy][sx] = 0;
}
/* 각 수까지의 판 스냅샷 사전 계산 */
const boards = [emptyBoard()];
for (const s of DATA.initial) boards[0][s.y][s.x] = s.c === "b" ? 1 : 2;
for (const m of DATA.moves) {
  const bd = boards[boards.length - 1].map(r => r.slice());
  if (m.x !== null) playMove(bd, m.x, m.y, m.c === "b" ? 1 : 2);
  boards.push(bd);
}

/* ---------- 바둑판 SVG ---------- */
const CELL = 26, PAD = 30, BW = PAD * 2 + CELL * (SZ - 1);
const boardSvg = document.getElementById("board");
boardSvg.setAttribute("viewBox", `0 0 ${BW} ${BW}`);
boardSvg.setAttribute("width", Math.min(500, BW));
boardSvg.setAttribute("height", Math.min(500, BW));
function px(x) { return PAD + x * CELL; }
function py(y) { return PAD + (SZ - 1 - y) * CELL; }
let curTurn = 0;
let variation = null; /* {baseTurn, seq:[{x,y,c,n}], label} */
let trial = null;     /* {board, seq:[{x,y,c,n}], next, redo:[{x,y}]} 직접 놓아보기 */

function starPoints() {
  if (SZ !== 19) return [];
  const p = [3, 9, 15], out = [];
  for (const a of p) for (const b of p) out.push([a, b]);
  return out;
}
function renderBoard() {
  const bd = trial ? trial.board : (variation ? boards[variation.baseTurn] : boards[curTurn]);
  let s = `<rect x="0" y="0" width="${BW}" height="${BW}" rx="6" fill="var(--wood)"/>`;
  for (let i = 0; i < SZ; i++) {
    s += `<line x1="${px(0)}" y1="${py(i)}" x2="${px(SZ-1)}" y2="${py(i)}" stroke="var(--wood-line)" stroke-width="1"/>`;
    s += `<line x1="${px(i)}" y1="${py(0)}" x2="${px(i)}" y2="${py(SZ-1)}" stroke="var(--wood-line)" stroke-width="1"/>`;
  }
  for (const [x, y] of starPoints())
    s += `<circle cx="${px(x)}" cy="${py(y)}" r="2.6" fill="var(--wood-line)"/>`;
  for (let i = 0; i < SZ; i++) {
    s += `<text x="${px(i)}" y="${PAD - 14}" font-size="9.5" text-anchor="middle" fill="var(--wood-line)">${COLS[i]}</text>`;
    s += `<text x="${PAD - 16}" y="${py(i) + 3.5}" font-size="9.5" text-anchor="middle" fill="var(--wood-line)">${i + 1}</text>`;
  }
  const drawStone = (x, y, color, opts = {}) => {
    const fill = color === 1 ? "#1a1a1a" : "#f4f4f2";
    const stroke = color === 1 ? "#000" : "#b9b8b2";
    s += `<circle cx="${px(x)}" cy="${py(y)}" r="${CELL * 0.47}" fill="${fill}" stroke="${stroke}" stroke-width="0.8" ${opts.ghost ? 'opacity="0.92"' : ""}/>`;
    if (opts.num !== undefined) {
      const tc = color === 1 ? "#fff" : "#111";
      s += `<text x="${px(x)}" y="${py(y) + 3.8}" font-size="11" font-weight="700" text-anchor="middle" fill="${tc}">${opts.num}</text>`;
    }
  };
  for (let y = 0; y < SZ; y++) for (let x = 0; x < SZ; x++)
    if (bd[y][x]) drawStone(x, y, bd[y][x]);
  if (trial) {
    for (const v of trial.seq)
      if (bd[v.y][v.x] === v.c) drawStone(v.x, v.y, v.c, { num: v.n, ghost: true });
  } else if (variation) {
    for (const v of variation.seq) drawStone(v.x, v.y, v.c, { num: v.n, ghost: true });
  } else if (curTurn > 0) {
    const m = DATA.moves[curTurn - 1];
    if (m.x !== null) {
      const mc = m.c === "b" ? "#fff" : "#111";
      s += `<circle cx="${px(m.x)}" cy="${py(m.y)}" r="${CELL * 0.24}" fill="none" stroke="${mc}" stroke-width="1.8"/>`;
    }
  }
  boardSvg.innerHTML = s;
  const lab = document.getElementById("moveLabel");
  if (trial) lab.textContent = `시험 수 ${trial.seq.length}수 (${curTurn}수 장면부터)`;
  else if (variation) lab.textContent = `변화도 (${variation.baseTurn}수 장면)`;
  else {
    const m = curTurn > 0 ? DATA.moves[curTurn - 1] : null;
    lab.textContent = curTurn === 0 ? "개시 전" :
      `${curTurn}/${DATA.moves.length}수 ${m.c === "b" ? "흑" : "백"} ${m.gtp}`;
  }
  document.getElementById("slider").value = curTurn;
  renderMoveEval();
}
function renderMoveEval() {
  const el = document.getElementById("moveEval");
  if (trial) {
    el.innerHTML = `<span style="color:var(--ink2)">직접 놓아보는 중입니다. 궁금한 수순을 자유롭게 시험해 보세요. 따냄도 실제로 계산됩니다.</span>`;
    return;
  }
  if (variation) {
    el.innerHTML = `<span style="color:var(--ink2)">KataGo 추천 변화를 보는 중입니다. 수순 버튼을 누르면 실전으로 돌아갑니다.</span>`;
    return;
  }
  if (curTurn === 0) {
    el.innerHTML = `<span style="color:var(--ink2)">수를 넘기면 그 수에 대한 KataGo 평가가 여기 표시됩니다.</span>`;
    return;
  }
  const m = DATA.moveEvals[curTurn - 1];
  const wb = DATA.perTurn[curTurn - 1].winrate, wa = DATA.perTurn[curTurn].winrate;
  const who = m.color === "b" ? "흑" : "백";
  let loss;
  if (m.lossPts >= 0.5) loss = `${m.lossPts}집 손실`;
  else if (m.lossPts <= -0.5) loss = `${Math.abs(m.lossPts)}집 이득`;
  else loss = "손실 없음";
  let html = `<span class="gradeTag ${m.grade}">${m.grade}</span>
    <b> ${curTurn}수 ${who} ${m.gtp}</b>${m.region ? "(" + m.region + ")" : ""} · ${loss}
    · 흑 승률 ${(wb * 100).toFixed(0)}% → ${(wa * 100).toFixed(0)}%`;
  if (m.bestAlternative && m.bestAlternative !== m.gtp) {
    html += `<div class="rec">KataGo 추천: <b>${m.bestAlternative}</b>`;
    if (m.bestPv && m.bestPv.length > 1)
      html += `<button data-var="${curTurn}">추천 변화 재생</button>`;
    html += `</div>`;
  } else if (m.matchedBest) {
    html += `<div class="rec">KataGo 1순위와 일치합니다.</div>`;
  }
  el.innerHTML = html;
}
function goTurn(t, keepVar) {
  if (!keepVar) clearVariation();
  clearTrial();
  curTurn = Math.max(0, Math.min(DATA.moves.length, t));
  renderBoard(); renderChart();
}
function clearVariation() {
  variation = null;
  document.getElementById("varBanner").classList.remove("on");
}
/* ---------- 직접 놓아보기 (시험 수) ---------- */
function clearTrial() {
  trial = null;
  document.getElementById("trialBar").classList.remove("on");
  hideAi();
}
function hideAi() {
  const b = document.getElementById("aiAnswer");
  b.style.display = "none"; b.innerHTML = "";
}
function colorToMoveAt(t) {
  if (t < DATA.moves.length) return DATA.moves[t].c === "b" ? 1 : 2;
  if (t > 0) return DATA.moves[t - 1].c === "b" ? 2 : 1;
  return 1;
}
function updateTrialBar() {
  const bar = document.getElementById("trialBar");
  if (!trial) { bar.classList.remove("on"); return; }
  bar.classList.add("on");
  const nextKr = trial.next === 1 ? "흑" : "백";
  document.getElementById("trialLabel").textContent =
    `직접 놓는 중 (${trial.seq.length}수) · 다음 ${nextKr} 차례`;
  document.getElementById("trialUndo").disabled = !trial.seq.length;
  document.getElementById("trialRedo").disabled = !(trial.redo && trial.redo.length);
  document.getElementById("trialAsk").disabled = asking || !trial.seq.length;
}
boardSvg.addEventListener("click", ev => {
  if (variation) return; /* 변화도 위에는 두지 않음 */
  const rect = boardSvg.getBoundingClientRect();
  const sx = (ev.clientX - rect.left) * (BW / rect.width);
  const sy = (ev.clientY - rect.top) * (BW / rect.height);
  const x = Math.round((sx - PAD) / CELL);
  const yRow = Math.round((sy - PAD) / CELL);
  if (x < 0 || x >= SZ || yRow < 0 || yRow >= SZ) return;
  if (Math.abs(sx - px(x)) > CELL * 0.45 || Math.abs(sy - (PAD + yRow * CELL)) > CELL * 0.45) return;
  const y = SZ - 1 - yRow;
  if (!trial) trial = { board: boards[curTurn].map(r => r.slice()), seq: [], next: colorToMoveAt(curTurn), redo: [] };
  if (trial.board[y][x] !== 0) return;
  playMove(trial.board, x, y, trial.next);
  trial.seq.push({ x, y, c: trial.next, n: trial.seq.length + 1 });
  trial.next = 3 - trial.next;
  trial.redo = []; /* 새 수를 두면 그 지점부터의 되돌리기 기록은 무효 */
  hideAi();
  updateTrialBar(); renderBoard();
});
function rebuildTrial(seq, redo) {
  trial = { board: boards[curTurn].map(r => r.slice()), seq: [], next: colorToMoveAt(curTurn), redo: redo };
  for (const m of seq) {
    playMove(trial.board, m.x, m.y, trial.next);
    trial.seq.push({ x: m.x, y: m.y, c: trial.next, n: trial.seq.length + 1 });
    trial.next = 3 - trial.next;
  }
}
document.getElementById("trialUndo").onclick = () => {
  if (!trial || !trial.seq.length) return;
  const last = trial.seq[trial.seq.length - 1];
  /* 한 수만 무르고, 무른 수는 redo에 쌓아 "다시 진행"으로 복원할 수 있게 한다 */
  rebuildTrial(trial.seq.slice(0, -1), [{ x: last.x, y: last.y }].concat(trial.redo || []));
  updateTrialBar(); renderBoard();
};
document.getElementById("trialRedo").onclick = () => {
  if (!trial || !trial.redo || !trial.redo.length) return;
  const m = trial.redo.shift();
  if (trial.board[m.y][m.x] === 0) {
    playMove(trial.board, m.x, m.y, trial.next);
    trial.seq.push({ x: m.x, y: m.y, c: trial.next, n: trial.seq.length + 1 });
    trial.next = 3 - trial.next;
  }
  updateTrialBar(); renderBoard();
};
document.getElementById("trialClear").onclick = () => { clearTrial(); renderBoard(); };

/* ---------- 시험 수 변화도 AI 평가 ---------- */
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
document.getElementById("trialAsk").onclick = async () => {
  if (!trial || !trial.seq.length || asking) return;
  const base = boards[curTurn];
  const initial = [];
  for (let y = 0; y < SZ; y++)
    for (let x = 0; x < SZ; x++)
      if (base[y][x]) initial.push([base[y][x] === 1 ? "B" : "W", COLS[x] + (y + 1)]);
  const seq = trial.seq.map(m => ({ c: m.c === 1 ? "b" : "w", gtp: COLS[m.x] + (m.y + 1) }));
  const moves = seq.map(m => [m.c === "b" ? "B" : "W", m.gtp]);
  const box = document.getElementById("aiAnswer");
  box.style.display = "block";
  box.innerHTML = "KataGo가 이 변화를 검토하는 중입니다… (수순이 길수록 오래 걸립니다)";
  asking = true; updateTrialBar();
  try {
    const res = await fetch(ASK_URL, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ komi: DATA.meta.komi, initial, moves }) });
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
    const nextKr = trial && trial.next === 1 ? "흑" : "백";
    h += `<div style="color:var(--ink2)">이 다음 ${nextKr}부터의 KataGo 추천 진행: ${pv.join(" → ")}</div>`;
  }
  return h;
}
function showVariation(moveNum, pv, label) {
  const baseTurn = moveNum - 1;
  const toMove = DATA.moves[moveNum - 1].c === "b" ? 1 : 2;
  const seq = [];
  pv.forEach((v, i) => {
    const p = gtpToXY(v);
    if (p) seq.push({ x: p.x, y: p.y, c: i % 2 === 0 ? toMove : 3 - toMove, n: i + 1 });
  });
  variation = { baseTurn, seq };
  curTurn = baseTurn;
  const bn = document.getElementById("varBanner");
  bn.textContent = label;
  bn.classList.add("on");
  renderBoard(); renderChart();
  document.getElementById("board").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- 컨트롤 ---------- */
document.getElementById("slider").max = DATA.moves.length;
document.getElementById("btnStart").onclick = () => goTurn(0);
document.getElementById("btnPrev").onclick = () => goTurn(curTurn - 1);
document.getElementById("btnNext").onclick = () => goTurn(curTurn + 1);
document.getElementById("btnEnd").onclick = () => goTurn(DATA.moves.length);
document.getElementById("slider").oninput = e => goTurn(+e.target.value);
document.addEventListener("keydown", e => {
  if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
  if (trial) {
    /* 시험 수 놓는 중에는 방향키가 시험 수순을 한 수씩 무르고/다시 진행한다 */
    document.getElementById(e.key === "ArrowLeft" ? "trialUndo" : "trialRedo").click();
  } else {
    goTurn(curTurn + (e.key === "ArrowLeft" ? -1 : 1));
  }
  e.preventDefault();
});

/* ---------- 승률/집차이 차트 ---------- */
let metric = "winrate";
const gradeColor = { "호착": "var(--good)", "완착": "var(--warn)", "실수": "var(--serious)", "대악수": "var(--critical)" };
const chartSvg = document.getElementById("chart");
const tooltip = document.getElementById("tooltip");
const CH = { w: 0, h: 300, l: 44, r: 12, t: 14, b: 26 };
const goodSet = new Set(DATA.goodMoveNums || []);
const markers = DATA.moveEvals.filter(m =>
  (m.grade !== "호착" && gradeColor[m.grade]) || (m.grade === "호착" && goodSet.has(m.moveNum)));

function chartScales() {
  CH.w = chartSvg.clientWidth || 480;
  const n = DATA.perTurn.length - 1;
  const xs = t => CH.l + (CH.w - CH.l - CH.r) * (n === 0 ? 0 : t / n);
  let ymin, ymax;
  if (metric === "winrate") { ymin = 0; ymax = 1; }
  else {
    const vals = DATA.perTurn.map(p => p.scoreLead);
    const ext = Math.max(10, ...vals.map(Math.abs));
    ymin = -ext; ymax = ext;
  }
  const ys = v => CH.t + (CH.h - CH.t - CH.b) * (1 - (v - ymin) / (ymax - ymin));
  return { xs, ys, ymin, ymax, n };
}
function valAt(t) {
  const p = DATA.perTurn[t];
  return metric === "winrate" ? p.winrate : p.scoreLead;
}
function renderChart() {
  const { xs, ys, ymin, ymax, n } = chartScales();
  let s = "";
  const gridVals = metric === "winrate" ? [0, 0.25, 0.5, 0.75, 1] :
    [ymin, ymin / 2, 0, ymax / 2, ymax];
  for (const gv of gridVals) {
    const strong = (metric === "winrate" && gv === 0.5) || (metric === "score" && gv === 0);
    s += `<line x1="${CH.l}" y1="${ys(gv)}" x2="${CH.w - CH.r}" y2="${ys(gv)}" stroke="${strong ? "var(--axis)" : "var(--grid)"}" stroke-width="1"/>`;
    const label = metric === "winrate" ? Math.round(gv * 100) + "%" : (gv > 0 ? "+" : "") + Math.round(gv);
    s += `<text x="${CH.l - 6}" y="${ys(gv) + 3.5}" font-size="10.5" text-anchor="end" fill="var(--muted)">${label}</text>`;
  }
  for (let t = 0; t <= n; t += (n > 150 ? 50 : 25)) {
    if (t === 0) continue;
    s += `<text x="${xs(t)}" y="${CH.h - 8}" font-size="10.5" text-anchor="middle" fill="var(--muted)">${t}수</text>`;
  }
  const pts = DATA.perTurn.map(p => `${xs(p.turn)},${ys(valAt(p.turn))}`).join(" ");
  const lineColor = metric === "winrate" ? "var(--line)" : "var(--line2)";
  s += `<polyline points="${pts}" fill="none" stroke="${lineColor}" stroke-width="2" stroke-linejoin="round"/>`;
  for (const m of markers) {
    s += `<circle class="mk" data-move="${m.moveNum}" cx="${xs(m.moveNum)}" cy="${ys(valAt(m.moveNum))}" r="5"
      fill="${gradeColor[m.grade]}" stroke="var(--surface)" stroke-width="2" style="cursor:pointer"/>`;
  }
  if (!variation && curTurn > 0) {
    s += `<line x1="${xs(curTurn)}" y1="${CH.t}" x2="${xs(curTurn)}" y2="${CH.h - CH.b}" stroke="var(--ink2)" stroke-width="1" stroke-dasharray="3 3" opacity="0.7"/>`;
  }
  s += `<rect id="hoverPane" x="${CH.l}" y="${CH.t}" width="${CH.w - CH.l - CH.r}" height="${CH.h - CH.t - CH.b}" fill="transparent"/>`;
  chartSvg.setAttribute("viewBox", `0 0 ${CH.w} ${CH.h}`);
  chartSvg.innerHTML = s;

  chartSvg.querySelectorAll(".mk").forEach(el => {
    el.addEventListener("click", () => goTurn(+el.dataset.move));
    el.addEventListener("mousemove", ev => showTip(ev, +el.dataset.move));
    el.addEventListener("mouseleave", hideTip);
  });
  const pane = chartSvg.querySelector("#hoverPane");
  pane.addEventListener("mousemove", ev => {
    const rect = chartSvg.getBoundingClientRect();
    const relX = (ev.clientX - rect.left) * (CH.w / rect.width);
    const t = Math.round((relX - CH.l) / (CH.w - CH.l - CH.r) * n);
    if (t >= 0 && t <= n) showTip(ev, t);
  });
  pane.addEventListener("mouseleave", hideTip);
  pane.addEventListener("click", ev => {
    const rect = chartSvg.getBoundingClientRect();
    const relX = (ev.clientX - rect.left) * (CH.w / rect.width);
    goTurn(Math.round((relX - CH.l) / (CH.w - CH.l - CH.r) * n));
  });
}
function showTip(ev, t) {
  const p = DATA.perTurn[t];
  const m = t > 0 ? DATA.moves[t - 1] : null;
  const ev2 = DATA.moveEvals[t - 1];
  let html = `<b>${t}수</b>`;
  if (m) html += ` ${m.c === "b" ? "흑" : "백"} ${m.gtp}`;
  html += `<br>흑 승률 ${(p.winrate * 100).toFixed(1)}% · 집차이 ${p.scoreLead > 0 ? "+" : ""}${p.scoreLead}`;
  if (ev2 && gradeColor[ev2.grade]) html += `<br>${ev2.grade} (${ev2.lossPts > 0 ? "-" : "+"}${Math.abs(ev2.lossPts)}집)`;
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  const box = document.getElementById("chartBox").getBoundingClientRect();
  let tx = ev.clientX - box.left + 14, ty = ev.clientY - box.top - 10;
  if (tx > box.width - 170) tx -= 190;
  tooltip.style.left = tx + "px"; tooltip.style.top = ty + "px";
}
function hideTip() { tooltip.style.display = "none"; }
document.querySelectorAll(".chip").forEach(c => c.onclick = () => {
  document.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
  c.classList.add("on"); metric = c.dataset.metric; renderChart();
});
window.addEventListener("resize", renderChart);

/* ---------- 해설 섹션 ---------- */
const R = DATA.review || {};
const evByNum = {}; DATA.moveEvals.forEach(m => evByNum[m.moveNum] = m);
function moveTag(n) {
  const m = evByNum[n];
  if (!m) return `${n}수`;
  return `${n}수 ${m.color === "b" ? "흑" : "백"} ${m.gtp}${m.region ? "(" + m.region + ")" : ""}`;
}
document.getElementById("oneliner").textContent = R.oneLiner || "";
document.getElementById("overall").textContent = R.overall || "";
if (!R.oneLiner) document.getElementById("oneliner").style.display = "none";
if (!R.overall) document.getElementById("overall").parentElement.style.display = "none";
const secs = [["secStory", R.story], ["secTp", R.turningPoints], ["secGood", R.goodMoves],
              ["secBad", R.badMoves], ["secLessons", R.lessons],
              ["secStrengths", R.strengths], ["secWeak", R.weaknesses]];
for (const [id, arr] of secs)
  if (!arr || !arr.length) document.getElementById(id).style.display = "none";

const sg = document.getElementById("storyGrid");
(R.story || []).forEach(st => {
  const d = document.createElement("div");
  d.className = "card story";
  d.innerHTML = `<h3>${st.phase} · ${st.title}<span class="range">${st.range || ""}수</span></h3>
    <div style="font-size:14px;color:var(--ink2)">${st.text}</div>`;
  sg.appendChild(d);
});

const tpl = document.getElementById("tpList");
(R.turningPoints || []).forEach(tp => {
  const m = evByNum[tp.moveNum] || {};
  const d = document.createElement("div");
  d.className = "card tp";
  let html = `<h3>${moveTag(tp.moveNum)} · ${tp.title}</h3>
    <div style="font-size:14px;color:var(--ink2)">${tp.text}</div>`;
  if (tp.variationComment && m.bestPv && m.bestPv.length) {
    html += `<div class="var"><b>KataGo 추천 변화</b> (${m.bestAlternative}부터): ${tp.variationComment}</div>`;
  }
  html += `<div class="btns"><button data-jump="${tp.moveNum}">이 장면 보기</button>`;
  if (m.bestPv && m.bestPv.length)
    html += `<button data-var="${tp.moveNum}">변화도 재생</button>`;
  html += `</div>`;
  d.innerHTML = html;
  tpl.appendChild(d);
});

function fillMoves(elId, arr, isBad) {
  const el = document.getElementById(elId);
  (arr || []).forEach(g => {
    const m = evByNum[g.moveNum] || {};
    const d = document.createElement("div");
    d.className = "mv";
    let txt = g.comment || "";
    if (isBad && g.better) txt += ` <b>대안:</b> ${g.better}`;
    d.innerHTML = `<span class="badge ${m.grade || (isBad ? "실수" : "호착")}">${m.grade || ""}</span>
      <span class="who">${moveTag(g.moveNum)}</span>
      <span class="txt">${txt}</span>
      <button data-jump="${g.moveNum}">보기</button>`;
    el.appendChild(d);
  });
}
fillMoves("goodList", R.goodMoves, false);
fillMoves("badList", R.badMoves, true);

const ll = document.getElementById("lessonList");
(R.lessons || []).forEach(t => {
  const li = document.createElement("li"); li.textContent = t; ll.appendChild(li);
});
const sl = document.getElementById("strengthList");
(R.strengths || []).forEach(t => {
  const li = document.createElement("li"); li.textContent = t; sl.appendChild(li);
});
const wl = document.getElementById("weakList");
(R.weaknesses || []).forEach(w => {
  const d = document.createElement("div"); d.style.margin = "8px 0";
  const h = document.createElement("div"); h.style.fontWeight = "600"; h.textContent = w.pattern || "";
  const e = document.createElement("div"); e.style.color = "var(--ink2)"; e.textContent = w.evidence || "";
  const f = document.createElement("div"); f.style.color = "var(--muted)"; f.textContent = w.fix ? "보완: " + w.fix : "";
  d.append(h, e, f); wl.appendChild(d);
});

document.body.addEventListener("click", e => {
  const j = e.target.closest("[data-jump]");
  if (j) { goTurn(+j.dataset.jump); document.getElementById("board").scrollIntoView({ behavior: "smooth", block: "nearest" }); }
  const v = e.target.closest("[data-var]");
  if (v) {
    const n = +v.dataset.var, m = evByNum[n];
    showVariation(n, m.bestPv, `${n}수 장면에서 KataGo 추천 진행: ${m.bestPv.join(" ")} (실전으로 돌아가려면 수순 버튼을 누르세요)`);
  }
});

/* ---------- 원자료 표 ---------- */
const tbl = document.getElementById("rawTable");
tbl.innerHTML = `<tr><th>수</th><th>색</th><th>좌표</th><th>등급</th><th>손실(집)</th><th>승률 변화</th><th>이후 흑 승률</th><th>KataGo 추천</th></tr>` +
  DATA.moveEvals.map(m =>
    `<tr><td>${m.moveNum}</td><td>${m.color === "b" ? "흑" : "백"}</td><td>${m.gtp}</td>
     <td><span class="gradeTag ${m.grade}">${m.grade}</span></td>
     <td>${m.lossPts}</td><td>${(m.lossWr * 100).toFixed(1)}%p</td><td>${(m.winrateAfter * 100).toFixed(0)}%</td><td>${m.bestAlternative || ""}</td></tr>`).join("");

goTurn(0);
</script>
</body>
</html>
"""


def render(analysis, review, initial, moves, out_path, game_name=""):
    meta = analysis["meta"]
    ev = analysis["moveEvals"]
    data = {
        "meta": meta,
        "initial": [{"c": s["color"], "x": s["col"], "y": s["row"]} for s in initial],
        "moves": [
            {"c": color, "x": mv[1] if mv else None, "y": mv[0] if mv else None,
             "gtp": ev[i]["gtp"]}
            for i, (color, mv) in enumerate(moves)
        ],
        "perTurn": analysis["perTurn"],
        "moveEvals": ev,
        "goodMoveNums": analysis["goodMoves"],
        "review": review,
    }
    result = meta["result"] or "미완성 대국 (도중 종료)"
    generic = meta["black"] in ("흑", "") and meta["white"] in ("백", "")
    header = game_name if (generic and game_name) else f"{meta['black']} (흑) vs {meta['white']} (백)"
    title = f"복기: {header} {meta['date']}"
    sub = (f"{meta['date']} · 덤 {meta['komi']} · {analysis['nMoves']}수 · {result} · "
           f"KataGo {analysis['visits']} visits")
    footer = (f"KataGo kata1-b18c384nbt ({analysis['visits']} visits) + Claude 해설 · "
              f"생성 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    html = (TEMPLATE
            .replace("__TITLE__", title)
            .replace("__HEADER__", header)
            .replace("__SUBHEADER__", sub)
            .replace("__FOOTER__", footer)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    Path(out_path).write_text(html, encoding="utf-8")
