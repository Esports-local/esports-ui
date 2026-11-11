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
