# Changelog

## Unreleased

- Translations of the library's texts, shipped in the package: `ar`, `bn`,
  `cs`, `da`, `de`, `el`, `es`, `fa`, `fi`, `fr`, `hu`, `id`, `it`, `kk`,
  `ms`, `nl`, `pl`, `pt`, `pt_BR`, `ro`, `ru`, `sv`, `th`, `tr`, `uk`, `ur`,
  `zh_Hans`. English stays the default. Projects that overrode the templates only to translate
  them can drop the overrides (#5).
- README: translations, and how a page without Django templates tells the
  endpoint its language (#5).
- `table_template_name`, a view attribute: the template of the whole table,
  used by the endpoint's plain GET and by `{% htmx_datatable %}` without
  `template=`. The default, `htmx_datatable/table.html`, does not change
  (#6).

## 0.2.4 (2026-11-24)

Documentation:

- README: how to show a table without the template tag, with `embed()`
  (step 9).
- README: pages without Django templates, as in a single-page application
  (React, ...): how to load a table and why the htmx history must be left to
  the router; the example project has such a page, `/spa/` (#4).

## 0.2.3 (2026-11-24)

- Python >= 3.8 (was 3.12): Python 3.8 is supported with Django 4.2 and
  tested in CI. The support is temporary and will be dropped in a future
  release. pip no longer needs `--ignore-requires-python`.

## 0.2.2 (2026-11-20)

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
