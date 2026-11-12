# esports-ui — 화면 (Django)

> 프로젝트 전체 구성과 결정 사항은 **`../esports-analyzer/docs/PLAN.md`가 기준**이다.
> **ui → api 스펙은 구글 스펙 시트 spec_sheet_lol이 기준** (링크는 PLAN.md 6장). 스펙에 없는 호출이 필요하면 먼저 사용자에게 확인한다.
> 드라마 스토리 예측 버전 화면은 `drama` 브랜치에 있다. main 에도 `/drama/` 아래 남아 있다.

## 이 레포의 역할
간단한 웹 화면. 자체 DB 없이 api 를 HTTP로 호출해 렌더링한다 (`API_URL`, 기본 `http://api:8000`).
Django 템플릿 위주, 자바스크립트는 최소로.

## 화면
- `/` 세트 영상 목록 (`GET /games`): 해설 언어, 블루 vs 레드, 길이, 분석 상태
- `/games/<id>/` 세트 화면 (`GET /games/{id}`): 경기 정보(대회·스코어·영상 링크), 단계 상태, 포지션별 선수
  - `?tab=lines` 대사·번역 (`/lines`): 영상 시간, 게임 시간, 킬, 받아쓴 원문(ASR 한국어), 조건 A/B/C 영어 번역. `only=translated`
  - `?tab=screen&tag=` 화면 OCR 구간 (`/screen`)
  - `?tab=json&stage=` 단계 결과 원본 (`/analysis`)
- 할 것: 케이스셋 검수 화면 (`/cases`), 영상 재생(hls)

## 구조
- api 호출은 `web/api_client.py`에만
- `web/views.py`: 화면별 뷰 (위쪽은 드라마 버전, 아래 "LoL 세트 영상" 부분이 지금 화면)
- 템플릿 `web/templates/web/` (`games.html`, `game.html`), 공통 필터 `web/templatetags/vod.py` (`tc` 초 → mm:ss, `get`)
- 색·글꼴 토큰은 `web/static/web/app.css` 맨 위. 블루 진영 = 파랑, 레드 진영 = 빨강

```
docker build -t esports-ui .
docker run --rm --name esports-ui-dev --network esports_default -p 8080:8080 -v "$PWD":/app esports-ui
# --network: api compose 네트워크에 붙어 http://api:8000 으로 호출 (api 를 먼저 띄울 것)
```

## 규칙 요약
- 데이터는 api 에서만 읽는다. ui 에 목업 JSON 을 두지 않는다
- api 호출은 GET/POST만, 시간은 초(float)
- 주소는 환경변수, 패키지는 `requirements.txt`에 `==` 고정 후 이미지 재빌드

## 커밋 규칙
- 메시지는 `종류/내용` 한 줄 (`feat/` `refactor/` `fix/` `docs/` `chore/`)
- 작성자는 사용자 본인만. Claude 를 `Co-Authored-By` 등 공동 작성자로 넣지 않는다
