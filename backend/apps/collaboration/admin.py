from django.contrib import admin

from apps.collaboration.models import ActivityEvent, ResourceComment, ResourceShareLink, WorkspaceCollection, WorkspaceCollectionItem


@admin.register(ResourceComment)
class ResourceCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "resource_kind", "resource_id", "author", "created_at")
    search_fields = ("body", "resource_kind", "resource_id", "author__username")
    list_filter = ("workspace", "resource_kind")


@admin.register(ResourceShareLink)
class ResourceShareLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "resource_kind", "resource_id", "access_scope", "created_by", "created_at", "revoked_at")
    search_fields = ("token", "label", "resource_kind", "resource_id")
    list_filter = ("workspace", "resource_kind", "access_scope")


class WorkspaceCollectionItemInline(admin.TabularInline):
    model = WorkspaceCollectionItem
    extra = 0


@admin.register(WorkspaceCollection)
class WorkspaceCollectionAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "name", "is_pinned", "created_by", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("workspace", "is_pinned")
    inlines = [WorkspaceCollectionItemInline]


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("id", "workspace", "verb", "resource_kind", "resource_id", "actor", "created_at")
    search_fields = ("verb", "summary", "resource_kind", "resource_id")
    list_filter = ("workspace", "resource_kind", "verb")

