"""api 호출을 한 곳에 모은다. 주소는 settings.API_URL.

확정 스펙(스펙 시트)에 있는 호출만 부른다.
"""

import requests
from django.conf import settings


class ApiError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.message = message
        self.status = status


def _http(method, path, timeout=10, **kwargs):
    url = settings.API_URL.rstrip("/") + path
    try:
        resp = requests.request(method, url, timeout=timeout, **kwargs)
    except requests.RequestException as e:
        raise ApiError(f"api에 연결하지 못했습니다 ({settings.API_URL})", 502) from e
    if resp.status_code >= 400:
        try:
            message = resp.json().get("error")
        except ValueError:
            message = None
        raise ApiError(message or f"api 오류 ({resp.status_code})", resp.status_code)
    return resp.json()


# ---------------------------------------------------------------- LoL 세트 영상 (spec_sheet_lol)

def list_games():
    """GET /games"""
    return _http("GET", "/games")


def get_game(game_id):
    """GET /games/{id} — 단계 상태, 경기 정보(진영별 선수) 포함"""
    return _http("GET", f"/games/{game_id}")


def get_game_lines(game_id, from_sec=None, to_sec=None):
    """GET /games/{id}/lines — 대사 + 그 시점 화면 정보 + 조건별 번역"""
    params = {k: v for k, v in (("from_sec", from_sec), ("to_sec", to_sec)) if v is not None}
    return _http("GET", f"/games/{game_id}/lines", params=params)


def get_game_screen(game_id, tag=None, min_samples=2):
    """GET /games/{id}/screen — 화면 OCR 구간"""
    params = {"min_samples": min_samples, **({"tag": tag} if tag else {})}
    return _http("GET", f"/games/{game_id}/screen", params=params)


def get_game_analysis(game_id, stage):
    """GET /games/{id}/analysis?stage= — 단계 결과 원본"""
    return _http("GET", f"/games/{game_id}/analysis", params={"stage": stage})


def list_sources():
    """GET /sources — 원본 영상 목록 (1920x1080 만 selectable)"""
    return _http("GET", "/sources", timeout=120)


def create_game(body):
    """POST /games — 영상 등록 + 분석 시작. body: {video, title, language, match, set, stages}"""
    return _http("POST", "/games", json=body, timeout=60)


def analyze_game(game_id, stages, conditions=None):
    """POST /games/{id}/analyze — 단계 추가 실행 (번역이면 conditions)"""
    body = {"stages": stages, **({"conditions": conditions} if conditions else {})}
    return _http("POST", f"/games/{game_id}/analyze", json=body, timeout=60)


def cancel_game(game_id):
    """POST /games/{id}/cancel"""
    return _http("POST", f"/games/{game_id}/cancel")


def estimate_game(game_id, conditions):
    """GET /games/{id}/estimate — 번역 예상 입력 토큰"""
    return _http("GET", f"/games/{game_id}/estimate", params={"conditions": ",".join(conditions)}, timeout=120)
