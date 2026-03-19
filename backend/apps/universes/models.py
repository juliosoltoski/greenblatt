from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.workspaces.models import Workspace


class UniverseUpload(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="universe_uploads")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="universe_uploads",
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255, blank=True)
    storage_backend = models.CharField(max_length=50, default="filesystem")
    storage_key = models.CharField(max_length=500, unique=True)
    checksum_sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.original_filename


class Universe(models.Model):
    class SourceType(models.TextChoices):
        BUILT_IN = "built_in", "Built-in"
        MANUAL = "manual", "Manual"
        UPLOADED_FILE = "uploaded_file", "Uploaded file"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="universes")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_universes",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    profile_key = models.CharField(max_length=100, blank=True)
    source_upload = models.ForeignKey(
        UniverseUpload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_universes",
    )
    is_system_managed = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    entry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self) -> str:
        return self.name


class UniverseEntry(models.Model):
    universe = models.ForeignKey(Universe, on_delete=models.CASCADE, related_name="entries")
    position = models.PositiveIntegerField()
    raw_ticker = models.CharField(max_length=32)
    normalized_ticker = models.CharField(max_length=32)
    inclusion_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["universe", "position"], name="uniq_universe_entry_position"),
            models.UniqueConstraint(fields=["universe", "normalized_ticker"], name="uniq_universe_entry_ticker"),
        ]

    def __str__(self) -> str:
        return f"{self.universe_id}:{self.normalized_ticker}"
