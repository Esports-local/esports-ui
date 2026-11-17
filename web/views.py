import difflib
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
LINE_FILTERS = [("", "전체"), ("unreviewed", "미검수 (X)"), ("edited", "고친 대사"), ("translated", "번역한 대사")]


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


def _diff(before, after):
    """(ASR 원문 html, 고친 문장 html). 지운 글자는 <del>, 넣은 글자는 <ins>."""
    old, new = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        a, b = escape(before[i1:i2]), escape(after[j1:j2])
        if op == "equal":
            old.append(a)
            new.append(b)
            continue
        if a:
            old.append(f"<del>{a}</del>")
        if b:
            new.append(f"<ins>{b}</ins>")
    return mark_safe("".join(old)), mark_safe("".join(new))


def _filter_lines(lines, only):
    if only == "unreviewed":
        return [x for x in lines if not (x["review"] or {}).get("reviewed")]
    if only == "edited":
        return [x for x in lines if (x["review"] or {}).get("text")]
    if only == "translated":
        return [x for x in lines if x["translations"]]
    return lines


@require_POST
def line_review(request, game_id, line_id):
    """대사 검수 저장 → 같은 대사 위치로 돌아간다.

    action: mark(검수 O/X 바꾸기) · save(고친 문장 저장, check 가 있으면 O 도) · revert(ASR 원문으로 되돌리기)
    """
    f = request.POST
    action = f.get("action")
    try:
        if action == "mark":
            api.review_line(game_id, line_id, reviewed=f.get("reviewed") == "1")
        elif action == "save":
            api.review_line(game_id, line_id, text=f.get("text", ""), reviewed=True if f.get("check") else None)
        elif action == "revert":
            api.review_line(game_id, line_id, text=f.get("asr_text", ""))
        msg = None
    except ApiError as e:
        msg = e.message
    query = {"tab": "lines", **({"only": f["only"]} if f.get("only") else {}), **({"msg": msg} if msg else {})}
    return redirect(f"/games/{game_id}/?{urlencode(query)}#line-{line_id}")


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
            if only not in dict(LINE_FILTERS):
                only = ""
            all_lines = api.get_game_lines(game_id)
            counts = {"all": len(all_lines),
                      "translated": sum(1 for x in all_lines if x["translations"]),
                      "reviewed": sum(1 for x in all_lines if (x["review"] or {}).get("reviewed")),
                      "edited": sum(1 for x in all_lines if (x["review"] or {}).get("text"))}
            lines = _filter_lines(all_lines, only)
            names = _known_names(game["match"])
            for line in lines:
                line["rows"] = _translation_rows(line, names)
                review = line["review"] or {}
                line["reviewed"] = bool(review.get("reviewed"))
                line["fixed"] = review.get("text")
                if line["fixed"]:
                    line["asr_html"], line["fixed_html"] = _diff(line["text"], line["fixed"])
            ctx.update(lines=lines, only=only, counts=counts, line_filters=LINE_FILTERS, conditions=CONDITIONS)
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


# ---------------------------------------------------------------- Claude Code 스킬 사용·선택 평가

JOB_STATUS_LABELS = {"queued": "대기 중", "running": "실행 중", "done": "완료", "failed": "실패", "cancelled": "중지됨"}
EVAL_MODELS = ["sonnet", "haiku"]
EVAL_REPEATS = [1, 2, 3]
CASES_PER_SKILL = 12  # dev-workflow evals/cases: 스킬마다 요청 12개 (화면에서 추가하면 늘어난다)
EVAL_REPOS = ["esports-analyzer", "esports-api", "esports-ui"]
# 평가 결과에 붙이는 이름 후보. 실제 이름은 "<후보>-<모델>" (예: baseline-sonnet). 설명을 고친 뒤에는 after-N 으로 돌려 비교한다
EVAL_LABELS = [("baseline", "기준 (지금 설명)"), ("after-1", "수정 후 1차"), ("after-2", "수정 후 2차"),
               ("after-3", "수정 후 3차"), ("recheck", "다시 재기 (확인용)")]
EVAL_SCOPES = [("all", "전체 요청"), ("failed", "지금 보는 결과에서 틀린 요청만")]
SAME_SKILL = "same"  # 테스트 요청 추가: 기대 스킬 = 시험하는 스킬


def _short(skill):
    """esports-dev:local-up → local-up"""
    return (skill or "").split(":")[-1]


