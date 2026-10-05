#!/usr/bin/env python3
"""reviews/ 아래 분석 완료된 대국들을 종합해 훈련용 통합 리포트를 만든다.

승호(사용자) 색 판별: 리뷰 폴더명의 "(승호 백)" / "(승호 흑)" 표기.
표기가 없는 대국은 종합 통계·문제집에서 제외하고 리포트에 그 사실을 명시한다.

사용법: ./venv/bin/python overall.py [--model claude-sonnet-5] [--no-llm] [--no-open]
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import analysis as A
from lib import lifedeath
from lib import llm
from lib import overall_render

ROOT = Path(__file__).resolve().parent
DEEP_VISITS = 1500  # 훈련 문제 장면 심층 재분석 visits (0이면 생략)
SPARRING_KEYWORDS = ("대비대국", "소소회", "스파링", "연습대국", "타이젬", "연습")


def game_kind(name):
    """폴더명(대회명)으로 공식 대국과 스파링을 나눈다. 프로 피드백: 스파링은 집중도가 달라 따로 봐야 한다."""
    return "스파링" if any(k in name for k in SPARRING_KEYWORDS) else "공식"


def pick_fight_move(cands, mover, wr_before, max_wr_drop=0.06, min_stdev_gain=1.0):
    """불리한 쪽(착수자 승률 40% 미만)에게, 최선수 대신 변화 폭(scoreStdev)이 큰 '승부수 후보'를 고른다.
    조건: 최선수 대비 착수자 승률 손실 max_wr_drop 이하, scoreStdev가 최선수보다 min_stdev_gain 이상 큼.
    프로 피드백(2026-09-17): 져 있을 때 인공은 조금 지는 길을 말하지만 사람은 껄끄럽게 두어야 한다."""
    if not cands or cands[0].get("scoreStdev") is None:
        return None
    mover_wr = wr_before if mover == "b" else 1 - wr_before
    if mover_wr >= 0.40:
        return None
    best = cands[0]
    def mwr(c):
        return c["winrate"] if mover == "b" else 1 - c["winrate"]
    pool = [c for c in cands[1:] if c.get("scoreStdev") is not None
            and mwr(best) - mwr(c) <= max_wr_drop
            and c["scoreStdev"] - best["scoreStdev"] >= min_stdev_gain]
    if not pool:
        return None
    c = max(pool, key=lambda c: c["scoreStdev"])
    return {"move": c["move"], "pv": c["pv"][:12], "stdev": round(c["scoreStdev"], 1),
            "bestStdev": round(best["scoreStdev"], 1), "wrDrop": round((mwr(best) - mwr(c)) * 100, 1)}
SGF_DIR = ROOT.parent / "baduk"


def find_games(player="승호", reviews_dir=None, sgf_dir=None):
    games, skipped = [], []
    reviews_dir = reviews_dir or (ROOT / "reviews")
    sgf_dir = sgf_dir or SGF_DIR
    for d in sorted(reviews_dir.iterdir()):
        if not (d / "analysis.json").exists():
            continue
        m = re.search(rf"\({re.escape(player)} (백|흑)", d.name)
        if not m:
            skipped.append(d.name)
            continue
        sgf = sgf_dir / (d.name + ".sgf")
        if not sgf.exists():
            skipped.append(d.name + " (SGF 없음)")
            continue
        games.append({
            "dir": d, "name": d.name,
            "myColor": "b" if m.group(1) == "흑" else "w",
            "sgf": sgf,
        })
    return games, skipped


def phase_of(move_num, n_moves):
    third = n_moves / 3
    return "초반" if move_num <= third else ("중반" if move_num <= 2 * third else "종반")


def gtp_dist(a, b):
    ra = A.gtp_to_rc(a) if a else None
    rb = A.gtp_to_rc(b) if b else None
    if ra is None or rb is None:
        return None
    return max(abs(ra[0] - rb[0]), abs(ra[1] - rb[1]))


def collect(games):
    """게임별 요약 + 종합 집계 + 훈련 문제 추출.

    손실 집계는 '경합 국면'(착수 직전 흑 승률 10~90%)만 대상으로 한다.
    승부가 이미 기운 국면의 손실과 쌍방 실수의 이중 집계 왜곡을 줄이기 위함이다.
    실수 유형은 최선수와 실전수의 거리로 나눈다: 5칸 이상이면 '대세점 놓침'(다른 곳이
    급했는데 국지전을 따라간 것), 미만이면 '국지 수읽기'.
    """
    per_game, problems = [], []
    agg_grade, agg_phase, agg_type = Counter(), Counter(), Counter()

    for g in games:
        a = json.loads((g["dir"] / "analysis.json").read_text())
        review = {}
        rp = g["dir"] / "review.json"
        if rp.exists():
            review = json.loads(rp.read_text())
        meta, initial, moves = A.parse_sgf(g["sgf"])
        snapshots = A.replay_boards(meta, initial, moves)
        wr = {p["turn"]: p["winrate"] for p in a["perTurn"]}
        mine = [m for m in a["moveEvals"] if m["color"] == g["myColor"]]
        bad = [m for m in mine if m["grade"] in ("대악수", "실수", "완착")]
        comp_bad = [m for m in bad if 0.10 <= wr[m["moveNum"] - 1] <= 0.90]

        for m in mine:
            agg_grade[m["grade"]] += 1
        for m in comp_bad:
            agg_phase[phase_of(m["moveNum"], a["nMoves"])] += m["lossPts"]
            d = gtp_dist(m["gtp"], m["bestAlternative"])
            mtype = "대세점 놓침 (다른 곳이 급했음)" if d is not None and d >= 5 \
                else "국지 수읽기 오류"
            agg_type[mtype] += m["lossPts"]

        n_serious = sum(1 for m in comp_bad if m["grade"] in ("대악수", "실수"))
        per_game.append({
            "name": g["name"],
            "report": str(g["dir"] / "report.html"),
            "date": a["meta"]["date"],
            "result": a["meta"]["result"] or "미완성 대국",
            "myColor": g["myColor"],
            "kind": game_kind(g["name"]),
            "won": (a["meta"]["result"] or "").upper().startswith("B+" if g["myColor"] == "b" else "W+"),
            "nMoves": a["nMoves"],
            "nBad": len(comp_bad),
            "totalLoss": round(sum(m["lossPts"] for m in comp_bad), 1),
            "per100": round(n_serious / max(1, len(mine)) * 100, 1),
            "oneLiner": (review.get("oneLiner") or ""),
            "lessons": review.get("lessons", []),
            "strengths": review.get("strengths", []),
            "weaknesses": review.get("weaknesses", []),
        })

        # 훈련 문제: 손실 3집 이상(실수·대악수급) 상위 6개
        cands = a.get("candidatesByTurn", {})
        rev_by_num = {b.get("moveNum"): b for b in review.get("badMoves", [])}
        chosen = [m for m in sorted(comp_bad, key=lambda x: -x["lossPts"])[:6]
                  if m["lossPts"] >= 3 and m["gtp"] != "pass"]
        # 문제로 낼 장면만 더 깊게 다시 분석해 최선수·변화도·후보를 갱신한다 (참고도 품질 보강).
        if chosen and DEEP_VISITS > 0:
            try:
                deep = A.run_katago(meta, initial, moves, DEEP_VISITS,
                                    analyze_turns=sorted({m["moveNum"] - 1 for m in chosen}))
                for m in chosen:
                    r = deep.get(m["moveNum"] - 1)
                    if not r or not r.get("moveInfos"):
                        continue
                    mis = r["moveInfos"]
                    m["bestAlternative"] = mis[0]["move"]
                    m["bestPv"] = mis[0]["pv"][:12]
                    cands[str(m["moveNum"] - 1)] = [
                        {"move": mi["move"], "winrate": mi["winrate"], "scoreLead": mi["scoreLead"],
                         "visits": mi["visits"], "scoreStdev": mi.get("scoreStdev"),
                         "pv": mi["pv"][:12]} for mi in mis[:5]]
                    m["deepVisits"] = DEEP_VISITS
            except Exception as e:
                print(f"      심층 재분석 실패 ({g['name']}): {e}")
        for m in chosen:
            turn = m["moveNum"] - 1
            played_pv = []
            for c in cands.get(str(turn), []):
                if c["move"] == m["gtp"]:
                    played_pv = c["pv"][:10]
            rb = rev_by_num.get(m["moveNum"], {})
            problems.append({
                "game": g["name"],
                "moveNum": m["moveNum"],
                "toMove": g["myColor"],
                "grid": snapshots[turn],
                "played": m["gtp"],
                "lossPts": m["lossPts"],
                "best": m["bestAlternative"],
                "bestPv": m["bestPv"],
                "playedPv": played_pv,
                "shape": m.get("shape", ""),
                "reviewComment": rb.get("comment", ""),
                "reviewBetter": rb.get("better", ""),
                "region": m["region"],
                "kind": game_kind(g["name"]),
                "fightMove": pick_fight_move(cands.get(str(turn), []), m["color"], wr[turn]),
                "candidates": [
                    {"move": c["move"], "scoreLead": round(c["scoreLead"], 1)}
                    for c in cands.get(str(turn), [])[:5]
                ],
            })

    problems.sort(key=lambda p: -p["lossPts"])
    record = {}
    for pg in per_game:
        r = record.setdefault(pg["kind"], {"games": 0, "wins": 0, "b": [0, 0], "w": [0, 0]})
        r["games"] += 1
        r["wins"] += int(pg["won"])
        r[pg["myColor"]][0] += 1
        r[pg["myColor"]][1] += int(pg["won"])
    return per_game, problems, {
        "record": record,
        "grade": dict(agg_grade),
        "phase": {k: round(v, 1) for k, v in agg_phase.items()},
        "mtype": {k: round(v, 1) for k, v in agg_type.most_common()},
    }


def build_judgment_problems(games, visits=200):
    """형세판단 훈련: 각 대국의 중반 이후 장면 + KataGo scoreLead + ownership"""
    out = []
    for g in games:
        a = json.loads((g["dir"] / "analysis.json").read_text())
        n = a["nMoves"]
        fracs = [0.35, 0.55, 0.75, 0.9] if n >= 60 else [0.6, 0.9]
        turns = sorted({max(20, int(n * f)) for f in fracs if int(n * f) <= n})
        if not turns:
            continue
        meta, initial, moves = A.parse_sgf(g["sgf"])
        snapshots = A.replay_boards(meta, initial, moves)
        print(f"      {g['name']}: 형세 장면 {len(turns)}개 ownership 쿼리...")
        resp = A.run_katago(meta, initial, moves, visits, analyze_turns=turns)
        per_turn = {p["turn"]: p for p in a["perTurn"]}
        for t in turns:
            r = resp.get(t)
            if not r or "ownership" not in r:
                continue
            out.append({
                "game": g["name"],
                "turn": t,
                "nMoves": n,
                "grid": snapshots[t],
                "scoreLead": per_turn[t]["scoreLead"],
                "winrate": per_turn[t]["winrate"],
                "ownership": [round(v, 2) for v in r["ownership"]],
            })
    return out


SYNTH_SCHEMA = """{
  "oneLiner": "승호 님 바둑을 한 문장으로",
  "overall": "종합 진단 6~9문장. 기력의 현재 위치, 강점과 약점의 구조, 무엇부터 고치면 승률이 가장 빨리 오를지.",
  "strengths": ["유지해야 할 강점 3~4개, 근거 포함"],
  "weaknesses": [
    {"pattern": "반복 패턴 이름", "evidence": "어느 판 몇 수 등 구체 근거", "fix": "교정 방법 1~2문장"}
  ],
  "practicePlan": [
    {"focus": "연습 주제", "how": "구체적으로 무엇을 어떻게", "cadence": "주 몇 회, 회당 몇 분"}
  ],
  "checklist": ["대국 중 착수 전에 자문할 체크리스트 3~5개, 짧은 명령형"]
}"""


EXPLAIN_SCHEMA = """[
  {"id": 0, "why": "최선수가 왜 좋은지와 실전 수가 왜 손해인지 2~3문장",
   "variation": "최선 변화(PV) 진행이 어떻게 흘러가는지 1~2문장"}
]"""


def explain_problems(problems, model, chunk=30):
    if len(problems) > chunk:
        for i in range(0, len(problems), chunk):
            _explain_chunk(problems[i:i + chunk], model)
        return problems
    return _explain_chunk(problems, model)


def _explain_chunk(problems, model):
    lines = []
    for i, p in enumerate(problems):
        color = "흑" if p["toMove"] == "b" else "백"
        lines.append(f"[{i}] {p['game']} {p['moveNum']}수 장면, {color} 차례 ({p['region']})")
        if p["shape"]:
            lines.append(f"  실전 수 {p['played']}의 형태 사실: {p['shape']}")
        lines.append(f"  실전 수 {p['played']}: {p['lossPts']}집 손실")
        lines.append(f"  최선 {p['best']}, 변화(PV): {' '.join(p['bestPv'])}")
        if p["playedPv"]:
            lines.append(f"  실전 수의 예상 진행: {' '.join(p['playedPv'])}")
        if p["reviewComment"]:
            lines.append(f"  복기 해설: {p['reviewComment']} / 대안: {p['reviewBetter']}")
    prompt = f"""당신은 프로 바둑 사범입니다. 훈련 문제집의 각 장면에 대해, 학생이 정답을 외우는 것이 아니라 이유를 이해하도록 해설을 써 주세요.

