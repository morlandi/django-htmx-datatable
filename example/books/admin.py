from django.contrib import admin

from .models import Author, Book, Tag


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "birth_date"]
    search_fields = ["first_name", "last_name"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "genre", "published", "pages", "price", "available", "created"]
    list_filter = ["genre", "available", "tags"]
    search_fields = ["title", "author__first_name", "author__last_name"]
    filter_horizontal = ["tags"]
