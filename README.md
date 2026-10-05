# baduk-review: KataGo + Claude 바둑 복기 앱

SGF 기보를 넣으면 KataGo의 정량 분석 위에 Claude의 서사형 해설(총평, 스토리, 승부처, 잘 둔 수, 아쉬운 수, 배워갈 것)을 얹은 인터랙티브 HTML 리포트를 만든다.

## 사용법

```bash
cd "~/Desktop/7 예술/baduk-review"
./review "기보.sgf"                      # 기본: 400 visits + Claude 해설, 끝나면 브라우저 자동 오픈
./review "기보.sgf" --player w           # 복기 주인공이 백일 때 (해설 관점이 백 중심)
./review "기보.sgf" --visits 800         # 더 깊은 분석
./review "기보.sgf" --fast               # 100 visits 빠른 분석
./review "기보.sgf" --no-llm             # KataGo 데이터만, Claude 호출 생략
./review "기보.sgf" --model claude-fable-5   # 해설 모델 변경 (기본 claude-sonnet-5 고정)
```

산출물: `reviews/<기보이름>/report.html` (+ analysis.json, review.json, prompt.txt)

## 종합 리포트 (훈련장)

```bash
./venv/bin/python overall.py        # reviews/ 전체 집계 → reviews/종합 리포트.html
```

- 분석 완료된 대국 중 폴더명에 "(승호 백)" / "(승호 흑)" 표기가 있는 판만 집계 대상
- 전적 대시보드(등급 분포·단계별·지역별 손실), Claude 종합 진단(강점·반복 패턴·연습 플랜·체크리스트)
- 훈련 문제집: 실전에서 3집 이상 잃은 장면을 문제로 출제 (판당 최대 6개), 판을 클릭해 답하면 KataGo 후보 순위 기준으로 채점, 최선수·실전수·추천 변화 표시
- 새 대국을 ./review 로 분석한 뒤 overall.py를 다시 돌리면 자동 반영

## 검토 변화도 AI 평가 (./ask)

리포트에서 판을 클릭해 직접 변화를 놓아본 뒤 "AI에게 묻기" 버튼을 누르면, KataGo가 그 변화의
각 수 손실(등급), 최종 형세, 이후 추천 진행을 계산해 판 아래에 보여준다. 이 기능은 로컬 평가
서버가 켜져 있어야 동작한다:

```bash
cd "~/Desktop/7 예술/바둑/baduk-review"
./ask                      # KataGo 상주 서버 (포트 8791, 45분 무사용 시 자동 종료)
./ask --visits 400         # 더 깊은 평가 (기본 200, 질의당 수초~수십초)
```

검토 중에는 "한 수 무르기 / 다시 진행" 버튼(또는 좌우 방향키)으로 변화 수순을 한 수씩
되돌리고 다시 진행할 수 있다. 새 수를 두면 그 지점부터의 되돌리기 기록은 지워진다.

## 리포트 기능

- 인터랙티브 바둑판: 슬라이더/버튼/좌우 방향키로 수순 재생
- 승률·집차이 그래프(토글): 호버 툴팁, 클릭하면 해당 장면으로 점프
- 실착 마커: 호착(초록)/완착(노랑)/실수(주황)/대악수(빨강), 클릭 점프
- 승부처 카드: "변화도 재생" 버튼으로 KataGo 추천 수순을 판 위에 번호로 오버레이
- 전체 수 평가 원자료 표 (접힘)
- 라이트/다크 모드 자동

## 구조

```
review.py        # CLI 진입점 (venv 파이썬으로 실행하는 ./review 래퍼 사용)
lib/analysis.py  # SGF 파싱(sgfmill) + KataGo analysis engine 구동 + 수 분류
lib/llm.py       # 프롬프트 구성 + claude -p 호출 (모델 명시 고정)
lib/render.py    # 단일 HTML 리포트 렌더링
analysis.cfg     # KataGo 설정 (reportAnalysisWinratesAs = BLACK 이 전제)
```

## 전제 조건

- `katago` (brew, Metal 백엔드) + 모델 `kata1-b18c384nbt` (경로는 lib/analysis.py 상수)
- `claude` CLI 로그인 상태
- venv: `python3 -m venv venv && ./venv/bin/pip install sgfmill`

## 수 등급 기준 (lib/analysis.py classify)

- 대악수: 6집 이상 손실 또는 승률 15%p 이상 하락
- 실수: 3집 / 8%p
- 완착: 1.5집 / 4%p
- 호착: KataGo 1순위 일치 또는 손실 0.3집 이하
- 승부처: 승률 변동 6%p 이상 상위 + 우세가 뒤바뀐 수 (최대 8개)

## 해설 정확도 장치 (lib/tactics.py)

해설 LLM이 수의 기능을 오독하는 것(이음을 끊음으로, 산 돌을 구하는 수로)을 막기 위해,
핵심 수마다 코드로 검증한 형태 사실을 계산해 프롬프트에 주입한다.

- 기하 규칙: 몇 선, 이음/끊음(실제로 상대 무리를 가르는지 그룹 판정)/붙임/젖힘/내려섬/뻗음/한칸/날일자 등, 따냄·단수, 착수 후 활로
- KataGo ownership: 착수 전 주변 아군·적군 무리의 생사 안정도("사실상 확정(생존)" 무리에 "살리는 수" 서술 금지)
- llm.py 작성 규칙: 전술 용어는 형태 정보와 일치할 때만 사용, 승률 %는 항상 흑 기준(색 반전 서술 금지)

## 주의

- KataGo analysis engine은 stdin이 닫히면 진행 중 쿼리를 버릴 수 있어, 결과 수신 완료까지 stdin을 열어 둔다 (lib/analysis.py run_katago)
- 승률/집차이는 전부 흑 기준. analysis.cfg의 reportAnalysisWinratesAs를 바꾸면 분류가 전부 틀어진다
- SGF의 본선(main line)만 분석한다. Sabaki 변화도가 있는 파일도 본선만 읽음
