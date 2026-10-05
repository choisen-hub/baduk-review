# baduk-review

baduk-review is a command-line tool that turns a Go (baduk) game record in SGF format into an interactive HTML review. KataGo's analysis engine supplies the numbers (winrate and score lead for every position, best moves, principal variations, ownership), and a Claude model turns those numbers into a narrative commentary: an overall assessment, a phase-by-phase story, the turning points, the good moves, the mistakes, and the lessons to take away. A second tool aggregates many reviewed games into a training dashboard with generated exercises, and a small local server lets you try your own variations inside a report and have KataGo grade them.

It is written for a Go player who wants to review their own games, or for a teacher reviewing a student's games. The generated reports and the commentary are in Korean.

The Korean version of this document is in `README.ko.md`.

## Features

Per-game review (`review.py`, invoked through the `./review` wrapper)

- Parses the SGF main line with `sgfmill` (players, komi, result, date, handicap stones).
- Sends the whole game to the KataGo analysis engine in one query (Korean rules, ownership included) and reads back one result per position. Default 400 visits per position; `--fast` uses 100; `--visits N` sets any value.
- Grades every move from the change in score lead and winrate (thresholds in `lib/analysis.py`):
  - 대악수 (blunder): loses 6 or more points, or 15 or more winrate percentage points
  - 실수 (mistake): 3 points or 8 percentage points
  - 완착 (slack move): 1.5 points or 4 percentage points
  - 호착 (good move): matches KataGo's top choice, or loses at most 0.3 points
  - 보통 (ordinary) otherwise
- Picks turning points: the largest winrate swings of at least 6 percentage points plus any move where the lead changed hands, at most 8 in total.
- Computes verified shape facts for each key move (`lib/tactics.py`): line number, connection versus cut (checked against actual group structure), attachment, hane, descent, extension, one-point and knight's jumps, captures and ataris, liberties after the move, and the life-and-death stability of nearby groups taken from KataGo ownership. These facts are injected into the prompt so the language model cannot describe a connection as a cut or claim a settled group was "saved".
- Builds a prompt with the full move list, a winrate trajectory, candidate turning points with ASCII board diagrams, candidate good and bad moves, and strict writing rules, then calls Claude through the `claude` CLI and parses the JSON reply (`lib/llm.py`). Up to three retries on malformed output.
- Two tones: `--level amateur` (default) explains principles; `--level pro` assumes a professional reader, forbids coordinates and raw numbers in prose, forbids life-and-death assertions, and restricts the good-move and mistake candidates to competitive positions (Black winrate between 10 and 90 percent before the move).
- `--player b|w` tells the commentary whose perspective to take. `--no-llm` produces a data-only report. `--reviews-dir` chooses the output folder. `--model` overrides the Claude model. `--no-open` suppresses opening the report in the browser.
- Writes `analysis.json`, `prompt.txt`, `review.json`, and `report.html` into `reviews/<sgf name>/`.

The HTML report (`lib/render.py`)

- Interactive board with a move slider, buttons, and left and right arrow keys.
- Winrate and score-lead chart with hover tooltips; clicking the chart jumps to that move.
- Colored move markers: good (green), slack (yellow), mistake (orange), blunder (red); clicking a marker jumps to the move.
- Turning-point cards with a button that replays KataGo's recommended variation on the board with numbered overlays.
- Collapsed table of the raw per-move evaluation.
- A review mode where you click on the board to play your own variation, undo and redo one move at a time (buttons or arrow keys), and press "Ask AI" to have the local evaluation server grade each move of the variation and show the resulting position and continuation.
- Automatic light and dark themes.

Aggregate training report (`overall.py`)

