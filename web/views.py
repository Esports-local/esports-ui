import json

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import api_client as api
from .api_client import ApiError

CATEGORY_LABELS = {
    "action": "행동", "discovery": "발견", "conflict": "갈등",
    "relationship": "관계", "twist": "반전", "resolution": "해결",
}
SCENE_TYPE_LABELS = {
    "talk": "대화", "action": "행동", "reaction": "반응",
    "transition": "전환", "montage": "몽타주", "mixed": "복합",
}
STATUS_LABELS = {
    "idle": "분석 전", "queued": "대기 중", "running": "분석 중", "done": "분석 완료", "failed": "실패",
}


def _error(request, e):
    return render(request, "web/error.html", {"error": e.message}, status=e.status)


def _targets(episodes):
    """예측할 수 있는 회차 번호. 1화부터 이어서 분석 완료인 회차 다음까지."""
    done = {ep["number"] for ep in episodes if ep["analyze_status"] == "done"}
    last = 0
    while last + 1 in done:
        last += 1
    return list(range(2, last + 2))


def home(request):
    try:
        series = api.list_series()
    except ApiError as e:
        return _error(request, e)
    return render(request, "web/home.html", {"series": series})


def series_detail(request, series_id):
    try:
        series = api.get_series(series_id)
    except ApiError as e:
        return _error(request, e)
    for ep in series["episodes"]:
        ep["status_label"] = STATUS_LABELS.get(ep["analyze_status"], ep["analyze_status"])
    targets = _targets(series["episodes"])
    return render(request, "web/series.html", {"series": series, "targets": targets})


def _scene_lookup(episode_id, cache):
    """회차의 scene id → scene. 분석 결과가 없으면 빈 dict."""
    if episode_id not in cache:
        try:
            analysis = api.get_analysis(episode_id)
            cache[episode_id] = {s["id"]: s for s in analysis["scenes"]}
        except ApiError:
            cache[episode_id] = {}
    return cache[episode_id]


def predict(request, series_id):
    if request.method == "POST":
        target = request.POST.get("target", "")
        try:
            api.start_predict(series_id, int(target))
        except ValueError:
            return _error(request, ApiError("회차를 골라 주세요", 400))
        except ApiError as e:
            return _error(request, e)
        return redirect(f"{request.path}?target={target}")

    try:
        target = int(request.GET.get("target", ""))
    except ValueError:
        return redirect("series", series_id=series_id)
    try:
        series = api.get_series(series_id)
        result = api.get_predict(series_id, target)
    except ApiError as e:
        return _error(request, e)

    # 상태 폴링 (htmx): 끝나면 전체 새로고침
    if request.headers.get("HX-Request"):
        if result["status"] in ("done", "failed"):
            resp = HttpResponse("")
            resp["HX-Refresh"] = "true"
            return resp
        return render(request, "web/_predict_status.html", {"result": result, "series": series})

    characters = {c["id"]: c["name"] for c in series["characters"]}
    episodes = {}
    scene_cache = {}
    for item in result["items"]:
        item["category_label"] = CATEGORY_LABELS.get(item["category"], item["category"])
        item["character_names"] = [characters.get(cid, f"#{cid}") for cid in item["characters"]]
        item["confidence_pct"] = round(item["confidence"] * 100)
        for kind in ("evidence", "counter_evidence"):
            for ev in item[kind]:
                eid = ev["episode_id"]
                if eid not in episodes:
                    try:
                        episodes[eid] = api.get_episode(eid)
                    except ApiError:
                        episodes[eid] = {"id": eid, "number": "?", "play_url": None}
                ev["episode"] = episodes[eid]
                ev["scene"] = _scene_lookup(eid, scene_cache).get(ev["scene_id"])

    return render(request, "web/predict.html", {
        "series": series, "result": result, "target": target,
        "targets": _targets(series["episodes"]),
    })


def episode_review(request, episode_id):
    try:
        episode = api.get_episode(episode_id)
        series = api.get_series(episode["series_id"])
    except ApiError as e:
        return _error(request, e)

    analysis, analysis_error = None, None
    try:
        analysis = api.get_analysis(episode_id)
    except ApiError as e:
        analysis_error = e.message

    ctx = {
        "episode": episode, "series": series, "analysis_error": analysis_error,
        "status_label": STATUS_LABELS.get(episode["analyze_status"], episode["analyze_status"]),
        "tab": "json" if request.GET.get("tab") == "json" else "review",
    }
    if analysis:
        reviews = api.get_line_reviews(episode_id)
        scenes = [{
            "id": s["id"], "start": s["start_sec"], "end": s["end_sec"],
            "type": s["type"], "type_label": SCENE_TYPE_LABELS.get(s["type"], s["type"]),
            "summary": s["summary"], "keywords": s.get("keywords", []), "faces": s.get("faces", []),
            "black_before": s.get("black_before", False),
            "lines": [{
                "index": i, "start": line["start_sec"], "end": line["end_sec"],
                "speaker": line["speaker"], "text": line["text"],
                "review": reviews.get(f"{s['id']}:{i}"),
            } for i, line in enumerate(s["lines"])],
        } for s in analysis["scenes"]]
        ctx.update({
            "analysis": analysis,
            "line_count": sum(len(s["lines"]) for s in scenes),
            "raw_json": json.dumps(analysis, ensure_ascii=False, indent=2),
            "studio": {
                "episode": {"id": episode["id"], "title": episode["title"], "play_url": episode["play_url"],
                            "duration": analysis["duration_sec"]},
                "scenes": scenes,
                "review_url": f"/episodes/{episode_id}/lines/",
            },
        })
    return render(request, "web/episode.html", ctx)


@require_POST
def review_line(request, episode_id, scene_id, index):
    """대사 판정 저장. 응답 {"review": {verdict, text} | null} 또는 {"error"}"""
    verdict = request.POST.get("verdict", "")
    text = request.POST.get("text", "").strip() or None
    try:
        review = api.save_line_review(episode_id, scene_id, index, verdict, text)
    except ApiError as e:  # 대사 없음(404)·고친 대사 누락(400) 검사는 api가 한다
        return JsonResponse({"error": e.message}, status=e.status)
    return JsonResponse({"review": review})
