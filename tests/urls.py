from django.http import HttpResponse
from django.urls import path

from tests.test_views import BookView, CustomTemplateBookView


class GenreBookView(BookView):
    def get_initial_queryset(self, request):
        return super().get_initial_queryset(request).filter(genre=self.kwargs["genre"])


urlpatterns = [
    path("books/", BookView.as_view(), name="books-table"),
    path("books/<genre>/", GenreBookView.as_view(), name="genre-books-table"),
    path("custom/", CustomTemplateBookView.as_view(), name="custom-template-books-table"),
    path("hello/", lambda request: HttpResponse("hello"), name="not-a-table"),
]
