#!/usr/bin/env python3
"""타 기사 기보(Lizzie 내보내기, PB/PW/RE 비어 있음)를 파일명에서 대국자·결과를 읽어
메타를 채운 사본으로 baduk/<선수>/ 에 만든다. 원본은 건드리지 않는다.

사용법: ./venv/bin/python prep_player.py --player <이름> --src ~/Downloads [--only "2026.9.1"]
파일명 규격: "YYYY.M.D-N 대회(시간) 흑 A 백 B 흑|백 불계승|N집승.sgf"
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

PAT = re.compile(
    r"^(\d{4})\.(\d{1,2})\.(\d{1,2})(?:-\d+)?\s*(.*?)\s*흑\s+(\S+)\s+백\s+(\S+)\s+(흑|백)\s+(불계승|불게승|[\d.]+집승)$")


def parse_name(stem):
    m = PAT.match(stem)
    if not m:
        return None
    y, mo, d, event, black, white, winner, how = m.groups()
    event = re.sub(r"\([^)]*\)\s*$", "", event).strip() or "대회 미상"
    if how.startswith("불"):
        res = f"{'B' if winner == '흑' else 'W'}+R"
        how_kr = "불계"
    else:
        pts = how.replace("집승", "")
        res = f"{'B' if winner == '흑' else 'W'}+{pts}"
        how_kr = f"{pts}집"
    return {
        "date": f"{y}-{int(mo):02d}-{int(d):02d}", "ymd": f"{y[2:]}{int(mo):02d}{int(d):02d}",
        "event": event, "black": black, "white": white, "winner": winner, "result": res, "how": how_kr,
    }


def inject(text, info):
    """루트 노드(첫 ';B[' 또는 ';W[' 이전)의 PB/PW/RE/DT/HA를 교체하고 EV를 추가."""
    m = re.search(r";[BW]\[", text)
    cut = m.start() if m else len(text)
    root, rest = text[:cut], text[cut:]
    root = re.sub(r"PB\[[^\]]*\]|PW\[[^\]]*\]|RE\[[^\]]*\]|DT\[[^\]]*\]|EV\[[^\]]*\]|HA\[[^\]]*\]", "", root)
    props = (f"DT[{info['date']}]EV[{info['event']}]PB[{info['black']}]PW[{info['white']}]"
             f"RE[{info['result']}]")
    root = root.replace("(;", "(;" + props, 1)
    return root + rest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--player", required=True)
    ap.add_argument("--src", default="~/Downloads")
    ap.add_argument("--only", default=None, help="파일명 접두 필터(쉼표 구분)")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    dst = Path(__file__).resolve().parent.parent / "baduk" / args.player
    dst.mkdir(parents=True, exist_ok=True)
    onlys = [o.strip() for o in args.only.split(",")] if args.only else None

    done, skipped = [], []
    for f in sorted(src.glob("*.sgf")):
        stem = unicodedata.normalize("NFC", f.stem)
        if stem.endswith(" (1)"):
            skipped.append((stem, "중복 다운로드"))
            continue
        if onlys and not any(stem.startswith(o) for o in onlys):
            continue
        info = parse_name(stem)
        if not info:
            skipped.append((stem, "파일명 규격 불일치"))
            continue
        if args.player == info["black"]:
            color, opp = "흑", info["white"]
        elif args.player == info["white"]:
            color, opp = "백", info["black"]
        else:
            skipped.append((stem, f"{args.player} 없음"))
            continue
        won = (info["winner"] == color)
        tag = f"{info['how']}{'승' if won else '패'}"
        new_name = f"{info['ymd']} {info['event']} vs {opp} ({args.player} {color}, {tag}).sgf"
        out = dst / new_name
        if args.dry:
            print(f"{stem}\n  -> {new_name}  [{info['result']}]")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        out.write_text(inject(text, info), encoding="utf-8")
        done.append(new_name)

    print(f"생성 {len(done)}건 -> {dst}")
    for n in done:
        print("  ", n)
    if skipped:
        print(f"건너뜀 {len(skipped)}건")
        for s, why in skipped:
            print(f"   {s}: {why}")


if __name__ == "__main__":
    main()
