from django.contrib import admin
from .models import Note, NoteFlag


class HasFlagsFilter(admin.SimpleListFilter):
    title = "has flags"
    parameter_name = "has_flags"

    def lookups(self, request, model_admin):
        return [("yes", "Yes"), ("no", "No")]

    def queryset(self, request, queryset):
        val = self.value()
        if val == "yes":
            return queryset.filter(flags__gt=0)
        if val == "no":
            return queryset.filter(flags=0)
        return queryset


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("short_text", "author", "pub_date", "views", "flags")
    search_fields = ("text", "author")
    list_filter = (HasFlagsFilter,)
    ordering = ("-flags", "-pub_date")

    @admin.display(description="text")
    def short_text(self, obj):
        return (obj.text[:80] + "…") if len(obj.text) > 80 else obj.text


@admin.register(NoteFlag)
class NoteFlagAdmin(admin.ModelAdmin):
    list_display = ("note", "device_id", "created_at")
    search_fields = ("device_id", "note__text")
    ordering = ("-created_at",)
