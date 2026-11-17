# esports-ui — 화면 (Django)

> 프로젝트 전체 구성과 결정 사항은 **`../esports-analyzer/docs/PLAN.md`가 기준**이다.
> **ui → api 스펙은 구글 스펙 시트 spec_sheet_lol이 기준** (링크는 PLAN.md 6장). 스펙에 없는 호출이 필요하면 먼저 사용자에게 확인한다.
> 드라마 스토리 예측 버전 화면은 `drama` 브랜치에만 있다. main 은 LoL 화면만.

## 스킬 먼저 (esports-dev 플러그인)
아래 작업은 코드를 보거나 명령을 치기 전에 해당 스킬을 먼저 부른다. 이 문서의 구조만 보고 바로 하면 스킬에 적힌 순서와 같이 고칠 곳(스펙 시트, api)을 빠뜨린다.
- 화면에 새 데이터를 보이려고 api 호출을 추가·변경 (`web/api_client.py`) → `esports-dev:add-endpoint`
- 로컬 서버 띄우기·끄기·로그 → `esports-dev:local-up`
- README·CLAUDE.md 를 코드에 맞추기 → `esports-dev:docs-sync`

## 이 레포의 역할
간단한 웹 화면. 자체 DB 없이 api 를 HTTP로 호출해 렌더링한다 (`API_URL`, 기본 `http://api:8000`).
Django 템플릿 위주, 자바스크립트는 최소로.

## 화면
- `/` 세트 영상 목록 (`GET /games`): 해설 언어, 블루 vs 레드, 길이, 분석 상태
- `/games/new/` 영상 추가 (`GET /sources`, `POST /games`): vod 폴더에서 1920x1080 영상만 골라 경기·세트·언어·단계 지정 → 분석 시작
- `/games/<id>/` 세트 화면 (`GET /games/{id}`): 경기 정보(대회·스코어·영상 링크), 단계 상태, 포지션별 선수
  - 분석 중이면 진행 단계·경과 시간 + 10초마다 새로고침, 중지 (`/cancel`)
  - 분석 다시 실행 (`/analyze`), 번역: 조건 고르기 → 예상 비용 (`/estimate` + 가정 가격) → 번역 시작
  - `?tab=lines` 대사·번역 (`/lines`): 영상 시간, 게임 시간, 킬, 받아쓴 원문(ASR 한국어), 조건 A/B/C 영어 번역. `only=unreviewed|edited|translated`
    - 대사 검수 (`/lines/{line_id}/review`): O/X 버튼(검수 여부), "고치기"로 문장 수정, 고친 대사는 ASR 원문과 글자 단위 비교(`<del>`/`<ins>`). 고친 문장으로 번역된다
  - `?tab=screen&tag=` 화면 OCR 구간 (`/screen`)
  - `?tab=json&stage=` 단계 결과 원본 (`/analysis`)
- `/skills/` 스킬 사용·선택 평가 (`GET /skills`, `/skills/evals`, `/skills/cases`, `/skills/evals/jobs`): 요약 타일, 스킬별 표, 틀린 요청(`?skill=`로 거름, `?batch=`로 결과 이름 바꿈)
  - 비교할 결과 고르기 (`?compare=`): 스킬별 표에 그 결과의 재현율과 차이(%p)
  - 평가 실행 (`POST /skills/evals/jobs`): 결과 이름은 후보(`EVAL_LABELS`: baseline, after-1~3, recheck)에서 고르고 실제 이름은 `<후보>-<모델>`. 진행 중이면 5초마다 새로고침, 중지 (`/cancel`). 실제 실행은 맥의 `../dev-workflow/evals/worker.py`
  - 테스트 요청 추가 (`POST /skills/cases`): "골라야 하는 스킬"이 시험하는 스킬과 다르면 쓰면 안 되는 요청으로 들어간다
  - 평가 범위: 전체 요청 / 지금 보는 결과에서 틀린 요청만 (`case_ids`)
  - 설명 개선 시도 (`GET /skills/improves`): 시도별 원인 종류·가설·새 설명·채택/기각/무효, 고쳐진·깨진 요청
  - 틀린 요청 표의 "실제로 한 일"에 스킬 대신 고른 첫 도구와 그 입력(Bash 명령, Read 파일 경로)을 보여 준다
  - 틀린 요청 표에서 정답 고치기·빼기 (`POST /skills/cases/{id}`): 이미 돈 결과도 새 정답으로 다시 판정. 파일(`evals/cases`) 반영은 실행기가 한다 ("파일 반영 대기")
- 할 것: 케이스셋 검수 화면 (`/cases`), 영상 재생(hls)

## 구조
- api 호출은 `web/api_client.py`에만
- `web/views.py`: 화면별 뷰
- 템플릿 `web/templates/web/` (`games.html`, `game.html`, `skills.html`), 공통 필터 `web/templatetags/fmt.py` (`tc` 초 → mm:ss, `get`, `pct` 비율 → %, `num` 천 단위 쉼표)
- 색·글꼴 토큰은 `web/static/web/app.css` 맨 위. 블루 진영 = 파랑, 레드 진영 = 빨강

```
cd ../esports-api && docker compose up --build   # ui 도 api compose 의 ui 서비스로 같이 뜬다 → http://localhost:8000
```
- ui 만 따로 띄울 때: `docker run --rm --network esports_default -p 8080:8080 -v "$PWD":/app esports-ui` (api compose 네트워크에서 http://api:8000 호출)

## 규칙 요약
- 데이터는 api 에서만 읽는다. ui 에 목업 JSON 을 두지 않는다
- api 호출은 GET/POST만, 시간은 초(float)
- 주소는 환경변수, 패키지는 `requirements.txt`에 `==` 고정 후 이미지 재빌드

## 커밋 규칙
- 메시지는 `종류/내용` 한 줄 (`feat/` `refactor/` `fix/` `docs/` `chore/`)
- 작성자는 사용자 본인만. Claude 를 `Co-Authored-By` 등 공동 작성자로 넣지 않는다
