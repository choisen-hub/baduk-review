"""실전 기보에서 사활이 실제로 갈린 장면을 검출해 사활 문제로 만든다.

원리: 큰 손실 수(5집 이상)의 전후 KataGo ownership을 비교해,
생사 안정도가 크게 뒤집힌 무리(돌 3개 이상)를 찾는다.
- 착수자 자신의 무리가 죽은 쪽으로 뒤집힘 → "살리는(수습하는) 문제"
- 상대 무리가 사는 쪽으로 뒤집힘(잡을 기회를 놓침) → "잡으러 가는 문제"
정답은 그 국면의 KataGo 최선수 (무리 근처에 있을 때만 문제로 채택).
"""
import json

from . import analysis as A
from .tactics import to_arr, group_at, group_stability


def all_groups(arr, min_size=3):
    size = len(arr)
    seen, groups = set(), []
    for y in range(size):
        for x in range(size):
            if arr[y][x] != "." and (x, y) not in seen:
                g = group_at(arr, x, y)
                seen |= g
                if len(g) >= min_size:
                    groups.append((arr[y][x], g))
    return groups


def bbox(pts, margin=2, size=19):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (max(0, min(xs) - margin), max(0, min(ys) - margin),
            min(size - 1, max(xs) + margin), min(size - 1, max(ys) + margin))


def in_box(x, y, box):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def find_problems(games, visits=250, per_game=4, flip_threshold=25, competitive=False):
    """games: overall.py의 find_games() 결과. 사활 문제 리스트 반환.
    competitive=True면 착수 직전 흑 승률 10~90% 국면만 후보로 삼는다(승부가 끝난 뒤의 사활은 제외)."""
    out = []
    for g in games:
        a = json.loads((g["dir"] / "analysis.json").read_text())
        meta, initial, moves = A.parse_sgf(g["sgf"])
        snapshots = A.replay_boards(meta, initial, moves)
        ev = {m["moveNum"]: m for m in a["moveEvals"]}
        wr = {p["turn"]: p["winrate"] for p in a["perTurn"]}
        pool = [m for m in a["moveEvals"] if m["lossPts"] >= 5 and m["gtp"] != "pass"]
        if competitive:
            pool = [m for m in pool if 0.10 <= wr.get(m["moveNum"] - 1, 0.5) <= 0.90]
        cand = sorted(pool, key=lambda m: -m["lossPts"])[:per_game * 2]
        if not cand:
            continue
        turns = sorted({t for m in cand for t in (m["moveNum"] - 1, m["moveNum"])})
        resp = A.run_katago(meta, initial, moves, visits, analyze_turns=turns)

        found = 0
        used_moves = []
        for m in cand:
            if found >= per_game:
                break
            if any(abs(m["moveNum"] - u) <= 3 for u in used_moves):
                continue  # 같은 전투의 연속 장면은 한 문제로
            n = m["moveNum"]
            rb, ra = resp.get(n - 1), resp.get(n)
            if not rb or not ra or "ownership" not in rb or "ownership" not in ra:
                continue
            arr = to_arr(snapshots[n - 1])
            flips = []
            for color, pts in all_groups(arr):
                sb = group_stability(arr, pts, rb["ownership"], color)
                sa = group_stability(arr, pts, ra["ownership"], color)
                if sb is None or sa is None:
                    continue
                if abs(sb - sa) >= flip_threshold:
                    flips.append((abs(sb - sa), color, pts, sb, sa))
            if not flips:
                continue
            flips.sort(reverse=True, key=lambda f: f[0])
            _, color, pts, sb, sa = flips[0]
            # 순수 사활·수상전 문제로 성립하려면 무리가 국지적이어야 한다.
            # 반상을 휘감은 대마의 소유권 붕괴(맛 처리 실패 등)는 사활 문제가 아니다.
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if len(pts) > 12 or (max(xs) - min(xs)) > 7 or (max(ys) - min(ys)) > 7:
                continue
            best = m["bestAlternative"]
            if not best:
                continue
            bx = A.gtp_to_rc(best)
            box = bbox(pts)
            wide = bbox(pts, margin=5)  # 치중·활로 조이기는 무리에서 떨어진 곳일 수 있음
            if bx is None or not in_box(bx[1], bx[0], wide):
                continue  # 최선수가 무리 주변이 아니면 순수 사활 문제로 부적합
            mover = m["color"]
            if color == mover and sa < sb:
                qtype, qtext = "살리기", "이 무리의 생사가 초점입니다. 최선수는?"
            elif color != mover and sa > sb:
                qtype, qtext = "잡기", "이 상대 무리를 추궁할 기회입니다. 최선수는?"
            else:
                qtype, qtext = "급소", "이 무리 주변이 초점입니다. 최선수는?"
            color_kr = "흑" if color == "b" else "백"
            out.append({
                "game": g["name"],
                "moveNum": n,
                "toMove": mover,
                "grid": snapshots[n - 1],
                "groupPts": sorted([x, y] for (x, y) in pts),
                "groupColor": color,
                "qtype": qtype,
                "qtext": f"△ 표시된 {color_kr} 무리에 주목. {qtext}",
                "played": m["gtp"],
                "lossPts": m["lossPts"],
                "best": best,
                "bestPv": m["bestPv"],
                "stabBefore": sb,
                "stabAfter": sa,
                "outcome": (f"실전 수 {m['gtp']} 이후 이 무리의 생존 안정도가 "
                            f"{sb}%에서 {sa}%로 바뀌며 {m['lossPts']}집이 걸린 사활이 갈렸습니다."),
                "candidates": [
                    {"move": c["move"], "scoreLead": round(c["scoreLead"], 1)}
                    for c in a.get("candidatesByTurn", {}).get(str(n - 1), [])[:5]
                ],
                "playedPv": [],
                "shape": m.get("shape", ""),
                "region": m["region"],
                "why": "", "variation": "", "reviewComment": "", "reviewBetter": "",
            })
            found += 1
            used_moves.append(m["moveNum"])
    out.sort(key=lambda p: -p["lossPts"])
    return out
