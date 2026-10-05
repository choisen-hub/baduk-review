"""수의 전술적 사실(형태)을 기하·규칙 기반으로 계산한다.

해설 LLM이 '이음을 끊음으로', '산 돌을 구하는 수로' 오독하는 것을 막기 위해,
각 핵심 수에 대해 판에서 검증 가능한 사실만을 한국어 요약으로 만들어 프롬프트에 주입한다.

좌표: arr[y][x], y=0 이 맨 아랫줄 (GTP 행번호-1), 값은 '.', 'b', 'w'
"""
from .analysis import rc_to_gtp, GTP_COLS


def to_arr(grid):
    """스냅샷(윗줄부터의 문자열 리스트) → arr[y][x] (y0=아랫줄)"""
    size = len(grid)
    return [[grid[size - 1 - y][x] for x in range(size)] for y in range(size)]


def neighbors(x, y, size):
    out = []
    if x > 0: out.append((x - 1, y))
    if x < size - 1: out.append((x + 1, y))
    if y > 0: out.append((x, y - 1))
    if y < size - 1: out.append((x, y + 1))
    return out


def diagonals(x, y, size):
    out = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < size and 0 <= ny < size:
                out.append((nx, ny))
    return out


def group_at(arr, x, y):
    size = len(arr)
    color = arr[y][x]
    pts, stack, seen = set(), [(x, y)], set()
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        px, py = p
        if arr[py][px] == color:
            pts.add(p)
            stack.extend(neighbors(px, py, size))
    return pts


def liberties(arr, pts):
    size = len(arr)
    libs = set()
    for (x, y) in pts:
        for (nx, ny) in neighbors(x, y, size):
            if arr[ny][nx] == ".":
                libs.add((nx, ny))
    return libs


def play(arr, x, y, color):
    """수를 둔 뒤의 새 판과 따낸 돌 수를 반환"""
    size = len(arr)
    new = [row[:] for row in arr]
    new[y][x] = color
    opp = "w" if color == "b" else "b"
    captured = 0
    for (nx, ny) in neighbors(x, y, size):
        if new[ny][nx] == opp:
            g = group_at(new, nx, ny)
            if not liberties(new, g):
                captured += len(g)
                for (gx, gy) in g:
                    new[gy][gx] = "."
    g = group_at(new, x, y)
    if not liberties(new, g):
        for (gx, gy) in g:
            new[gy][gx] = "."
    return new, captured


def ownership_at(ownership, x, y, size=19):
    """KataGo ownership 배열(row-major, 왼쪽 위부터, 흑 기준 -1~1)에서 (x,y) 값"""
    return ownership[(size - 1 - y) * size + x]


def group_stability(arr, pts, ownership, color, size=19):
    """무리의 평균 ownership을 착수자 색 기준 0~100%로"""
    if not ownership or not pts:
        return None
    vals = [ownership_at(ownership, x, y, size) for (x, y) in pts]
    mean = sum(vals) / len(vals)  # 흑 기준 -1~1
    if color == "w":
        mean = -mean
    return round((mean + 1) / 2 * 100)


def stability_word(pct):
    if pct is None:
        return ""
    if pct >= 85: return f"사실상 확정(생존 안정도 {pct}%)"
    if pct >= 65: return f"우세하지만 미확정(안정도 {pct}%)"
    if pct >= 35: return f"생사 불확실(안정도 {pct}%)"
    return f"죽은 돌에 가까움(안정도 {pct}%)"