- Collects every reviewed game whose folder name carries a `(<player> 백)` or `(<player> 흑)` tag, so the tool knows which color the student played. Games without the tag are listed as skipped.
- Separates official games from sparring games by keywords in the folder name (`SPARRING_KEYWORDS`).
- Aggregates grade distribution, losses by game phase and by board region, counting only competitive positions, and splits mistakes into "missed the big point" (best move 5 or more lines away) versus "local reading error".
- Extracts reading problems from positions where the student lost points, re-analyzes each chosen position more deeply (`DEEP_VISITS = 1500`), and for the losing side proposes a "fighting move" candidate that keeps winrate within 6 points of the best move but has a much larger score variance.
- Builds positional-judgment exercises at 35, 55, 75 and 90 percent of each game with KataGo ownership maps for scoring.
- Detects life-and-death problems (`lib/lifedeath.py`) by comparing ownership before and after large losses and looking for groups of 3 or more stones whose stability flipped.
- Asks Claude for a short explanation of each problem and for an overall diagnosis (strengths, recurring patterns, practice plan, checklist).
- Caches everything in `_종합캐시.json` so `--render-only` can redraw the HTML without calling KataGo or Claude. Output is `reviews/종합 리포트.html` (or `종합 리포트 (<player>).html` for a non-default player).

Variation evaluation server (`ask_server.py`, invoked through `./ask`)

- A `ThreadingHTTPServer` on `127.0.0.1:8791` with `POST /eval` and `GET /ping`, CORS enabled so a report opened from the file system can reach it.
- Keeps one KataGo analysis engine process alive and serializes queries with a lock; queries take seconds instead of the engine's start-up time.
- Shuts itself down after 45 minutes without a query (`--idle 0` disables this). Variations are capped at 60 moves and 1000 visits per query.

Helper scripts

- `prep_player.py`: takes SGF files exported without player metadata, reads date, event, players and result from a filename of the form `YYYY.M.D-N event 흑 A 백 B 흑|백 불계승|N집승.sgf`, writes copies with `DT`, `EV`, `PB`, `PW`, `RE` injected into the root node, and names them with the `(<player> 색, 결과)` tag the other tools expect. Originals are untouched.
- `regen_player_reviews.py`: regenerates only the Claude commentary (and the HTML) for review folders whose `review.json` is missing or broken, without re-running KataGo.
- `rerender_html.py`: redraws every `report.html` from existing `analysis.json` and `review.json`; useful after editing `lib/render.py`.
- `regen_reviews.py`: an older ad hoc script with a hard-coded game list, kept for reference.

## How it works

```
SGF file
  |
  v
lib/analysis.parse_sgf          main line only, metadata, handicap stones
  |
  v
lib/analysis.run_katago         one JSON query to `katago analysis`, one response per turn
  |
  v
lib/analysis.classify           per-move loss, grade, turning points, good/bad candidates
lib/analysis.restrict_to_competitive   (pro level only)
  |
  v
lib/tactics.enrich_analysis     verified shape facts from board geometry + ownership
  |                              -> analysis.json
  v
lib/llm.build_prompt            Korean prompt with rules and JSON schema -> prompt.txt
lib/llm.call_claude             `claude -p --model <model> --tools "" ...`  -> review.json
  |
  v
lib/render.render               single self-contained HTML -> report.html
```

`overall.py` reads the `analysis.json` and `review.json` files of many games, runs extra KataGo queries for deep re-analysis and ownership maps, calls Claude for problem explanations and a synthesis, and renders through `lib/overall_render.py`.

`ask_server.py` is independent of the review pipeline: the report's JavaScript posts the starting position and the moves you played, and the server returns per-turn winrate, score lead, best move, principal variation and the top three candidates.

Two conventions matter throughout the code:

- All winrates and score leads are from Black's point of view. This relies on `reportAnalysisWinratesAs = BLACK` in `analysis.cfg`. Changing that setting silently breaks every grade.
- The analysis engine may drop an in-flight query if stdin is closed, so `run_katago` keeps stdin open until all turns have been received.

## Requirements

