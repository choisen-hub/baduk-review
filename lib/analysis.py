"""SGF 파싱 + KataGo analysis engine 구동 + 수 분류.

좌표계 정리:
- sgfmill: (row, col), row 0 = 맨 아랫줄
- GTP/KataGo: "Q16" 스타일, 열 문자는 I 생략, 행 번호 1 = 맨 아랫줄
- 승률/집차이는 analysis.cfg 의 reportAnalysisWinratesAs = BLACK 에 따라 항상 흑 기준
"""
import json
import subprocess
import sys
from pathlib import Path

from sgfmill import sgf, sgf_moves

GTP_COLS = "ABCDEFGHJKLMNOPQRST"  # I 없음

KATAGO_MODEL = "/opt/homebrew/share/katago/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz"
ANALYSIS_CFG = str(Path(__file__).resolve().parent.parent / "analysis.cfg")


def rc_to_gtp(row, col):
    return f"{GTP_COLS[col]}{row + 1}"


def gtp_to_rc(vertex):
    if vertex.lower() == "pass":
        return None
    col = GTP_COLS.index(vertex[0].upper())
    row = int(vertex[1:]) - 1
    return row, col


def region_name(row, col, size=19):
    """한국 바둑 해설 관례의 지역 이름. row 큰 쪽이 상변."""
    third = (size - 1) / 3.0
    x = 0 if col < third else (2 if col > 2 * third else 1)
    y = 0 if row < third else (2 if row > 2 * third else 1)
    names = {
        (0, 2): "좌상귀", (1, 2): "상변", (2, 2): "우상귀",
        (0, 1): "좌변", (1, 1): "중앙", (2, 1): "우변",
        (0, 0): "좌하귀", (1, 0): "하변", (2, 0): "우하귀",
    }
    return names[(x, y)]


def parse_sgf(path):
    """SGF 본선(main line)만 읽는다. 반환: 메타 dict, 초기돌, 수순 [(color, (row,col) or None)]"""
    with open(path, "rb") as f:
        game = sgf.Sgf_game.from_bytes(f.read())
    board, moves = sgf_moves.get_setup_and_moves(game)
    root = game.get_root()

    def prop(p, default=""):
        try:
            return root.get(p)
        except (KeyError, ValueError):
            return default

    meta = {
        "size": game.get_size(),
        "komi": game.get_komi() if game.get_komi() is not None else 6.5,
        "black": prop("PB", "흑"),
        "white": prop("PW", "백"),
        "result": prop("RE", ""),
        "date": prop("DT", ""),
        "event": prop("EV", ""),
        "handicap": (prop("HA", 0) if isinstance(prop("HA", 0), int) else 0) or 0,
    }
    initial = []  # 접바둑 배석
    for r in range(meta["size"]):
        for c in range(meta["size"]):
            colour = board.get(r, c)
            if colour is not None:
                initial.append({"color": colour, "row": r, "col": c})
    return meta, initial, moves


def run_katago(meta, initial, moves, visits, progress=lambda done, total: None,
               analyze_turns=None, include_ownership=True):
    """수순을 analysis engine 한 쿼리로 분석. analyze_turns 미지정 시 전 턴.
    반환: analyze_turns 미지정이면 턴 순서 리스트, 지정이면 {turn: resp} dict."""
    size = meta["size"]
    turns_wanted = analyze_turns if analyze_turns is not None else list(range(len(moves) + 1))
    query = {
        "id": "review",
        "rules": "korean",
        "komi": meta["komi"],
        "boardXSize": size,
        "boardYSize": size,
        "initialStones": [[s["color"].upper(), rc_to_gtp(s["row"], s["col"])] for s in initial],
        "moves": [[color.upper(), "pass" if mv is None else rc_to_gtp(*mv)] for color, mv in moves],
        "analyzeTurns": sorted(set(turns_wanted)),
        "maxVisits": visits,
        "includePolicy": False,
        "includeOwnership": include_ownership,
    }
    n_turns = len(set(turns_wanted))
    stderr_log = Path(__file__).resolve().parent.parent / "katago_stderr.log"
    proc = subprocess.Popen(
        ["katago", "analysis", "-config", ANALYSIS_CFG, "-model", KATAGO_MODEL],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=open(stderr_log, "w"), text=True,
    )
    proc.stdin.write(json.dumps(query) + "\n")
    proc.stdin.flush()

    results = {}
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        resp = json.loads(line)
        if "error" in resp:
            proc.kill()
            raise RuntimeError(f"KataGo 오류: {resp['error']}")
        if "warning" in resp and "turnNumber" not in resp:
            continue
        turn = resp["turnNumber"]
        results[turn] = resp
        progress(len(results), n_turns)
        if len(results) == n_turns:
            break
    proc.kill()
    if len(results) != n_turns:
        raise RuntimeError(f"분석 불완전: {len(results)}/{n_turns} 턴")
    if analyze_turns is not None:
        return results
    return [results[t] for t in range(n_turns)]


def replay_boards(meta, initial, moves):
    """각 턴 직후의 판 상태 스냅샷(문자열 리스트) 생성. boards[t] = t수까지 둔 판."""
    from sgfmill.boards import Board
    size = meta["size"]
    b = Board(size)
    for s in initial:
        b.play(s["row"], s["col"], s["color"])
    snapshots = [board_to_grid(b, size)]
    for color, mv in moves:
        if mv is not None:
            try:
                b.play(mv[0], mv[1], color)
            except ValueError:
                pass  # 비정상 SGF의 착수 무시
        snapshots.append(board_to_grid(b, size))
    return snapshots


