from django.contrib import admin

from apps.universes.models import Universe, UniverseEntry, UniverseUpload


class UniverseEntryInline(admin.TabularInline):
    model = UniverseEntry
    extra = 0
    fields = ["position", "raw_ticker", "normalized_ticker"]
    readonly_fields = ["position", "raw_ticker", "normalized_ticker"]
    show_change_link = False


@admin.register(Universe)
class UniverseAdmin(admin.ModelAdmin):
    list_display = ["name", "workspace", "source_type", "profile_key", "entry_count", "updated_at"]
    list_filter = ["source_type", "workspace"]
    search_fields = ["name", "description", "profile_key", "workspace__name", "workspace__slug"]
    autocomplete_fields = ["workspace", "created_by", "source_upload"]
    inlines = [UniverseEntryInline]


@admin.register(UniverseUpload)
class UniverseUploadAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "workspace", "storage_backend", "size_bytes", "created_at"]
    list_filter = ["storage_backend", "workspace"]
    search_fields = ["original_filename", "storage_key", "checksum_sha256", "workspace__name"]
    autocomplete_fields = ["workspace", "created_by"]


@admin.register(UniverseEntry)
class UniverseEntryAdmin(admin.ModelAdmin):
    list_display = ["normalized_ticker", "universe", "position"]
    list_filter = ["universe__workspace"]
    search_fields = ["normalized_ticker", "raw_ticker", "universe__name"]
    autocomplete_fields = ["universe"]
