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
