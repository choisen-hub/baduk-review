"""분석 데이터를 Claude(claude -p)에 넘겨 서사형 복기 해설을 생성한다.

주의: 자동화 원칙에 따라 모델은 반드시 명시적으로 고정한다 (--model).
"""
import json
import re
import subprocess

DEFAULT_MODEL = "claude-sonnet-5"

HEAD_AMATEUR = ('당신은 다정하지만 정확한 프로 바둑 사범입니다. 아마추어 기력의 학생이 둔 대국을 KataGo 분석 데이터에 근거해 '
                '복기해 주세요. 학생이 "아, 그래서 그랬구나"를 느끼도록, 데이터를 나열하지 말고 이야기로 풀어 주세요.')
HEAD_PRO = ('당신은 냉철하고 정확한 프로 바둑 도장의 수석 사범입니다. 프로 기사가 둔 공식 대국을 KataGo 분석 데이터에 근거해 '
            '복기해 주세요. 상대도 프로이므로 기초 원칙 설명은 생략하고, 형세판단의 오차, 수읽기 누락, 방향 선택, 시간 배분이 '
            '엿보이는 장면, 끝내기 정밀도처럼 프로 승률을 실제로 가르는 요소를 중심으로 짚어 주세요. 학생이 다음 공식 대국에서 '
            '바로 고칠 수 있는 구체적 습관 단위로 정리하되, 데이터를 나열하지 말고 이야기로 풀어 주세요.')

SCHEMA_HINT = """{
  "overall": "총평 4~6문장. 이 대국의 성격, 승부의 흐름, 패인/승인을 짚는다.",
  "oneLiner": "이 판을 한 문장으로 요약",
  "story": [
    {"phase": "포석", "range": "1~30", "title": "소제목", "text": "그 구간의 이야기 3~5문장"},
    {"phase": "중반", "range": "...", "title": "...", "text": "..."},
    {"phase": "종반", "range": "...", "title": "...", "text": "..."}
  ],
  "turningPoints": [
    {"moveNum": 57, "title": "승부처 소제목", "text": "무엇이 갈렸는지 4~6문장",
     "variationComment": "제시된 KataGo 변화도(PV)를 말로 풀어낸 해설 2~4문장"}
  ],
  "goodMoves": [{"moveNum": 12, "comment": "왜 좋은 수였는지 1~2문장"}],
  "badMoves": [{"moveNum": 33, "comment": "무엇이 문제였는지 1~2문장", "better": "대신 둘 곳과 이유 1문장"}],
  "lessons": ["이 판에서 배워갈 것 (구체적 원칙 형태로) 4~6개"],
  "strengths": ["이 판에서 드러난 학생의 강점 2~3개, 근거가 된 수 번호 포함"],
  "weaknesses": [{"pattern": "이 판에서 드러난 약점 이름", "evidence": "근거 수 번호와 상황", "fix": "다음 대국에서 어떻게 보완할지 1~2문장"}]
}"""


def ascii_board(grid):
    """grid: 문자열 리스트(윗줄부터), '.', 'b', 'w'. 좌표 라벨 포함 텍스트 보드."""
    size = len(grid[0])
    cols = "ABCDEFGHJKLMNOPQRST"[:size]
    lines = ["   " + " ".join(cols)]
    for i, row in enumerate(grid):
        num = size - i
        cells = " ".join({".": "·", "b": "X", "w": "O"}[ch] for ch in row)
        lines.append(f"{num:2d} {cells}")
    return "\n".join(lines)


