from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def qs_remove(context, key, value):
    request = context["request"]
    q = request.GET.copy()

    values = q.getlist(key)
    values = [v for v in values if v != str(value)]
    q.setlist(key, values)

    q.pop("page", None)

    encoded = q.urlencode()
    return f"?{encoded}" if encoded else ""

@register.simple_tag(takes_context=True)
def qs_add(context, key, value):

    request = context["request"]
    q = request.GET.copy()

    values = q.getlist(key)
    value = str(value)

    if value not in values:
        values.append(value)

    q.setlist(key, values)
    q.pop("page", None)

    encoded = q.urlencode()
    return f"?{encoded}" if encoded else ""
