"""
Models of the example project, shared with the test suite.

They cover the field kinds the library has to deal with: text, numbers, dates and
datetimes, booleans, choices, FK (nullable, to exercise NULL relations in a field
path) and M2M.
"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Author(models.Model):
    first_name = models.CharField(_("first name"), max_length=100)
    last_name = models.CharField(_("last name"), max_length=100)
    birth_date = models.DateField(_("birth date"), null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class AuthorProfile(models.Model):
    author = models.OneToOneField(
        Author,
        verbose_name=_("author"),
        on_delete=models.CASCADE,
        related_name="profile",
    )
    website = models.URLField(_("website"), blank=True)

    def __str__(self):
        return f"{self.author} profile"


class Tag(models.Model):
    name = models.CharField(_("name"), max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):

    class Genre(models.TextChoices):
        NOVEL = "novel", _("Novel")
        SHORT_STORIES = "short_stories", _("Short stories")
        ESSAY = "essay", _("Essay")
        POETRY = "poetry", _("Poetry")

    title = models.CharField(_("title"), max_length=200)
    author = models.ForeignKey(
        Author,
        verbose_name=_("author"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="books",
    )
    tags = models.ManyToManyField(Tag, verbose_name=_("tags"), blank=True, related_name="books")
    genre = models.CharField(_("genre"), max_length=20, choices=Genre.choices)
    published = models.DateField(_("published"), null=True, blank=True)
    pages = models.PositiveIntegerField(_("pages"))
    price = models.DecimalField(_("price"), max_digits=8, decimal_places=2)
    available = models.BooleanField(_("available"), default=True)
    created = models.DateTimeField(_("created"), default=timezone.now)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
