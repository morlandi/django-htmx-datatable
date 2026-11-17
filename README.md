# django-htmx-datatable

Searchable, sortable, filterable, paginated tables for Django models,
declared once on the server and rendered as HTML with [htmx](https://htmx.org).

Successor of [django-ajax-datatable](https://github.com/morlandi/django-ajax-datatable),
without jQuery and datatables.net.

## Status

0.1: first usable version, not on PyPI yet; the API may still change before 1.0.
Changes: [CHANGELOG.md](CHANGELOG.md).

Design decisions and roadmap: [docs/2026-11-15_design.md](docs/2026-11-15_design.md).

## Requirements

- Python >= 3.12
- Django >= 5.1
- htmx 2.x

## Example project

```
cd example
python manage.py migrate
python manage.py loaddata books
python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## License

MIT
