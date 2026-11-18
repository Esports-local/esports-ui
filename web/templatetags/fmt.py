from django import template

register = template.Library()


@register.filter
def tc(seconds):
    """초 → 12:14 (한 시간 넘으면 1:02:14)"""
    if seconds is None:
        return "-"
    total = int(float(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


@register.filter
def get(mapping, key):
    """dict 에서 key 값 (없으면 None). 템플릿에서 변수 key 로 꺼낼 때."""
    if not mapping:
        return None
    return mapping.get(key)


@register.filter
def pct(ratio):
    """0.875 → 88% (None 이면 -)"""
    return "-" if ratio is None else f"{round(float(ratio) * 100)}%"


@register.filter
def num(value):
    """1234567 → 1,234,567 (None 이면 -)"""
    return "-" if value is None else f"{value:,}"


@register.simple_tag
def static_v(path):
    """정적 파일 주소 + ?v=수정 시각. 파일이 바뀌면 주소가 바뀌어 브라우저가 옛 캐시를 쓰지 않는다."""
    import os
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static
    found = finders.find(path)
    return f"{static(path)}?v={int(os.path.getmtime(found)) if found else 0}"
