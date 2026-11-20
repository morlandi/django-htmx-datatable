# Changelog

## Unreleased

Fixed:

- Enter in the search box or in a text filter sorted the table by its first
  sortable column (#1).
- The browser no longer suggests past values in the search box and the filters.

## 0.2.1 (2026-11-20)

- Django >= 4.2 (was 5.1).
- Partial, temporary support for Python 3.8 and Django 4.2, for projects that
  cannot upgrade yet; see the README for the installation. The declared
  Python requirement (>= 3.12) does not change.

## 0.2.0 (2026-11-18)

Breaking changes:

- A view is a table and its htmx endpoint, no longer a page:
  `template_name` is removed. Show the table in any page with
  `{% htmx_datatable "url-name" %}` or `embed()`; see the README.
- The `prefix` class attribute is removed: pass `prefix=` to the tag or to
  `embed()`. A prefix is made of ASCII letters and digits.
- Element ids start with `dt-<prefix>` instead of `<prefix>`.

Added:

- Several tables on one page, also of the same class (GitLab issue #7).
- The form's action is the page: a submit without JavaScript reloads it.

## 0.1.1 (2026-11-18)

First release on PyPI.

- README rewritten as a step-by-step tutorial, with screenshots.
- Removed `Column(initial_search_value=...)`: it was never used. To open a
  table already filtered, link to its URL with the query string, or redirect
  to it (see the README).
- Example project: a few hundred Italian classics (`loaddata books`), British
  English as language; the tests use the small `books_test` fixture.

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