{chr(10).join(lines)}

## 작성 규칙
- 출력은 아래 스키마의 순수 JSON 배열 하나만. 모든 id(0~{len(problems) - 1})를 포함할 것.
- why는 "형태 사실"과 제공된 데이터만 근거로 쓸 것. 형태 사실에 없는 전술 행위(끊음, 살림 등)를 단정하지 말 것.
- variation은 반드시 제공된 PV 수순을 근거로, 그 진행의 목적을 설명할 것.
- 문장 어디에도 엠대쉬(—) 금지. 존댓말.

## 출력 JSON 스키마
{EXPLAIN_SCHEMA}"""
    arr = llm.call_claude(prompt, model=model)
    if isinstance(arr, dict):  # 모델이 객체로 감싼 경우
        arr = next(iter(arr.values()))
    by_id = {e["id"]: e for e in arr}
    for i, p in enumerate(problems):
        e = by_id.get(i, {})
        p["why"] = e.get("why", "")
        p["variation"] = e.get("variation", "")
    return problems


def synthesize(per_game, agg, model, player="승호", level="amateur"):
    lines = []
    for pg in per_game:
        color = "흑" if pg["myColor"] == "b" else "백"
        lines.append(f"### {pg['name']} [{pg.get('kind', '공식')}] ({color}, {pg['result']}, {pg['nMoves']}수)")
        lines.append(f"- 한 줄 요약: {pg['oneLiner']}")
        lines.append(f"- 문제 수 {pg['nBad']}개, 총 손실 {pg['totalLoss']}집")
        for l in pg["lessons"]:
            lines.append(f"- 교훈: {l}")
        for st in pg.get("strengths", []):
            lines.append(f"- 강점: {st}")
        for w in pg.get("weaknesses", []):
            if isinstance(w, dict):
                lines.append(f"- 약점: {w.get('pattern', '')} / 근거: {w.get('evidence', '')} / 보완: {w.get('fix', '')}")
    if level == "pro":
        intro = (f"당신은 프로 바둑 도장의 수석 사범입니다. 프로 기사 {player} 님의 최근 공식 대국 여러 판을 복기한 결과가 아래에 있습니다. "
                 "상대도 모두 프로이므로 기초 원칙이 아니라, 프로 승률을 실제로 가르는 구조적 약점(형세판단 오차, 수읽기 누락 유형, "
                 "방향 선택, 시간 배분, 끝내기 정밀도)을 진단하고 다음 대국에 바로 적용할 훈련 계획을 만들어 주세요.")
    else:
        intro = f"당신은 프로 바둑 사범입니다. 한 학생({player} 님)의 최근 대국 여러 판을 복기한 결과가 아래에 있습니다. 이를 종합해 학생의 기풍 진단과 훈련 계획을 만들어 주세요."
    prompt = f"""{intro}

