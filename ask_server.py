#!/usr/bin/env python3
"""검토 변화도 AI 평가 서버.

리포트 HTML의 "AI에게 묻기" 버튼이 http://127.0.0.1:8791/eval 로
검토 시작 국면 + 직접 놓은 수순을 보내면, KataGo가 각 수의 손실과
최종 형세, 이후 최선 진행을 계산해 돌려준다.

- KataGo 분석 엔진은 서버 시작 시 한 번 띄워서 계속 재사용한다 (질의당 수 초).
- 일정 시간(기본 45분) 질의가 없으면 스스로 종료해 메모리를 돌려준다.

사용법: ./ask               # 기본 포트 8791
       ./ask --port 8791 --visits 300 --idle 45
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from lib.analysis import ANALYSIS_CFG, KATAGO_MODEL  # noqa: E402

MAX_MOVES = 60  # 검토 수순 상한 (한 변화도로는 충분)


class Engine:
    """KataGo analysis engine 상주 프로세스. 질의는 락으로 직렬화한다."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.qid = 0

    def start(self):
        stderr_log = ROOT / "katago_stderr.log"
        self.proc = subprocess.Popen(
            ["katago", "analysis", "-config", ANALYSIS_CFG, "-model", KATAGO_MODEL],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=open(stderr_log, "a"), text=True,
        )

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def query(self, komi, initial, moves, visits):
        with self.lock:
            if not self.alive():
                self.start()
            self.qid += 1
            qid = f"ask{self.qid}"
            n_turns = len(moves) + 1
            q = {
                "id": qid,
                "rules": "korean",
                "komi": komi,
                "boardXSize": 19,
                "boardYSize": 19,
                "initialStones": initial,
                "moves": moves,
                "analyzeTurns": list(range(n_turns)),
                "maxVisits": visits,
                "includePolicy": False,
                "includeOwnership": False,
            }
            self.proc.stdin.write(json.dumps(q) + "\n")
            self.proc.stdin.flush()
            results = {}
            while len(results) < n_turns:
                line = self.proc.stdout.readline()
                if not line:
                    raise RuntimeError("KataGo 프로세스가 종료됨")
                line = line.strip()
                if not line:
                    continue
                resp = json.loads(line)
                if resp.get("id") != qid:
                    continue
                if "error" in resp:
                    raise RuntimeError(f"KataGo 오류: {resp['error']}")
                if "turnNumber" not in resp:
                    continue
                results[resp["turnNumber"]] = resp
            turns = []
            for t in range(n_turns):
                r = results[t]
                ri = r["rootInfo"]
                mis = r.get("moveInfos", [])
                best = mis[0] if mis else None
                turns.append({
                    "turn": t,
                    "winrate": round(ri["winrate"], 4),      # 흑 기준
                    "scoreLead": round(ri["scoreLead"], 2),  # 흑 기준
                    "best": best["move"] if best else None,
                    "pv": best["pv"][:8] if best else [],
                    "candidates": [
                        {"move": m["move"], "scoreLead": round(m["scoreLead"], 2),
                         "winrate": round(m["winrate"], 4)}
                        for m in mis[:3]
                    ],
                })
            return turns


engine = Engine()
last_query = [time.time()]
DEFAULT_VISITS = 200


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}", flush=True)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self._json(200, {"ok": True, "engine": engine.alive()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/eval":
            self._json(404, {"error": "not found"})
            return
        last_query[0] = time.time()
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n))
            moves = req.get("moves", [])
            if not moves:
                raise ValueError("moves가 비어 있음")
            if len(moves) > MAX_MOVES:
                raise ValueError(f"수순이 너무 김 (최대 {MAX_MOVES}수)")
            turns = engine.query(
                komi=float(req.get("komi", 6.5)),
                initial=req.get("initial", []),
                moves=moves,
                visits=min(int(req.get("visits", DEFAULT_VISITS)), 1000),
            )
            self._json(200, {"turns": turns})
        except Exception as e:
            self._json(500, {"error": str(e)})
        last_query[0] = time.time()


def idle_watcher(minutes, server):
    while True:
        time.sleep(60)
        if time.time() - last_query[0] > minutes * 60:
            print(f"질의 없이 {minutes}분 경과, 종료합니다.", flush=True)
            threading.Thread(target=server.shutdown, daemon=True).start()
            return


def main():
    global DEFAULT_VISITS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--visits", type=int, default=DEFAULT_VISITS)
    ap.add_argument("--idle", type=int, default=45, help="분 단위, 0이면 계속 실행")
    args = ap.parse_args()
    DEFAULT_VISITS = args.visits

    print("KataGo 엔진 기동 중 (첫 기동은 십수 초 걸릴 수 있습니다)...", flush=True)
    engine.start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    if args.idle > 0:
        threading.Thread(target=idle_watcher, args=(args.idle, server), daemon=True).start()
    print(f"준비 완료: http://127.0.0.1:{args.port}/eval  "
          f"(유휴 {args.idle}분 후 자동 종료, Ctrl-C로 종료)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if engine.proc:
            engine.proc.kill()


if __name__ == "__main__":
    main()
