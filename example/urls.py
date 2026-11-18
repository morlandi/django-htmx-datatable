from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

# from example.books.views import BookTableView
from example.books.views import AuthorBookTableView, BookTableView, CompareView

urlpatterns = [
    # path("", BookTableView.as_view(), name="books"),
    path("", TemplateView.as_view(template_name="books/book_list.html"), name="books"),
    path("books/table/", BookTableView.as_view(), name="books-table"),
    path("compare/", CompareView.as_view(), name="compare"),
    path("authors/<int:pk>/books/table/", AuthorBookTableView.as_view(), name="author-books-table"),
    path("admin/", admin.site.urls),
]