def board_to_grid(b, size):
    """판 상태를 문자열로: 행별 '.', 'b', 'w' (row 0 = 아랫줄이 리스트 마지막)"""
    rows = []
    for r in range(size - 1, -1, -1):
        rows.append("".join(
            {"b": "b", "w": "w", None: "."}[b.get(r, c)] for c in range(size)))
    return rows


def classify(meta, moves, turns, visits):
    """턴별 KataGo 결과에서 수별 delta, 등급, 승부처, 단계 요약을 계산."""
    n = len(moves)
    per_turn = []
    for t, resp in enumerate(turns):
        ri = resp["rootInfo"]
        best = resp["moveInfos"][0] if resp.get("moveInfos") else None
        per_turn.append({
            "turn": t,
            "winrate": ri["winrate"],          # 흑 기준 0~1
            "scoreLead": ri["scoreLead"],      # 흑 기준 집차이
            "bestMove": best["move"] if best else None,
            "bestPv": best["pv"][:12] if best else [],
            "candidates": [
                {"move": mi["move"], "winrate": mi["winrate"],
                 "scoreLead": mi["scoreLead"], "visits": mi["visits"],
                 "scoreStdev": mi.get("scoreStdev"), "pv": mi["pv"][:12]}
                for mi in resp.get("moveInfos", [])[:5]
            ],
        })

    move_evals = []
    for i in range(1, n + 1):
        color, mv = moves[i - 1]
        before, after = per_turn[i - 1], per_turn[i]
        sign = 1 if color == "b" else -1
        loss_pts = sign * (before["scoreLead"] - after["scoreLead"])
        loss_wr = sign * (before["winrate"] - after["winrate"])
        gtp = "pass" if mv is None else rc_to_gtp(*mv)
        matched_best = before["bestMove"] == gtp

        if loss_pts >= 6 or loss_wr >= 0.15:
            grade = "대악수"
        elif loss_pts >= 3 or loss_wr >= 0.08:
            grade = "실수"
        elif loss_pts >= 1.5 or loss_wr >= 0.04:
            grade = "완착"
        elif matched_best or loss_pts <= 0.3:
            grade = "호착"
        else:
            grade = "보통"

        move_evals.append({
            "moveNum": i,
            "color": color,
            "gtp": gtp,
            "region": region_name(*mv) if mv else "",
            "lossPts": round(loss_pts, 1),
            "lossWr": round(loss_wr, 3),
            "grade": grade,
            "matchedBest": matched_best,
            "winrateAfter": round(after["winrate"], 3),
            "scoreLeadAfter": round(after["scoreLead"], 1),
            "bestAlternative": before["bestMove"],
            "bestPv": before["bestPv"],
        })

    # 승부처: 승률 변동 상위 + 리드가 뒤바뀐 수
    swings = sorted(move_evals, key=lambda m: abs(m["lossWr"]), reverse=True)
    turning = []
    seen = set()
    for m in swings:
        if abs(m["lossWr"]) < 0.06 or len(turning) >= 6:
            break
        if m["moveNum"] in seen:
            continue
        seen.add(m["moveNum"])
        turning.append(m["moveNum"])
    for i in range(1, n + 1):
        wb, wa = per_turn[i - 1]["winrate"], per_turn[i]["winrate"]
        if (wb - 0.5) * (wa - 0.5) < 0 and abs(wa - wb) >= 0.05 and i not in seen:
            seen.add(i)
            turning.append(i)
    turning = sorted(turning)[:8]

    good = [m for m in move_evals if m["grade"] == "호착"]
    # 호착 중에서도 의미 있는 국면(후보 간 차이가 컸던 곳) 우선, 최대 10개
    good = sorted(good, key=lambda m: -abs(m["lossWr"]))
    good_nums = sorted(m["moveNum"] for m in good[:10])
    bad = sorted([m for m in move_evals if m["grade"] in ("대악수", "실수", "완착")],
                 key=lambda m: -m["lossPts"])
    bad_nums = [m["moveNum"] for m in bad[:12]]

    return {
        "meta": meta,
        "visits": visits,
        "nMoves": n,
        "perTurn": [{"turn": p["turn"], "winrate": round(p["winrate"], 3),
                     "scoreLead": round(p["scoreLead"], 1)} for p in per_turn],
        "moveEvals": move_evals,
        "turningPoints": turning,
        "goodMoves": good_nums,
        "badMoves": bad_nums,
        "candidatesByTurn": {str(p["turn"]): p["candidates"] for p in per_turn},
    }


def restrict_to_competitive(result, lo=0.10, hi=0.90):
    """프로 기보용: 잘 둔 수·문제 수 후보를 착수 직전 흑 승률 lo~hi 경합 국면에서 다시 뽑는다.
    classify()의 후보는 집 손실 순이라 승부가 기운 뒤의 큰 손실이 상위를 차지하므로, 후보 목록을
    필터링하지 않고 moveEvals에서 재산출한다. 경합 국면에서는 승률 손실 순으로 정렬한다.
    (승부가 끝난 국면의 손실은 훈련 가치가 없다는 프로 피드백 2026-09-17 반영. 멱등.)"""
    wr = {p["turn"]: p["winrate"] for p in result["perTurn"]}
    comp = [m for m in result["moveEvals"]
            if lo <= wr.get(m["moveNum"] - 1, 0.5) <= hi and m["gtp"] != "pass"]
    bad = sorted([m for m in comp if m["grade"] in ("대악수", "실수", "완착")],
                 key=lambda m: (-m["lossWr"], -m["lossPts"]))
    good = sorted([m for m in comp if m["grade"] == "호착"], key=lambda m: -abs(m["lossWr"]))
    result["badMoves"] = [m["moveNum"] for m in bad[:12]]
    result["goodMoves"] = sorted(m["moveNum"] for m in good[:10])
    result["competitiveOnly"] = True
    return result