def skills(request):
    """스킬별 사용 기록과 선택 평가 결과, 틀린 요청 목록, 평가 실행."""
    batch, skill = request.GET.get("batch") or None, request.GET.get("skill") or None
    compare = request.GET.get("compare") or None
    try:
        data = api.get_skills(batch, compare)
        tries = api.list_improve_tries(skill)
        cases = api.get_skill_evals(data["batch"], skill) if data["batch"] else []
        jobs = api.list_eval_jobs()
        all_cases = api.list_eval_cases()
    except ApiError as e:
        return _error(request, e)
    for s in data["skills"]:
        s["name"] = _short(s["skill"])
        if s["eval"] and s["eval"]["recall"] is not None:
            s["eval"]["recall_width"] = round(s["eval"]["recall"] * 100)
        a, b = (s["eval"] or {}).get("recall"), (s["compare"] or {}).get("recall")
        s["recall_diff"] = None if a is None or b is None else round((a - b) * 100)
    for t in tries:
        t["name"] = _short(t["skill"])
    for c in cases:
        c["expect_name"] = _short(c["expect"]) or "스킬 없음"
        c["bad"] = c["miss"] + c["wrong"]
        c["did_text"] = ", ".join(f"{_short(d['name'])} {d['count']}번" for d in c["did"])
    known = sorted({c["skill"] for c in all_cases} | {s["skill"] for s in data["skills"]})
    added = [c for c in all_cases if c["origin"] == "ui"]
    for c in added:
        c["skill_name"], c["expect_name"] = _short(c["skill"]), _short(c["expect"]) or "스킬 없음"
    job = data["job"]
    last = next((j for j in jobs if j["status"] not in ("queued", "running")), None)
    for j in (job, last):
        if j:
            j["status_label"] = JOB_STATUS_LABELS.get(j["status"], j["status"])
            j["skills_text"] = ", ".join(j["skills"]) or "전체"
    return render(request, "web/skills.html", {
        "data": data, "totals": data["totals"], "cases": cases, "skill": skill, "skill_name": _short(skill),
        "job": job, "last_job": last, "models": EVAL_MODELS, "repeats": EVAL_REPEATS,
        "cases_per_skill": CASES_PER_SKILL, "error": request.GET.get("error"),
        "skill_options": [(s, _short(s)) for s in known], "repos": EVAL_REPOS, "added": added,
        "labels": EVAL_LABELS, "same_skill": SAME_SKILL, "scopes": EVAL_SCOPES, "tries": tries,
        "compare": data.get("compare"),
        "case_count": len(all_cases),
        "query": urlencode({"batch": data["batch"]}) if batch else ""})


@require_POST
def skills_action(request):
    """평가 실행 요청 / 중지, 테스트 요청 추가 / 정답 바꾸기 / 빼기 → 스킬 화면으로 돌아간다."""
    f = request.POST
    try:
        if f.get("action") == "cancel":
            api.cancel_eval_job(f.get("job_id"))
        elif f.get("action") in ("edit_case", "remove_case"):
            api.update_eval_case(f.get("case_id", ""), expect=f.get("expect", ""),
                                 remove=f.get("action") == "remove_case")
            back = f.get("back", "")
            return redirect(back if back.startswith("/skills/") else "skills")  # 거르던 스킬·결과 이름 그대로
        elif f.get("action") == "add_case":
            skill = f.get("skill", "")
            expect = skill if f.get("expect") == SAME_SKILL else f.get("expect", "")
            api.create_eval_case({"skill": skill, "expect": expect, "kind": "should" if expect == skill else "should_not",
                                  **{k: f.get(k, "") for k in ("split", "repo", "prompt")}})
        else:
            model = f.get("model", "sonnet")
            if f.get("label") not in dict(EVAL_LABELS):
                raise ValueError
            case_ids = []
            if f.get("scope") == "failed":  # 지금 보는 결과(source)에서 틀린 적 있는 요청만 다시 돌린다
                failed = api.get_skill_evals(f.get("source") or None, f.get("skill") or None, "failed")
                case_ids = [c["id"] for c in failed]
                if not case_ids:
                    raise ApiError("다시 돌릴 틀린 요청이 없습니다", 400)
            api.create_eval_job(f"{f['label']}-{model}", [f["skill"]] if f.get("skill") else [],
                                int(f.get("repeat") or 1), model, case_ids)
    except (ApiError, ValueError) as e:
        return redirect(f"/skills/?{urlencode({'error': getattr(e, 'message', '입력값이 올바르지 않습니다')})}")
    return redirect("skills")
