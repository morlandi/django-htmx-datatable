"""
{% htmx_datatable %}: show a table in a page (#7).

    {% load htmx_datatable %}
    {% htmx_datatable "books-table" %}
    {% htmx_datatable "author-books-table" pk=author.pk prefix="a" template="books/book_table.html" %}

The first argument is the URL name of the table's endpoint; the keyword
arguments other than prefix and template are the kwargs of that URL.
"""
from django.core.exceptions import ImproperlyConfigured
from django.template import Library
from django.template.loader import render_to_string
from django.urls import resolve, reverse

from ..views import HtmxDatatableView

register = Library()


@register.simple_tag(takes_context=True)
def htmx_datatable(context, url_name, *, prefix="", template="htmx_datatable/table.html", **kwargs):
    request = context.get("request")
    if request is None:
        raise ImproperlyConfigured(
            "{% htmx_datatable %} needs the request in the template context: add "
            "'django.template.context_processors.request' to the context processors"
        )
    url = reverse(url_name, kwargs=kwargs)
    match = resolve(url)
    view_class = getattr(match.func, "view_class", None)
    if not (isinstance(view_class, type) and issubclass(view_class, HtmxDatatableView)):
        raise ImproperlyConfigured(
            f"{{% htmx_datatable %}}: {url_name!r} is not the URL of an HtmxDatatableView"
        )
    table = view_class.embed(request, url=url, prefix=prefix, kwargs=match.kwargs)
    return render_to_string(template, {"table": table}, request=request)
