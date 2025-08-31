from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import reverse
from .models import Note


# Create your views here.
def index(request):
    all_notes = Note.objects.order_by("-pub_date")
    context = {"latest_note_list": all_notes}
    return render(request, "aether_notes/index.html", context)


def create_note(request):
    if request.method == "POST":
        new_note = Note(
            text=request.POST["text"],
            author=request.POST.get("author", "anonymous"),
            pub_date=timezone.now(),
        )
        new_note.save()

    return redirect(reverse("index"))



def about(request):
    return render(request, "aether_notes/about.html")
