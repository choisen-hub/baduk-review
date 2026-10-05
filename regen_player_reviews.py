#!/usr/bin/env python3
"""analysis.json은 있으나 해설(review.json)이 없거나 깨진 리뷰 폴더의 Claude 해설만 다시 생성해 HTML을 다시 그린다.
KataGo는 돌리지 않는다.

사용법: ./venv/bin/python regen_player_reviews.py --reviews-dir reviews/이서영 --sgf-dir ../baduk/이서영 --player 이서영 --level pro [--force]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.analysis import parse_sgf, replay_boards
from lib import llm, render


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reviews-dir", required=True)
    ap.add_argument("--sgf-dir", required=True)
    ap.add_argument("--player", required=True)
    ap.add_argument("--level", choices=["amateur", "pro"], default="amateur")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true", help="해설이 있어도 다시 생성")
    args = ap.parse_args()
    rdir, sdir = Path(args.reviews_dir).expanduser(), Path(args.sgf_dir).expanduser()

    for d in sorted(rdir.iterdir()):
        if not (d / "analysis.json").exists():
            continue
        rp = d / "review.json"
        ok = False
        if rp.exists() and not args.force:
            try:
                r = json.loads(rp.read_text())
                ok = bool(r.get("overall")) and bool(r.get("turningPoints"))
            except Exception:
                ok = False
        html_has_review = False
        if (d / "report.html").exists():
            html_has_review = '"review": null' not in (d / "report.html").read_text(encoding="utf-8")
        if ok and html_has_review:
            print(f"건너뜀 (해설 있음): {d.name}")
            continue
        m = re.search(rf"\({re.escape(args.player)} (백|흑)", d.name)
        focus = None if not m else ("b" if m.group(1) == "흑" else "w")
        sgf = sdir / (d.name + ".sgf")
        if not sgf.exists():
            print(f"건너뜀 (SGF 없음): {d.name}")
            continue
        print(f"=== 해설 생성: {d.name} (focus={focus})", flush=True)
        a = json.loads((d / "analysis.json").read_text())
        if args.level == "pro":
            from lib.analysis import restrict_to_competitive
            restrict_to_competitive(a)
            (d / "analysis.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        meta, initial, moves = parse_sgf(sgf)
        snaps = replay_boards(meta, initial, moves)
        if ok:
            review = json.loads(rp.read_text())
            print("    기존 review.json 사용, HTML만 재렌더", flush=True)
        else:
            prompt = llm.build_prompt(a, snaps, moves, focus=focus, level=args.level)
            (d / "prompt.txt").write_text(prompt, encoding="utf-8")
            review = llm.call_claude(prompt, model=args.model)
            rp.write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
        render.render(a, review, initial, moves, d / "report.html", game_name=d.name)
        print("    완료:", review.get("oneLiner", "")[:70], flush=True)
    print("REGEN DONE", flush=True)


if __name__ == "__main__":
    main()
