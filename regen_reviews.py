import sys, json
sys.path.insert(0, '.')
from lib.analysis import parse_sgf, replay_boards, run_katago
from lib import llm, render, tactics

GAMES = [
    ('reviews/260521 교준 (승호 백)', '../baduk/260521 교준 (승호 백).sgf', 'w', '260521 교준 (승호 백)'),
    ('reviews/260812 타이젬 vs chtaek (승호 흑)', '../baduk/260812 타이젬 vs chtaek (승호 흑).sgf', 'b', ''),
    ('reviews/260812 타이젬 vs kim379 (승호 흑, 불계패)', '../baduk/260812 타이젬 vs kim379 (승호 흑, 불계패).sgf', 'b', ''),
    ('reviews/260812 타이젬 vs kktaeek (승호 백)', '../baduk/260812 타이젬 vs kktaeek (승호 백).sgf', 'w', ''),
]
for D, SGF, focus, name in GAMES:
    print('===', D, flush=True)
    a = json.load(open(D + '/analysis.json'))
    meta, initial, moves = parse_sgf(SGF)
    snaps = replay_boards(meta, initial, moves)
    key_nums = set(a['turningPoints']) | set(a['goodMoves']) | set(a['badMoves'])
    turns = sorted({n - 1 for n in key_nums})
    print(f'  ownership 쿼리: {len(turns)}턴', flush=True)
    resp = run_katago(meta, initial, moves, visits=200, analyze_turns=turns)
    own = {t: r.get('ownership') for t, r in resp.items()}
    tactics.enrich_analysis(a, snaps, own)
    open(D + '/analysis.json', 'w').write(json.dumps(a, ensure_ascii=False, indent=1))
    prompt = llm.build_prompt(a, snaps, moves, focus=focus)
    open(D + '/prompt.txt', 'w').write(prompt)
    review = llm.call_claude(prompt)
    open(D + '/review.json', 'w').write(json.dumps(review, ensure_ascii=False, indent=1))
    render.render(a, review, initial, moves, D + '/report.html', game_name=name)
    print('  완료:', review['oneLiner'][:70], flush=True)
print('ALL DONE', flush=True)