- macOS is assumed: the wrapper scripts are zsh, reports are opened with `open`, and the author runs KataGo from Homebrew with the Metal backend. The Python code itself is portable, but the paths and the `open` calls would need adjusting elsewhere.
- Python 3.9 or later with `sgfmill`.
- KataGo (`katago` on `PATH`) and a network file. The path to the network is the `KATAGO_MODEL` constant in `lib/analysis.py`; the default points to a Homebrew install of `kata1-b18c384nbt`.
- Claude Code CLI (`claude`) installed and logged in. Commentary is generated with `claude -p`, not with a direct API call, so no API key is read by this project. Whatever authentication the CLI uses applies.

## Installation and running

```bash
git clone https://github.com/choisen-hub/baduk-review.git
cd baduk-review

# KataGo and a network (example for Homebrew on macOS)
brew install katago
# place a network file and point KATAGO_MODEL in lib/analysis.py at it

# Python environment
python3 -m venv venv
./venv/bin/pip install sgfmill

# Review one game (opens reviews/<name>/report.html when done)
./review path/to/game.sgf
```

Make sure `claude` works from the shell (`claude -p "ping" --model claude-sonnet-5`) before running with commentary enabled, or pass `--no-llm`.

## Configuration

| Where | Setting | Meaning |
| --- | --- | --- |
| `analysis.cfg` | `reportAnalysisWinratesAs = BLACK` | Required. All classification assumes Black-relative values. |
| `analysis.cfg` | `maxVisits`, `numAnalysisThreads`, `numSearchThreadsPerAnalysisThread`, `nnMaxBatchSize` | KataGo search and hardware settings; tune for your machine. |
| `analysis.cfg` | `logDir = analysis_logs` | KataGo writes a log per run here (gitignored). |
| `lib/analysis.py` | `KATAGO_MODEL` | Absolute path to the network file. |
| `lib/analysis.py` | `ANALYSIS_CFG` | Path to `analysis.cfg` (defaults to the repo copy). |
| `lib/llm.py` | `DEFAULT_MODEL = "claude-sonnet-5"` | Model passed to `claude -p`. Override per run with `--model`. The model is always passed explicitly. |
| `lib/llm.py` | `call_claude` | Runs `claude -p --tools "" --setting-sources "" --no-session-persistence` with a JSON-only system prompt and strips `CLAUDECODE*` environment variables so a nested Claude Code session cannot turn the call into an agent run. |
| `overall.py` | `DEEP_VISITS = 1500` | Visits for the deep re-analysis of training positions; 0 skips it. |
| `overall.py` | `SPARRING_KEYWORDS` | Folder-name keywords that mark a game as sparring rather than official. |
| `overall.py` | `SGF_DIR = ROOT.parent / "baduk"` | Default location of the SGF files, a sibling folder named `baduk`; override with `--sgf-dir`. |
| `overall.py`, `regen_player_reviews.py` | `--player` | The name tag in review folder names. `overall.py` defaults to the author's own tag (`승호`); pass your own. |
| `ask_server.py` | `--port 8791`, `--visits 200`, `--idle 45` | Server port, default visits per query, idle minutes before shutdown. |

No environment variables are read by this project. If you authenticate the `claude` CLI with an API key, set `ANTHROPIC_API_KEY=<your key>` in the shell where you run the scripts; this project never stores it.

## Project structure

