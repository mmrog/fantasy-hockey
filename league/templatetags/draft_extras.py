# league/templatetags/draft_extras.py

from django import template

register = template.Library()


@register.filter
def first_attr(obj, names):
    """
    Try multiple attribute names (comma-separated) and return the first found.

    Usage:
      {{ p|first_attr:"team_abbr,nhl,nhl_abbr,team.abbr" }}
    """
    if not obj:
        return ""

    for name in names.split(","):
        cur = obj
        for part in name.strip().split("."):
            if not hasattr(cur, part):
                cur = None
                break
            cur = getattr(cur, part)
        if cur not in (None, ""):
            return cur

    return "—"
