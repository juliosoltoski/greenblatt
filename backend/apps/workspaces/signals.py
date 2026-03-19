from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from apps.workspaces.models import Workspace, WorkspaceMembership


User = get_user_model()
logger = logging.getLogger(__name__)


def _build_personal_workspace_slug(base_text: str) -> str:
    base_slug = slugify(base_text) or "workspace"
    candidate = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


@receiver(post_save, sender=User)
def create_default_workspace_for_user(sender, instance, created, **kwargs) -> None:
    if not created:
        return
    base_name = instance.get_full_name().strip() or instance.username or f"user-{instance.pk}"
    workspace = Workspace.objects.create(
        owner=instance,
        name=f"{base_name} Workspace",
        slug=_build_personal_workspace_slug(f"{base_name}-workspace"),
        plan_type="personal",
        timezone="UTC",
    )
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=instance,
        role=WorkspaceMembership.Role.OWNER,
    )

    transaction.on_commit(lambda: _sync_builtins_after_workspace_create(workspace))


def _sync_builtins_after_workspace_create(workspace: Workspace) -> None:
    from apps.universes.builtin_sync import safe_sync_builtin_universes_for_workspace

    try:
        safe_sync_builtin_universes_for_workspace(workspace)
    except Exception:
        logger.exception("Workspace built-in universe sync failed for workspace %s", workspace.id)
