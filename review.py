#!/usr/bin/env python3
"""SGF 기보를 받아 KataGo 분석 + Claude 서사 해설이 담긴 HTML 복기 리포트를 만든다.

사용법:
  ./review "기보.sgf"                 # 기본 (400 visits, Claude 해설 포함)
  ./review "기보.sgf" --visits 800    # 더 깊은 분석
  ./review "기보.sgf" --fast          # 빠른 분석 (100 visits)
  ./review "기보.sgf" --no-llm        # KataGo 데이터만 (Claude 호출 생략)
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import analysis as A
from lib import llm
from lib import render
from lib import tactics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sgf", help="SGF 기보 파일 경로")
    ap.add_argument("--visits", type=int, default=400)
    ap.add_argument("--fast", action="store_true", help="visits 100으로 빠르게")
    ap.add_argument("--no-llm", action="store_true", help="Claude 해설 생략")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL)
    ap.add_argument("--player", choices=["b", "w"], default=None,
                    help="복기 주인공 색 (해설 관점이 이쪽에 맞춰짐)")
    ap.add_argument("--no-open", action="store_true", help="완료 후 브라우저 열지 않음")
    ap.add_argument("--level", choices=["amateur", "pro"], default="amateur",
                    help="학생 기력대 (해설 톤과 초점)")
    ap.add_argument("--reviews-dir", default=None,
                    help="리뷰 출력 폴더 (기본 reviews/). 타 기사 기보는 reviews/<선수>/ 권장")
    args = ap.parse_args()

    visits = 100 if args.fast else args.visits
    sgf_path = Path(args.sgf).expanduser()
    if not sgf_path.exists():
        sys.exit(f"파일 없음: {sgf_path}")

    base = Path(args.reviews_dir).expanduser() if args.reviews_dir \
        else Path(__file__).resolve().parent / "reviews"
    out_dir = base / sgf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] SGF 파싱: {sgf_path.name}")
    meta, initial, moves = A.parse_sgf(sgf_path)
    print(f"      {meta['black']}(흑) vs {meta['white']}(백), {len(moves)}수, "
          f"덤 {meta['komi']}, 결과 {meta['result'] or '미기록'}")

    print(f"[2/4] KataGo 분석 ({visits} visits x {len(moves) + 1}국면)...")
    t0 = time.time()

    def prog(done, total):
        pct = done * 100 // total
        print(f"\r      진행 {done}/{total} ({pct}%)", end="", flush=True)

    turns = A.run_katago(meta, initial, moves, visits, progress=prog)
    print(f"\n      완료 ({time.time() - t0:.0f}초)")

    result = A.classify(meta, moves, turns, visits)
    if args.level == "pro":
        A.restrict_to_competitive(result)
    snapshots = A.replay_boards(meta, initial, moves)
    ownership_by_turn = {t: r.get("ownership") for t, r in enumerate(turns)}
    tactics.enrich_analysis(result, snapshots, ownership_by_turn)
    (out_dir / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    review = None
    if not args.no_llm:
        print(f"[3/4] Claude 해설 생성 (모델 {args.model})...")
        t0 = time.time()
        prompt = llm.build_prompt(result, snapshots, moves, focus=args.player, level=args.level)
        (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        try:
            review = llm.call_claude(prompt, model=args.model)
            (out_dir / "review.json").write_text(
                json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"      완료 ({time.time() - t0:.0f}초)")
        except Exception as e:
            print(f"      해설 실패 (데이터 리포트만 생성): {e}")
    else:
        print("[3/4] Claude 해설 생략 (--no-llm)")

    print("[4/4] HTML 리포트 생성...")
    out_html = out_dir / "report.html"
    render.render(result, review, initial, moves, out_html, game_name=sgf_path.stem)
    print(f"\n✔ 완료: {out_html}")

    if not args.no_open:
        subprocess.run(["open", str(out_html)])


if __name__ == "__main__":
    main()
