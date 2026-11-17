from django.contrib import admin
from django.urls import path

from example.books.views import BookTableView

urlpatterns = [
    path("", BookTableView.as_view(), name="books"),
    path("admin/", admin.site.urls),
]
