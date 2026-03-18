from __future__ import annotations

from apps.universes.models import Universe, UniverseEntry, UniverseUpload
from apps.workspaces.presenters import serialize_workspace


def serialize_upload(upload: UniverseUpload) -> dict[str, object | None]:
    return {
        "id": upload.id,
        "original_filename": upload.original_filename,
        "content_type": upload.content_type,
        "storage_backend": upload.storage_backend,
        "storage_key": upload.storage_key,
        "checksum_sha256": upload.checksum_sha256,
        "size_bytes": upload.size_bytes,
        "metadata": upload.metadata,
        "created_at": upload.created_at.isoformat(),
    }


def serialize_entry(entry: UniverseEntry) -> dict[str, object | None]:
    return {
        "id": entry.id,
        "position": entry.position,
        "raw_ticker": entry.raw_ticker,
        "normalized_ticker": entry.normalized_ticker,
        "inclusion_metadata": entry.inclusion_metadata,
    }


def serialize_universe(universe: Universe, *, include_entries: bool = False) -> dict[str, object | None]:
    payload: dict[str, object | None] = {
        "id": universe.id,
        "workspace": serialize_workspace(universe.workspace),
        "created_by_id": universe.created_by_id,
        "name": universe.name,
        "description": universe.description,
        "source_type": universe.source_type,
        "profile_key": universe.profile_key or None,
        "is_starred": universe.is_starred,
        "tags": universe.tags,
        "notes": universe.notes,
        "entry_count": universe.entry_count,
        "preview_tickers": [entry.normalized_ticker for entry in universe.entries.all()[:10]],
        "source_upload": serialize_upload(universe.source_upload) if universe.source_upload else None,
        "created_at": universe.created_at.isoformat(),
        "updated_at": universe.updated_at.isoformat(),
    }
    if include_entries:
        payload["entries"] = [serialize_entry(entry) for entry in universe.entries.all()]
    return payload
