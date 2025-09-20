from django.contrib import admin
from .models import Note, NoteFlag, NoteCrosspost


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


@admin.register(NoteCrosspost)
class NoteCrosspostAdmin(admin.ModelAdmin):
    list_display = ("note", "network", "status", "short_remote", "created_at")
    list_filter = ("network", "status")
    search_fields = ("note__text", "remote_id", "remote_url")
    ordering = ("-created_at",)

    @admin.display(description="remote")
    def short_remote(self, obj):  # type: ignore[no-untyped-def]
        if obj.remote_url:
            return (obj.remote_url[:60] + "…") if len(obj.remote_url) > 60 else obj.remote_url
        if obj.remote_id:
            return obj.remote_id
        return "—"