## 판별 복기 요약
{chr(10).join(lines)}

## 종합 통계 (학생 수만, 승률 10~90% 경합 국면 한정 집계)
- 등급 분포(전체): {json.dumps(agg['grade'], ensure_ascii=False)}
- 단계별 경합 손실(집): {json.dumps(agg['phase'], ensure_ascii=False)}
- 실수 유형별 경합 손실(집): {json.dumps(agg['mtype'], ensure_ascii=False)}

## 작성 규칙
- 출력은 아래 스키마의 순수 JSON 하나만. 코드펜스 금지.
- 판별 교훈을 단순 반복하지 말고, 판을 관통하는 구조적 패턴으로 묶어서 진단할 것.
- 대국명 뒤의 [공식]/[스파링] 구분을 반영할 것. 스파링은 집중도가 달라 참고로만 쓰고, 진단과 훈련 계획의 근거는 공식 대국 위주로 삼을 것. 두 구분에서 패턴이 다르면 그 차이도 짚을 것.
- 문장에서 좌표(Q16 같은 표기)를 쓰지 말고 "3국 128수"처럼 대국과 수 번호로 지칭할 것. 안정도 퍼센트나 활로 개수 같은 수치는 쓰지 말 것.
- practicePlan은 3~5개, 실행 가능한 수준으로 구체적으로.
- 문장 어디에도 엠대쉬(—) 금지. 존댓말, 학생은 "님"으로.

