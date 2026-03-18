from django.contrib import admin

from apps.workspaces.models import Workspace, WorkspaceMembership


class WorkspaceMembershipInline(admin.TabularInline):
    model = WorkspaceMembership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "owner", "plan_type", "timezone", "created_at"]
    search_fields = ["name", "slug", "owner__username", "owner__email"]
    list_filter = ["plan_type", "timezone"]
    inlines = [WorkspaceMembershipInline]


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ["workspace", "user", "role", "joined_at"]
    list_filter = ["role"]
    search_fields = ["workspace__name", "workspace__slug", "user__username", "user__email"]
    autocomplete_fields = ["workspace", "user"]