def move_shape(grid_before, x, y, color, ownership=None):
    """수의 형태 사실을 한국어 한 단락으로. grid_before = 착수 직전 스냅샷."""
    arr = to_arr(grid_before)
    size = len(arr)
    opp = "w" if color == "b" else "b"
    facts = []

    line = min(x, y, size - 1 - x, size - 1 - y) + 1
    facts.append(f"{line}선")

    adj_own_groups, adj_enemy_groups = [], []
    seen_own, seen_enemy = set(), set()
    for (nx, ny) in neighbors(x, y, size):
        c = arr[ny][nx]
        if c == color and (nx, ny) not in seen_own:
            g = group_at(arr, nx, ny)
            seen_own |= g
            adj_own_groups.append(g)
        elif c == opp and (nx, ny) not in seen_enemy:
            g = group_at(arr, nx, ny)
            seen_enemy |= g
            adj_enemy_groups.append(g)

    after, captured = play(arr, x, y, color)
    my_group_after = group_at(after, x, y) if after[y][x] == color else set()
    my_libs_after = len(liberties(after, my_group_after)) if my_group_after else 0

    # 기본 관계
    if len(adj_own_groups) >= 2:
        facts.append(f"자신의 무리 {len(adj_own_groups)}개를 연결하는 이음")
    elif len(adj_own_groups) == 1:
        own_stone_lines = [min(gx, gy, size - 1 - gx, size - 1 - gy) + 1
                           for (gx, gy) in adj_own_groups[0]
                           if abs(gx - x) + abs(gy - y) == 1]
        if own_stone_lines and line < min(own_stone_lines):
            facts.append("자기 돌에서 변 쪽으로 내려서는 수(내려섬)")
        else:
            facts.append("자기 돌에 잇대어 두는 수(뻗음)")
    if adj_enemy_groups and not adj_own_groups:
        has_diag_own = any(arr[dy][dx] == color for (dx, dy) in diagonals(x, y, size))
        facts.append("상대 돌에 젖히는 수(젖힘)" if has_diag_own else "상대 돌에 붙이는 수(붙임)")

    # 끊음 판정: 서로 다른 상대 무리 둘 이상과 접촉 + 그 무리의 돌들이 이 점을 사이에 두고 대각 관계
    if len(adj_enemy_groups) >= 2:
        cut = False
        adj_enemy_stones = [(nx, ny) for (nx, ny) in neighbors(x, y, size) if arr[ny][nx] == opp]
        for i in range(len(adj_enemy_stones)):
            for j in range(i + 1, len(adj_enemy_stones)):
                ax, ay = adj_enemy_stones[i]
                bx, by = adj_enemy_stones[j]
                if abs(ax - bx) == 1 and abs(ay - by) == 1:
                    ga = next(g for g in adj_enemy_groups if (ax, ay) in g)
                    gb = next(g for g in adj_enemy_groups if (bx, by) in g)
                    if ga is not gb:
                        cut = True
        facts.append("상대 무리 둘을 실제로 갈라놓는 끊음" if cut
                     else f"상대 무리 {len(adj_enemy_groups)}개 사이에 끼어드는 수")

    # 접촉 없는 수: 가장 가까운 자기 돌과의 관계
    if not adj_own_groups and not adj_enemy_groups:
        best = None
        for gy in range(size):
            for gx in range(size):
                if arr[gy][gx] != ".":
                    d = max(abs(gx - x), abs(gy - y))
                    if best is None or d < best[0]:
                        best = (d, gx, gy, arr[gy][gx])
        if best and best[0] <= 3:
            d, gx, gy, c = best
            rel = "자기" if c == color else "상대"
            dx, dy = abs(gx - x), abs(gy - y)
            names = {(0, 2): "한칸", (2, 0): "한칸", (1, 2): "날일자", (2, 1): "날일자",
                     (0, 3): "두칸", (3, 0): "두칸", (1, 3): "눈목자", (3, 1): "눈목자",
                     (1, 1): "어깨/마늘모", (2, 2): "밭전자"}
            nm = names.get((dx, dy), f"거리 {d}")
            facts.append(f"{rel} 돌 {rc_to_gtp(gy, gx)}에서 {nm} 관계, 어느 돌과도 접촉 없음")
            if ownership:
                g = group_at(arr, gx, gy)
                w = stability_word(group_stability(arr, g, ownership, c, size))
                if w:
                    facts.append(f"그 {rel} 무리는 착수 전 {w}")
        else:
            facts.append("주변에 돌이 없는 전개/침입성 수")

    # 따냄·단수
    if captured:
        facts.append(f"상대 돌 {captured}개를 따냄")
    ataris = []
    for (nx, ny) in neighbors(x, y, size):
        if after[ny][nx] == opp:
            g = group_at(after, nx, ny)
            if len(liberties(after, g)) == 1:
                ataris.append(len(g))
    if ataris:
        facts.append(f"상대 무리(돌 {max(ataris)}개)를 단수로 몰음")
    facts.append(f"착수 후 이 무리의 활로 {my_libs_after}개"
                 + (" (위험)" if my_libs_after <= 2 else ""))

    # ownership 기반 생사 판단
    if ownership:
        if adj_own_groups:
            biggest = max(adj_own_groups, key=len)
            w = stability_word(group_stability(arr, biggest, ownership, color, size))
            if w:
                facts.append(f"이 수가 닿는 자기 무리는 착수 전 이미 {w}")
        if adj_enemy_groups:
            biggest = max(adj_enemy_groups, key=len)
            w = stability_word(group_stability(arr, biggest, ownership, opp, size))
            if w:
                facts.append(f"접촉한 상대 무리는 {w}")

    return " · ".join(facts)


def enrich_analysis(analysis, snapshots, ownership_by_turn=None):
    """핵심 수(승부처·잘둔·아쉬운)에 shape 문자열을 심는다. analysis를 제자리 수정."""
    key_nums = set(analysis["turningPoints"]) | set(analysis["goodMoves"]) | set(analysis["badMoves"])
    ev = {m["moveNum"]: m for m in analysis["moveEvals"]}
    for n in key_nums:
        m = ev.get(n)
        if not m or m["gtp"] == "pass":
            continue
        col = GTP_COLS.index(m["gtp"][0])
        row = int(m["gtp"][1:]) - 1
        own = (ownership_by_turn or {}).get(n - 1)
        m["shape"] = move_shape(snapshots[n - 1], col, row, m["color"], own)
    return analysis
