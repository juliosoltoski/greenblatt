from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.workspaces.models import Workspace


def generate_share_token() -> str:
    return secrets.token_urlsafe(24)


class CollaborationResourceKind(models.TextChoices):
    STRATEGY_TEMPLATE = "strategy_template", "Strategy template"
    RUN_SCHEDULE = "run_schedule", "Run schedule"
    SCREEN_RUN = "screen_run", "Screen run"
    BACKTEST_RUN = "backtest_run", "Backtest run"


class ReviewStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In review"
    APPROVED = "approved", "Approved"
    CHANGES_REQUESTED = "changes_requested", "Changes requested"


class ResourceComment(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="resource_comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_comments",
    )
    resource_kind = models.CharField(max_length=32, choices=CollaborationResourceKind.choices)
    resource_id = models.PositiveIntegerField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["workspace", "resource_kind", "resource_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.resource_kind}:{self.resource_id}:{self.pk}"


class ResourceShareLink(models.Model):
    class AccessScope(models.TextChoices):
        WORKSPACE_MEMBER = "workspace_member", "Workspace member"
        TOKEN = "token", "Anyone with the link"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="resource_share_links")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_share_links",
    )
    resource_kind = models.CharField(max_length=32, choices=CollaborationResourceKind.choices)
    resource_id = models.PositiveIntegerField()
    label = models.CharField(max_length=255, blank=True)
    token = models.CharField(max_length=255, unique=True, default=generate_share_token)
    access_scope = models.CharField(max_length=32, choices=AccessScope.choices, default=AccessScope.TOKEN)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "resource_kind", "resource_id", "created_at"]),
            models.Index(fields=["workspace", "revoked_at", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.resource_kind}:{self.resource_id}:{self.token}"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_expired


class WorkspaceCollection(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="collections")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workspace_collections",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "name", "id"]
        indexes = [
            models.Index(fields=["workspace", "is_pinned", "updated_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class WorkspaceCollectionItem(models.Model):
    collection = models.ForeignKey(WorkspaceCollection, on_delete=models.CASCADE, related_name="items")
    resource_kind = models.CharField(max_length=32, choices=CollaborationResourceKind.choices)
    resource_id = models.PositiveIntegerField()
    note = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "resource_kind", "resource_id"],
                name="uniq_collection_item_resource",
            ),
        ]
        indexes = [
            models.Index(fields=["collection", "position"]),
        ]

    def __str__(self) -> str:
        return f"{self.collection_id}:{self.resource_kind}:{self.resource_id}"


class ActivityEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="activity_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_events",
    )
    resource_kind = models.CharField(max_length=32, choices=CollaborationResourceKind.choices)
    resource_id = models.PositiveIntegerField()
    verb = models.CharField(max_length=64)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["workspace", "resource_kind", "resource_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.workspace_id}:{self.verb}:{self.resource_kind}:{self.resource_id}"

