# Changelog

## 0.1.0 (2026-11-17)

First usable version. Not on PyPI yet.

- Columns declared once on the view, bound and checked when the view class is
  defined: field paths across foreign keys, many-to-many, reverse relations and
  one-to-one; annotation and computed columns.
- Global search with a per-field type rule (text, numbers, dates as shown,
  choice labels); column filters, typed (exact match) or text (words);
  OR separator.
- Stable ordering (pk always last), `nulls_last` per column, default ordering
  on the view.
- Queryset optimization with `select_related` / `prefetch_related`.
- HTMX view: full page or out-of-band fragment; the table state lives in the
  query string, with a canonical URL in `HX-Replace-Url`; unstyled templates,
  meant to be overridden.
- Example project.

Known limits: single-column sort; `GenericForeignKey` not supported; on SQLite
`icontains` is case-insensitive for ASCII only.

## 0.0.1 (2026-11-15)

Placeholder release reserving the PyPI name.
