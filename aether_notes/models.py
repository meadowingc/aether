import datetime

from django.db import models
from django.utils import timezone


# Create your models here.
class Note(models.Model):
    text = models.CharField(max_length=160)
    pub_date = models.DateTimeField("date published")
    author = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self) -> str:
        return self.text

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)
