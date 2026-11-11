"""api 호출을 한 곳에 모은다. 주소는 settings.API_URL.

확정 스펙(스펙 시트)에 있는 호출만 실제로 부른다.
분석 결과 조회와 대사 검수 저장은 아직 스펙에 없어서 ApiError(501)를 낸다 —
api에 호출이 생기면 이 파일의 두 함수만 바꾼다.
"""

import requests
from django.conf import settings


class ApiError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.message = message
        self.status = status


def _http(method, path, **kwargs):
    url = settings.API_URL.rstrip("/") + path
    try:
        resp = requests.request(method, url, timeout=10, **kwargs)
    except requests.RequestException as e:
        raise ApiError(f"api에 연결하지 못했습니다 ({settings.API_URL})", 502) from e
    if resp.status_code >= 400:
        try:
            message = resp.json().get("error")
        except ValueError:
            message = None
        raise ApiError(message or f"api 오류 ({resp.status_code})", resp.status_code)
    return resp.json()


# ---------------------------------------------------------------- 확정 스펙


def list_series():
    """GET /series"""
    return _http("GET", "/series")


def get_series(series_id):
    """GET /series/{id} — 회차 목록, 등장인물 포함"""
    return _http("GET", f"/series/{series_id}")


def get_episode(episode_id):
    """GET /episodes/{id}"""
    return _http("GET", f"/episodes/{episode_id}")


def start_predict(series_id, target):
    """POST /series/{id}/predict"""
    return _http("POST", f"/series/{series_id}/predict", json={"target": target})


def get_predict(series_id, target):
    """GET /series/{id}/predict?target="""
    return _http("GET", f"/series/{series_id}/predict", params={"target": target})


# ---------------------------------------------------------------- 스펙 미정


def get_analysis(episode_id):
    """회차 분석 결과 (main analysis/episode.json 모양: scenes[].start_sec, lines …)."""
    raise ApiError("분석 결과 조회는 아직 api 스펙에 없습니다", 501)


def get_line_reviews(episode_id):
    """{"<scene_id>:<line_index>": {"verdict", "text"}}"""
    return {}


def save_line_review(episode_id, scene_id, index, verdict, text=None):
    """verdict: ok | wrong | fixed | clear. 저장된 판정(clear면 None)을 돌려준다."""
    raise ApiError("대사 검수 저장은 아직 api 스펙에 없습니다", 501)