def build_prompt(analysis, snapshots, moves, focus=None, level="amateur"):
    meta = analysis["meta"]
    ev = {m["moveNum"]: m for m in analysis["moveEvals"]}

    move_list = ", ".join(
        f"{m['moveNum']}{'B' if m['color'] == 'b' else 'W'}:{m['gtp']}"
        for m in analysis["moveEvals"])

    traj = ", ".join(
        f"{p['turn']}수:{round(p['winrate'] * 100)}%/{p['scoreLead']:+.1f}"
        for p in analysis["perTurn"] if p["turn"] % 4 == 0 or p["turn"] == analysis["nMoves"])

    def move_detail(n, with_board=False):
        m = ev[n]
        color = "흑" if m["color"] == "b" else "백"
        s = (f"- {n}수 {color} {m['gtp']}({m['region']}): 등급 {m['grade']}, "
             f"손실 {m['lossPts']}집 / 승률 {m['lossWr'] * 100:+.1f}%p, "
             f"이 수 이후 흑 승률 {m['winrateAfter'] * 100:.0f}%")
        if m.get("shape"):
            s += f"\n  형태 정보(코드로 검증된 사실): {m['shape']}"
        if m["bestAlternative"] and m["bestAlternative"] != m["gtp"]:
            s += f"\n  KataGo 추천: {m['bestAlternative']}, 변화도(PV): {' '.join(m['bestPv'])}"
        if with_board:
            s += f"\n  [{n - 1}수까지 둔 장면, X=흑 O=백]\n" + ascii_board(snapshots[n - 1])
        return s

    turning = "\n".join(move_detail(n, with_board=True) for n in analysis["turningPoints"])
    good = "\n".join(move_detail(n) for n in analysis["goodMoves"])
    bad = "\n".join(move_detail(n) for n in analysis["badMoves"])

    handicap_note = f", {meta['handicap']}점 접바둑" if meta.get("handicap") else ""
    result_note = meta["result"] or "기록 없음"
    partial_note = ""
    if not meta["result"]:
        partial_note = ("\n- 이 기보는 도중까지만 두고 끝낸 미완성 대국입니다. 승패를 단정하지 말고, "
                        "기록된 수까지의 흐름만 해설한 뒤 마지막 국면의 형세 판단(승률·집차이)으로 마무리하세요. "
                        "story의 단계 구분도 기록이 끝나는 지점까지만 나누세요.")
    focus_note = ""
    if focus in ("b", "w"):
        color_kr = "흑" if focus == "b" else "백"
        name = meta["black"] if focus == "b" else meta["white"]
        focus_note = (f"\n- 학생은 {color_kr}({name})입니다. 해설은 양쪽 수를 모두 다루되, "
                      f"총평과 배워갈 것은 학생({color_kr}) 관점을 중심으로 써 주세요.")

    head = HEAD_PRO if level == "pro" else HEAD_AMATEUR
    if level == "pro":
        coord_rule = ("- 문장에서는 좌표(Q16 같은 GTP 표기)를 쓰지 말 것. 수는 \"60수(좌변)\"처럼 수 번호와 지역명으로만 지칭. "
                      "읽는 사람이 프로라 좌표는 보지 않는다.\n"
                      "- 안정도 퍼센트, 활로 개수, 손실 집수, 승률 퍼센트 같은 수치를 문장에 옮겨 적지 말 것. 수치는 리포트의 그래프와 표가 "
                      "이미 보여준다. 문장은 방향 선택, 순서, 타이밍, 크기 비교, 두터움과 실리의 교환 같은 판단의 언어로 쓸 것.\n"
                      "- 무리의 생사를 단정하지 말 것(\"죽은 돌\", \"사실상 잡힌 돌\", \"살아 있는 무리\" 금지). 형태 정보는 서술의 방향을 "
                      "정하는 참고일 뿐이며, 특히 400 visits 분석의 안정도와 활로 수치는 프로 검토에서 틀린 사례가 있으므로 문장의 근거로 쓰지 말 것.\n"
                      "- 이미 승부가 기운 국면의 손실은 다루지 말고, 경합 국면에서 승부를 가른 판단만 다룰 것.\n"
                      "- strengths와 weaknesses는 이 판에서 실제로 드러난 것만, 수 번호를 근거로 쓸 것. 일반론 금지.")
    else:
        coord_rule = "- 좌표는 \"Q16(우상귀)\"처럼 GTP 표기와 지역명을 병기."
    return f"""{head}

## 대국 정보
- 흑: {meta['black']} / 백: {meta['white']}
- 날짜: {meta['date']}, 덤 {meta['komi']}{handicap_note}, 결과: {result_note}
- 총 {analysis['nMoves']}수, KataGo {analysis['visits']} visits 분석{partial_note}{focus_note}

## 전체 수순 (수번호+색:좌표)
{move_list}

## 승률 궤적 (수: 흑 승률%/흑 기준 집차이, 4수 간격)
{traj}

## 승부처 후보 (장면도 포함)
{turning}

## 잘 둔 수 후보
{good}

## 문제 수 후보
{bad}

## 작성 규칙
- 출력은 아래 스키마의 순수 JSON 하나만. 코드펜스, 설명문 금지.
- 중요: 위 승률 궤적의 %와 집차이는 전부 흑 기준입니다. 98%는 흑이 압도적으로 유리하다는 뜻이고, 2%는 백이 압도적으로 유리하다는 뜻입니다. 총평과 스토리를 쓰기 전에, 서사의 우세·열세 서술이 이 궤적과 일치하는지 반드시 검증하세요. 색을 혼동한 해설은 전부 무효입니다.
{coord_rule}
- 변화도 해설(variationComment)은 반드시 위에 제시된 KataGo PV를 근거로 쓸 것. PV에 없는 수순을 지어내지 말 것.
- 수의 기능 서술은 각 수에 딸린 "형태 정보"를 유일한 근거로 삼을 것. 형태 정보와 모순되는 전술 용어 사용 금지: 형태 정보에 "이음"이라 되어 있으면 끊음이라 쓰지 말고, "끊음"이 명시된 경우에만 끊음이라 쓸 것. "돌을 살린다/구한다/잡으러 간다" 같은 표현은 형태 정보에 활로 위험이나 낮은 생사 안정도가 명시된 경우에만 사용할 것. "사실상 확정(생존)"으로 표시된 무리에 대해 살리는 수라고 쓰는 것은 오류임. 형태 정보가 없는 수는 좌표·방향·지역 수준으로만 서술하고 세부 전술을 단정하지 말 것.
- 용어 정의: 이음=자기 무리 연결, 끊음=상대 무리를 실제로 가르는 수, 붙임=자기 돌 지원 없이 상대 돌에 접촉, 젖힘=자기 돌과 대각으로 상대 돌을 감싸며 접촉, 내려섬=자기 돌에서 변 쪽으로 뻗는 수, 뻗음=자기 돌에 잇대어 두는 수.
- goodMoves는 3~6개, badMoves는 3~8개로 추릴 것 (후보 전부를 쓸 필요 없음). turningPoints는 후보 중 진짜 승부처 2~5개만.
- 문장 어디에도 엠대쉬(—) 금지. 쉼표, 마침표, 콜론만 사용.
- 존댓말로, 학생을 "님"으로 지칭.

## 출력 JSON 스키마
{SCHEMA_HINT}"""


