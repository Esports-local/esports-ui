# esports-ui

LoL 중계 번역 실험의 화면 (Django 템플릿). [esports-api](https://github.com/djkim0704/esports-api)를 호출해서 보여 준다.

- 계획·실험 조건: [esports-analyzer/docs/PLAN.md](https://github.com/djkim0704/esports-analyzer/blob/main/docs/PLAN.md)

## 화면
| 주소 | 내용 |
|---|---|
| `/` | 세트 영상 목록 |
| `/games/<id>/?tab=lines` | 해설 대사(ASR 한국어)와 조건별 영어 번역 비교 (A 대사만 / B + 화면 OCR / C + 영상 프레임), 그 시점 게임 시간·킬 |
| `/games/<id>/?tab=screen` | 화면 OCR 구간 (팀 킬, KDA, 골드, 타워, 게임 시간, 선수 이름) |
| `/games/<id>/?tab=json` | 분석 단계 결과 원본 |

## 실행
api를 먼저 띄운 뒤 (`esports-api`에서 `docker compose up`):
```
docker build -t esports-ui .
docker run --rm --network esports_default -p 8080:8080 -v "$PWD":/app esports-ui
```
http://localhost:8080 . api 주소는 `API_URL` 환경변수 (기본 `http://api:8000`).