```
baduk-review/
  review              zsh wrapper: runs review.py with the venv interpreter
  review.py           CLI entry point for a single-game review
  ask                 zsh wrapper: runs ask_server.py with the venv interpreter
  ask_server.py       local KataGo evaluation server for in-report variations
  overall.py          aggregate training report across reviewed games
  prep_player.py      inject metadata into SGF files named by a filename convention
  regen_player_reviews.py   regenerate missing or broken commentary without KataGo
  rerender_html.py    redraw all report.html files from cached JSON
  regen_reviews.py    older ad hoc regeneration script (hard-coded list)
  analysis.cfg        KataGo analysis engine configuration
  lib/
    analysis.py       SGF parsing, KataGo driver, move grading, competitive filter
    tactics.py        geometric shape facts and group stability for the prompt
    lifedeath.py      life-and-death problem detection from ownership flips
    llm.py            prompt construction and `claude -p` call
    render.py         single-game HTML report template and renderer
    overall_render.py aggregate report template (dashboard, diagnosis, exercises)
  reviews/            generated output, one folder per game (gitignored)
  analysis_logs/      KataGo logs (gitignored)
  venv/               Python virtual environment (gitignored)
  LICENSE
  README.md           this file
  README.ko.md        Korean version
```

## Usage examples

Single game, default settings (400 visits, Claude commentary, opens in browser):

```bash
./review "260812 club game.sgf"
```

The student played White, deeper search, no browser:

```bash
./review "game.sgf" --player w --visits 800 --no-open
```

Data-only report without any Claude call:

```bash
./review "game.sgf" --no-llm
```

Professional-level tone, output under a per-player folder:

```bash
./review "../baduk/alice/260917 league vs bob (alice 백, 불계패).sgf" \
  --player w --level pro --reviews-dir reviews/alice --no-open
```

Aggregate report for every game tagged `(alice 백)` or `(alice 흑)`:

```bash
./venv/bin/python overall.py --player alice --level pro \
  --reviews-dir reviews/alice --sgf-dir ../baduk/alice
# later, after editing the template only:
./venv/bin/python overall.py --player alice --reviews-dir reviews/alice --render-only
```

Prepare exported SGF files whose root node lacks player names and result:

```bash
./venv/bin/python prep_player.py --player alice --src ~/Downloads --dry
./venv/bin/python prep_player.py --player alice --src ~/Downloads
```

Start the variation server, then open any `report.html`, play a variation on the board, and press "Ask AI":

```bash
./ask --visits 400
```

Regenerate commentary for folders that have `analysis.json` but no usable `review.json`:

```bash
./venv/bin/python regen_player_reviews.py --reviews-dir reviews/alice \
  --sgf-dir ../baduk/alice --player alice --level pro
```

Redraw every report after a change to `lib/render.py`:

```bash
./venv/bin/python rerender_html.py
```

## Data, licensing and attribution

- KataGo (https://github.com/lightvector/KataGo) is a separate program under its own MIT license. Network weights are downloaded separately from the KataGo project; check their terms before redistributing. Neither the binary nor any network file is included in this repository.
- `sgfmill` (https://mjw.woodcraft.me.uk/sgfmill/) is used for SGF parsing and board replay.
- Commentary is produced by a Claude model through the Claude Code CLI and may be wrong. The shape facts and prompt rules reduce, but do not eliminate, misreadings of a position.
- The `reviews/` folder, the SGF folder, and any `*_복기_*` folders are gitignored because game records and reports identify the players. Do not commit other people's games without their consent.
- Grade thresholds, turning-point rules, the competitive-position filter and the fighting-move heuristic were tuned by hand from feedback on real reviews; they are not derived from any published standard.

## Known limitations and roadmap

- Only the SGF main line is analyzed; variations stored in the file are ignored.
- All prompts, reports and UI strings are in Korean. There is no language switch.
- `KATAGO_MODEL` is a hard-coded absolute path and the scripts call `open`, so running on Linux or Windows requires small edits.
- Ownership-based stability and liberty counts at 400 visits are sometimes wrong in tactical positions; the pro-level prompt already tells the model not to cite them, but the amateur-level prompt still exposes them.
- The report's "Ask AI" button only works while `./ask` is running on the same machine.
- The `--player` tag convention (folder name must contain `(<name> 백)` or `(<name> 흑)`) is the only way the aggregate report learns the student's color.
- `regen_reviews.py` contains a hard-coded list of games from an early session and is not maintained.

## License

MIT. See [LICENSE](LICENSE).
