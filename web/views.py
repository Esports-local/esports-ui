import json
import re

from django.shortcuts import redirect, render
from django.utils.html import escape
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from . import api_client as api
from .api_client import ApiError


def _error(request, e):
    return render(request, "web/error.html", {"error": e.message}, status=e.status)


# ---------------------------------------------------------------- LoL 세트 영상

GAME_STATUS_LABELS = {"pending": "분석 전", "running": "분석 중", "done": "분석 완료", "failed": "실패"}
STAGE_LABELS = {"preprocess": "전처리", "segments": "화면 전환", "hls": "재생용 변환", "roi_ocr": "화면 OCR",
                "asr": "받아쓰기", "translate": "번역", "evaluate": "평가"}
ROLE_LABELS = {"top": "탑", "jungle": "정글", "mid": "미드", "bot": "원딜", "support": "서포터"}
SCREEN_TAGS = [("team_kills", "팀 킬"), ("kda", "KDA"), ("gold", "골드"), ("gold_diff", "골드 차이"),
               ("towers", "타워"), ("game_time", "게임 시간"), ("player_name", "선수 이름"), ("team", "팀")]
CONDITIONS = [("A", "대사만"), ("B", "+ 화면 OCR"), ("C", "+ 영상 프레임")]
JSON_STAGES = ["asr", "roi_ocr", "translate", "preprocess"]
GAME_TABS = [("lines", "대사·번역"), ("screen", "화면 OCR"), ("json", "원본 JSON")]


RUN_STAGES = [("preprocess", "전처리"), ("roi_ocr", "화면 OCR"), ("asr", "받아쓰기")]
# 번역 비용 예상에 쓰는 가정값 (Gemini Flash 등급 가격. 실제 가격과 다를 수 있음)
PRICE_IN_PER_M, PRICE_OUT_PER_M, OUT_TOKENS_PER_REQUEST = 0.5, 3.0, 120


def _cost(est):
    """입력 토큰(측정) + 출력 토큰(가정) → 예상 달러."""
    tokens_in = sum(est["input_tokens"].values())
    tokens_out = est["requests"] * OUT_TOKENS_PER_REQUEST
    usd = tokens_in / 1e6 * PRICE_IN_PER_M + tokens_out / 1e6 * PRICE_OUT_PER_M
    return {"tokens_in": tokens_in, "tokens_out": tokens_out, "usd": usd, "krw": round(usd * 1400, -1)}


def game_new(request):
    error = None
    if request.method == "POST":
        f = request.POST
        body = {"video": f.get("video"), "title": f.get("title"), "language": f.get("language", "ko"),
                "stages": f.getlist("stages") or None}
        if f.get("match") or f.get("set"):
            body.update(match=f.get("match"), set=f.get("set"))
        try:
            game = api.create_game(body)
            return redirect("game", game_id=game["id"])
        except ApiError as e:
            error = e.message
    try:
        sources = api.list_sources()
    except ApiError as e:
        return _error(request, e)
    return render(request, "web/game_new.html", {"sources": sources, "error": error, "run_stages": RUN_STAGES,
                                                 "form": request.POST if request.method == "POST" else None})


@require_POST
def game_action(request, game_id):
    """분석 실행 / 번역 실행 / 중지 → 세트 화면으로 돌아간다."""
    action = request.POST.get("action")
    try:
        if action == "analyze":
            api.analyze_game(game_id, request.POST.getlist("stages"))
        elif action == "translate":
            api.analyze_game(game_id, ["translate"], request.POST.getlist("conditions"))
        elif action == "cancel":
            api.cancel_game(game_id)
    except ApiError as e:
        return redirect(f"/games/{game_id}/?" + urlencode({"msg": e.message}))
    return redirect("game", game_id=game_id)


def games(request):
    try:
        items = api.list_games()
    except ApiError as e:
        return _error(request, e)
    for g in items:
        g["status_label"] = GAME_STATUS_LABELS.get(g["analyze_status"], g["analyze_status"])
    return render(request, "web/games.html", {"games": items})