## 출력 JSON 스키마
{SYNTH_SCHEMA.replace("승호", player)}"""
    return llm.call_claude(prompt, model=model)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=llm.DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--render-only", action="store_true",
                    help="캐시된 데이터로 HTML만 다시 그림 (KataGo·Claude 호출 없음)")
    ap.add_argument("--player", default="승호", help="집계 대상 선수 (폴더명의 '(선수 백|흑)' 표기)")
    ap.add_argument("--level", choices=["amateur", "pro"], default="amateur")
    ap.add_argument("--reviews-dir", default=None, help="리뷰 폴더 (기본 reviews/)")
    ap.add_argument("--sgf-dir", default=None, help="SGF 폴더 (기본 ../baduk/)")
    args = ap.parse_args()

    reviews_dir = Path(args.reviews_dir).expanduser() if args.reviews_dir else ROOT / "reviews"
    sgf_dir = Path(args.sgf_dir).expanduser() if args.sgf_dir else SGF_DIR
    cache_path = reviews_dir / "_종합캐시.json"
    out = reviews_dir / ("종합 리포트.html" if args.player == "승호" else f"종합 리포트 ({args.player}).html")

    if args.render_only:
        if not cache_path.exists():
            sys.exit("캐시가 없습니다. 먼저 전체 실행을 한 번 하세요.")
        c = json.loads(cache_path.read_text())
        overall_render.render(c["per_game"], c["problems"], c["agg"], c["synthesis"],
                              c["skipped"], out, judgments=c["judgments"],
                              ld_problems=c["ld_problems"])
        print(f"완료 (렌더만): {out}")
        if not args.no_open:
            subprocess.run(["open", str(out)])
        return

    games, skipped = find_games(args.player, reviews_dir, sgf_dir)
    if not games:
        sys.exit(f"({args.player} 백/흑) 표기가 있는 분석 완료 대국이 없습니다.")
    print(f"[1/3] 대국 수집: {len(games)}판 포함, {len(skipped)}건 제외 {skipped}")

    per_game, problems, agg = collect(games)
    print(f"[2/3] 집계 완료: 훈련 문제 {len(problems)}개 추출")

    print("      형세판단 문제 생성 (KataGo ownership)...")
    judgments = build_judgment_problems(games)
    print(f"      형세판단 장면 {len(judgments)}개")

    print("      사활 장면 검출 (ownership 반전 탐지)...")
    ld_problems = lifedeath.find_problems(games, competitive=(args.level == "pro"))
    print(f"      사활 문제 {len(ld_problems)}개")

    synthesis = None
    if not args.no_llm:
        print(f"      Claude 문제 해설 생성 (모델 {args.model})...")
        try:
            explain_problems(problems + ld_problems, args.model)
        except Exception as e:
            print(f"      문제 해설 실패 (해설 없이 진행): {e}")
        print(f"      Claude 종합 진단 생성 (모델 {args.model})...")
        try:
            synthesis = synthesize(per_game, agg, args.model, player=args.player, level=args.level)
        except Exception as e:
            print(f"      진단 실패 (통계·문제집만 생성): {e}")

    cache_path.write_text(json.dumps({
        "per_game": per_game, "problems": problems, "agg": agg,
        "synthesis": synthesis, "skipped": skipped,
        "judgments": judgments, "ld_problems": ld_problems,
    }, ensure_ascii=False), encoding="utf-8")
    overall_render.render(per_game, problems, agg, synthesis, skipped, out,
                          judgments=judgments, ld_problems=ld_problems)
    print(f"[3/3] 완료: {out}")
    if not args.no_open:
        subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
