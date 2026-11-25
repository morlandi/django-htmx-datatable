from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

# from example.books.views import BookTableView
from example.books.views import AuthorBookTableView, BookTableView, CompareView, spa_page

urlpatterns = [
    # path("", BookTableView.as_view(), name="books"),
    path("", TemplateView.as_view(template_name="books/book_list.html"), name="books"),
    path("books/table/", BookTableView.as_view(), name="books-table"),
    path("compare/", CompareView.as_view(), name="compare"),
    # A wide table in a small box, with a fixed header (#7)
    path("scroll/", TemplateView.as_view(template_name="books/scroll.html"), name="scroll"),
    path("authors/<int:pk>/books/table/", AuthorBookTableView.as_view(), name="author-books-table"),
    # A page without Django templates, with its client-side routes (#4)
    path("spa/", spa_page, name="spa"),
    path("spa/<path:route>", spa_page),
    path("admin/", admin.site.urls),
]
