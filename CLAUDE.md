# storycast-ui — 화면 (Django)

> 프로젝트 전체 구성, 결정 사항, **API 스펙(요청/응답 예시 포함)은 `../PLAN.md`가 기준**이다.
> 작업 전에 반드시 읽고, 스펙에 없는 호출이 필요하면 먼저 사용자에게 확인한다. 스펙을 이 파일에 복사하지 않는다.

## 이 레포의 역할
간단한 웹 UI. 자체 DB 모델 없이 api를 HTTP로 호출해 렌더링한다 (`API_URL` 환경변수).
Django 템플릿 + htmx 수준으로 가볍게. 영상은 hls.js로 MinIO에서 직접 재생.

## 현재 상태
`web/` 앱에 화면 1~4(드라마 → 예측 → 결과, 회차 검수 + 분석 JSON). 데이터는 전부 api에서 읽는다 (ui에 JSON 저장 안 함). `requirements.txt`: django, requests.
settings의 SECRET_KEY/DEBUG/ALLOWED_HOSTS는 환경변수(`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`)로 받음.
- api 호출은 `web/api_client.py`에만. 주소는 `API_URL` (기본 `http://api:8000`)
- 분석 결과 조회(`get_analysis`)와 대사 검수 저장(`save_line_review`)은 **api 스펙에 없음** → 지금은 회차 검수 화면에 "아직 api 스펙에 없습니다" 표시. api에 호출이 생기면 이 함수들만 바꾼다
- 회차 검수(`episode.html` + `web/static/web/studio.js`)는 영상 편집기형 단일 화면: 장면 목록 · 영상 · 인스펙터 + 타임라인(장면 트랙, 선택 장면의 대사 레인). 페이지에 심은 JSON으로 브라우저에서 그리고, 판정 POST는 JSON 응답
- 색·글꼴 토큰은 `web/static/web/app.css` 맨 위. 근거=형광펜 노랑, 반대 근거=빨간 밑줄, 검수 맞음/수정/틀림=청/노랑/빨강
```
docker build -t storycast-ui .
docker run --rm --network storycast_default -p 8080:8080 -v "$PWD":/app storycast-ui   # -v: 코드 수정 시 자동 reload
# --network: api compose 네트워크에 붙어 http://api:8000 으로 호출 (api를 먼저 띄울 것)
```

## 화면 (MVP)
메인 흐름은 PLAN.md 5장 "화면 흐름": 드라마 선택 → 예측할 회차(`target`) 선택 → 예측 시작 → 결과.
업로드 화면은 만들지 않는다 (영상은 관리 명령으로 넣음).

1. 드라마 선택 → 회차 목록 + 등장인물 (크롤링 데이터, 조회만)
2. 예측할 회차 선택 (앞 회차가 모두 분석 완료인 회차만), 예측 시작 + 상태 폴링
3. 예측 결과: 예측 카드 + 확신도 + 근거/반대 근거 클릭 → 해당 회차 영상의 `currentTime = start`
4. 회차 타임라인: Segment 목록 + 대사, 분석 진행 상태
5. 화자 매핑: S1, S2… → 등장인물 선택
6. 창작 아이디어

## 작업 순서
데이터는 api에서만 읽는다. ui에 목업 JSON을 두지 않는다 (api가 떠 있어야 화면이 나옴).
api 호출은 `web/api_client.py` 한 모듈에 모은다.

## 규칙 요약 (상세는 PLAN.md)
- api 호출은 GET/POST만
- 시간은 초 단위 float, 장면 참조는 `{segment_id, start, end}`
- 주소는 환경변수, 패키지는 `requirements.txt`에 `==` 고정 후 이미지 재빌드
