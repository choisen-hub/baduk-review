#!/usr/bin/env python3
"""기존 analysis.json + review.json으로 모든 report.html만 다시 그린다.

KataGo·Claude 호출이 없어 즉시 끝난다. 리포트 UI(lib/render.py)만 고쳤을 때 사용.
종합 리포트는 `./venv/bin/python overall.py --render-only`로 재렌더.

사용법: ./venv/bin/python rerender_html.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.analysis import parse_sgf
from lib import render

ROOT = Path(__file__).resolve().parent
SGF_DIR = ROOT.parent / "baduk"

for d in sorted((ROOT / "reviews").iterdir()):
    if not (d / "analysis.json").exists() or not (d / "review.json").exists():
        continue
    sgf = SGF_DIR / (d.name + ".sgf")
    if not sgf.exists():
        print(f"건너뜀 (SGF 없음): {d.name}")
        continue
    a = json.loads((d / "analysis.json").read_text())
    review = json.loads((d / "review.json").read_text())
    meta, initial, moves = parse_sgf(sgf)
    # 대국자 이름이 SGF에 없으면 폴더명을 헤더로 (승호 백/흑 표기는 떼지 않고 그대로)
    generic = meta["black"] in ("흑", "") and meta["white"] in ("백", "")
    name = d.name if generic else ""
    render.render(a, review, initial, moves, d / "report.html", game_name=name)
    print(f"OK {d.name}")
