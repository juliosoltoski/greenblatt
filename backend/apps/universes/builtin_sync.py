from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.db import transaction

from apps.core.providers import default_provider_config
from apps.universes.models import Universe, UniverseEntry
from apps.universes.services import ParsedTicker, UniverseInputError, resolve_builtin_profile_tickers
from apps.workspaces.models import Workspace
from greenblatt.services import ProviderConfig, build_provider
from greenblatt.universe import UniverseProfile, list_profiles


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BuiltInUniverseSyncResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)


def sync_builtin_universes(
    *,
    workspace: Workspace | None = None,
    provider_config: ProviderConfig | None = None,
) -> BuiltInUniverseSyncResult:
    result = BuiltInUniverseSyncResult()
    workspaces = [workspace] if workspace is not None else list(Workspace.objects.select_related("owner").all())
    profiles = list_profiles()
    active_provider = _build_live_profile_provider(profiles, provider_config=provider_config, result=result)

    for current_workspace in workspaces:
        for profile in profiles:
            _sync_profile_for_workspace(
                workspace=current_workspace,
                profile=profile,
                provider=active_provider,
                provider_config=provider_config,
                result=result,
            )
    return result


def safe_sync_builtin_universes_for_workspace(workspace: Workspace) -> None:
    try:
        sync_builtin_universes(workspace=workspace)
    except Exception:
        logger.exception("Built-in universe sync failed for workspace %s", workspace.id)


def _build_live_profile_provider(
    profiles: list[UniverseProfile],
    *,
    provider_config: ProviderConfig | None,
    result: BuiltInUniverseSyncResult,
):
    if not any(profile.requires_live_data for profile in profiles):
        return None
    try:
        return build_provider(
            provider_config
            or default_provider_config(
                use_cache=False,
                refresh_cache=True,
                cache_ttl_hours=1.0,
            )
        )
    except Exception as exc:
        result.errors.append(f"Unable to initialize the live market data provider for built-in sync: {exc}")
        return None


def _sync_profile_for_workspace(
    *,
    workspace: Workspace,
    profile: UniverseProfile,
    provider,
    provider_config: ProviderConfig | None,
    result: BuiltInUniverseSyncResult,
) -> None:
    if profile.requires_live_data and provider is None:
        result.errors.append(
            f"Skipped {profile.key} for workspace {workspace.slug}: live market data provider is unavailable."
        )
        return

    try:
        entries = resolve_builtin_profile_tickers(
            profile.key,
            provider_config=provider_config,
            provider=provider,
        )
    except UniverseInputError as exc:
        detail = "; ".join(exc.errors) if exc.errors else exc.detail
        result.errors.append(f"Skipped {profile.key} for workspace {workspace.slug}: {detail}")
        return

    with transaction.atomic():
        universe = (
            Universe.objects.select_for_update()
            .filter(
                workspace=workspace,
                source_type=Universe.SourceType.BUILT_IN,
                profile_key=profile.key,
                is_system_managed=True,
            )
            .order_by("id")
            .first()
        )
        if universe is None:
            universe = Universe.objects.create(
                workspace=workspace,
                created_by=workspace.owner,
                name=profile.label,
                description=profile.description,
                source_type=Universe.SourceType.BUILT_IN,
                profile_key=profile.key,
                is_system_managed=True,
                entry_count=len(entries),
            )
            UniverseEntry.objects.bulk_create(_build_entry_models(universe, entries))
            result.created += 1
            return

        if not universe.name.strip() or universe.name == universe.profile_key:
            universe.name = profile.label
        universe.description = profile.description
        universe.entry_count = len(entries)
        universe.save()
        universe.entries.all().delete()
        UniverseEntry.objects.bulk_create(_build_entry_models(universe, entries))
        result.updated += 1


def _build_entry_models(universe: Universe, entries: list[ParsedTicker]) -> list[UniverseEntry]:
    return [
        UniverseEntry(
            universe=universe,
            position=entry.position,
            raw_ticker=entry.raw_ticker,
            normalized_ticker=entry.normalized_ticker,
            inclusion_metadata=entry.inclusion_metadata,
        )
        for entry in entries
    ]