JSON_ONLY_SYSTEM = ("You are a JSON generator. Respond with exactly one JSON value that matches the schema in the "
                    "user prompt. No tools, no file writes, no markdown, no prose before or after the JSON.")


def call_claude(prompt, model=DEFAULT_MODEL, timeout=600):
    """claude -p 를 도구 없는 순수 생성 모드로 호출한다.

    Claude Code 세션 안에서(nohup 등) 호출되면 CLAUDECODE 계열 환경변수와 CLAUDE.md 설정이 상속되어
    에이전트처럼 파일을 쓰고 마크다운 요약을 돌려주는 사고가 있었다(2026-09-17). 그래서 도구·설정 소스를
    끄고 세션 환경변수를 제거한 뒤 시스템 프롬프트로 JSON 전용을 못박는다.
    """
    import os
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE", "CLAUDE_PID", "CLAUDE_EFFORT"))}
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", JSON_ONLY_SYSTEM]
    last_err = None
    for attempt in range(3):
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env)
        if proc.returncode != 0:
            last_err = RuntimeError(f"claude -p 실패: {proc.stderr[:500]}")
            continue
        try:
            return parse_json(proc.stdout)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = e
            print(f"      (해설 JSON 파싱 실패, 재시도 {attempt + 1}/3: {str(e)[:80]})", flush=True)
    raise last_err


def parse_json(text):
    """코드펜스나 앞뒤 잡음이 있어도 첫 JSON 값({} 또는 [])을 파싱."""
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE)
    so, sa = text.find("{"), text.find("[")
    if so == -1 and sa == -1:
        raise ValueError(f"JSON을 찾지 못함:\n{text[:300]}")
    if sa != -1 and (so == -1 or sa < so):
        start, end = sa, text.rfind("]")
    else:
        start, end = so, text.rfind("}")
    if end == -1:
        raise ValueError(f"JSON이 닫히지 않음:\n{text[:300]}")
    return json.loads(text[start:end + 1])