def _roster(match):
    """경기 정보 → 포지션별 [역할, 블루 선수, 레드 선수] 행."""
    if not match:
        return []
    rows = []
    for role, label in ROLE_LABELS.items():
        blue = match["blue"]["players"].get(role)
        red = match["red"]["players"].get(role)
        if blue or red:
            rows.append({"role": label, "blue": blue, "red": red})
    return rows


def _known_names(match):
    """경기 정보의 선수·팀 이름 (번역문에서 형광펜으로 표시할 것)."""
    if not match:
        return []
    names = {match[side].get("team") for side in ("blue", "red")}
    for side in ("blue", "red"):
        for p in match[side]["players"].values():
            names.update({p.get("name"), p.get("champion")})
    return sorted((n for n in names if n), key=len, reverse=True)


def _highlight(text, names):
    """이름을 <mark> 로 감싼다. 대소문자까지 같을 때만 (on, knight 같은 일반 단어와 구분), 단어 경계 기준."""
    out = escape(text)
    if names:
        pattern = re.compile(r"\b(" + "|".join(re.escape(escape(n)) for n in names) + r")\b")
        out = pattern.sub(r"<mark>\1</mark>", out)
    return mark_safe(out)


def _translation_rows(line, names):
    """대사 하나의 [{key, label, html, same_as_a}] (번역이 없으면 빈 목록)."""
    trs = line.get("translations") or {}
    base = trs.get("A")
    rows = []
    for key, label in CONDITIONS:
        text = trs.get(key)
        if text is None:
            continue
        rows.append({"key": key, "label": label, "html": _highlight(text, names),
                     "same_as_a": key != "A" and text == base})
    return rows


def game_detail(request, game_id):
    tab = request.GET.get("tab", "lines")
    if tab not in dict(GAME_TABS):
        tab = "lines"
    try:
        game = api.get_game(game_id)
    except ApiError as e:
        return _error(request, e)
    for s in game["stages"]:
        s["label"] = STAGE_LABELS.get(s["stage"], s["stage"])
    ctx = {"game": game, "tab": tab, "tabs": GAME_TABS, "roster": _roster(game["match"]),
           "status_label": GAME_STATUS_LABELS.get(game["analyze_status"], game["analyze_status"]),
           "running": game["analyze_status"] == "running", "msg": request.GET.get("msg"),
           "run_stages": RUN_STAGES, "conditions": CONDITIONS,
           "done_stages": {s["stage"] for s in game["stages"] if s["status"] == "done"}}
    if game["progress"]:
        game["progress"]["label"] = STAGE_LABELS.get(game["progress"]["current_stage"] or "", "준비 중")
    raw = request.GET.getlist("cond") if "est" in request.GET else request.GET.get("estimate", "").split(",")
    est_conds = [c for c in ("A", "B", "C") if c in raw]
    if est_conds and not ctx["running"]:
        try:
            est = api.estimate_game(game_id, est_conds)
            ctx.update(estimate=est, cost=_cost(est), est_conds=est_conds)
        except ApiError as e:
            ctx["msg"] = e.message
    try:
        if tab == "lines":
            only = request.GET.get("only", "")
            lines = api.get_game_lines(game_id)
            n_translated = sum(1 for line in lines if line["translations"])
            if only == "translated":
                lines = [line for line in lines if line["translations"]]
            names = _known_names(game["match"])
            for line in lines:
                line["rows"] = _translation_rows(line, names)
            ctx.update(lines=lines, only=only, n_translated=n_translated, conditions=CONDITIONS)
        elif tab == "screen":
            tag = request.GET.get("tag", "team_kills")
            if tag not in dict(SCREEN_TAGS):
                tag = "team_kills"
            screen = api.get_game_screen(game_id, tag=tag)
            for r in screen["runs"]:
                r["dur"] = r["end_sec"] - r["start_sec"]
            ctx.update(screen=screen, tag=tag, screen_tags=SCREEN_TAGS)
        else:
            stage = request.GET.get("stage", "asr")
            if stage not in JSON_STAGES:
                stage = "asr"
            ctx.update(stage=stage, json_stages=JSON_STAGES,
                       raw=json.dumps(api.get_game_analysis(game_id, stage), ensure_ascii=False, indent=1))
    except ApiError as e:
        ctx["tab_error"] = e.message
    return render(request, "web/game.html", ctx)
