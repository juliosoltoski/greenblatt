from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from apps.universes.models import Universe, UniverseEntry, UniverseUpload
from apps.workspaces.models import Workspace
from greenblatt.providers.base import MarketDataProvider
from greenblatt.providers.yahoo import YahooFinanceProvider
from greenblatt.universe import list_profiles, resolve_profile


MAX_TICKER_COUNT = 10_000
MAX_UPLOAD_BYTES = 1_000_000
TICKER_PATTERN = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,24}$")
IGNORED_HEADER_VALUES = {"ticker", "tickers", "symbol", "symbols"}


class UniverseInputError(ValueError):
    def __init__(self, detail: str, errors: list[str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []


@dataclass(frozen=True, slots=True)
class ParsedTicker:
    position: int
    raw_ticker: str
    normalized_ticker: str
    inclusion_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    storage_backend: str
    storage_key: str
    checksum_sha256: str
    size_bytes: int


class _StaticProfileProvider(MarketDataProvider):
    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        raise NotImplementedError

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        raise NotImplementedError

    def get_us_equity_candidates(self, *, limit=3_000):
        raise RuntimeError("The requested profile must be resolved dynamically.")


class ArtifactStorage:
    def __init__(self, *, root: str | Path | None = None, backend: str | None = None) -> None:
        self.root = Path(root or settings.ARTIFACT_STORAGE_ROOT)
        self.backend = backend or settings.ARTIFACT_STORAGE_BACKEND

    def store_artifact(
        self,
        *,
        workspace: Workspace,
        category: str,
        original_filename: str,
        content: bytes,
    ) -> StoredArtifact:
        if self.backend != "filesystem":
            raise RuntimeError(f"Unsupported artifact storage backend: {self.backend}")

        suffix = Path(original_filename or "artifact.bin").suffix.lower() or ".bin"
        storage_key = (
            Path(category)
            / str(workspace.id)
            / timezone.now().strftime("%Y/%m/%d")
            / f"{uuid4().hex}{suffix}"
        )
        destination = self.root / storage_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredArtifact(
            storage_backend=self.backend,
            storage_key=storage_key.as_posix(),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    def store_universe_upload(self, *, workspace: Workspace, original_filename: str, content: bytes) -> StoredArtifact:
        return self.store_artifact(
            workspace=workspace,
            category="universes",
            original_filename=original_filename,
            content=content,
        )

    def resolve_path(self, storage_key: str) -> Path:
        if self.backend != "filesystem":
            raise RuntimeError(f"Unsupported artifact storage backend: {self.backend}")
        return self.root / storage_key


def flatten_errors(value) -> list[str]:
    if isinstance(value, dict):
        messages: list[str] = []
        for field, item in value.items():
            for nested in flatten_errors(item):
                if field == "detail":
                    messages.append(nested)
                else:
                    messages.append(f"{field}: {nested}")
        return messages
    if isinstance(value, list):
        messages: list[str] = []
        for item in value:
            messages.extend(flatten_errors(item))
        return messages
    return [str(value)]


def list_builtin_profile_payloads() -> list[dict[str, object | None]]:
    payloads: list[dict[str, object | None]] = []
    static_provider = _StaticProfileProvider()
    for profile in list_profiles():
        preview_tickers: list[str] = []
        estimated_entry_count: int | None = None
        resolution_note: str | None = None
        if profile.key == "us_top_3000":
            estimated_entry_count = 3_000
            resolution_note = "Resolved from live market data when the universe is created."
        else:
            tickers = resolve_profile(static_provider, profile.key)
            preview_tickers = tickers[:10]
            estimated_entry_count = len(tickers)
        payloads.append(
            {
                "key": profile.key,
                "description": profile.description,
                "source": profile.source,
                "estimated_entry_count": estimated_entry_count,
                "preview_tickers": preview_tickers,
                "resolution_note": resolution_note,
            }
        )
    return payloads


def _normalize_ticker(raw: str) -> str:
    normalized = YahooFinanceProvider._normalize_symbol(raw.strip())
    if not normalized:
        raise UniverseInputError("Universe input contains invalid tickers.", ["Blank ticker values are not allowed."])
    if not TICKER_PATTERN.fullmatch(normalized):
        raise UniverseInputError(
            "Universe input contains invalid tickers.",
            [f"Ticker '{raw}' contains unsupported characters."],
        )
    return normalized


def parse_ticker_text(text: str) -> list[ParsedTicker]:
    entries: list[ParsedTicker] = []
    seen: set[str] = set()
    errors: list[str] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        tokens = [token for token in re.split(r"[\s,]+", line) if token]
        if line_number == 1 and len(tokens) == 1 and tokens[0].strip().lower() in IGNORED_HEADER_VALUES:
            continue
        for token in tokens:
            try:
                normalized = _normalize_ticker(token)
            except UniverseInputError:
                errors.append(f"Line {line_number}: '{token}' is not a supported ticker symbol.")
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            entries.append(
                ParsedTicker(
                    position=len(entries) + 1,
                    raw_ticker=token.strip(),
                    normalized_ticker=normalized,
                    inclusion_metadata={"line_number": line_number},
                )
            )
            if len(entries) > MAX_TICKER_COUNT:
                raise UniverseInputError(
                    "Universe input exceeds the maximum supported ticker count.",
                    [f"Limit the universe to at most {MAX_TICKER_COUNT} unique tickers."],
                )

    if errors:
        raise UniverseInputError("Universe input contains invalid tickers.", errors)
    if not entries:
        raise UniverseInputError("No tickers were found in the submitted universe.")
    return entries


def parse_uploaded_ticker_file(upload_file: UploadedFile) -> tuple[list[ParsedTicker], bytes]:
    if upload_file.size and upload_file.size > MAX_UPLOAD_BYTES:
        raise UniverseInputError(
            "The uploaded file is too large.",
            [f"Upload a text file smaller than {MAX_UPLOAD_BYTES} bytes."],
        )

    raw_bytes = upload_file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UniverseInputError("Uploaded files must be UTF-8 text.", [str(exc)]) from exc
    return parse_ticker_text(text), raw_bytes


def resolve_builtin_profile_tickers(profile_key: str) -> list[ParsedTicker]:
    profile_index = {profile.key: profile for profile in list_profiles()}
    if profile_key not in profile_index:
        raise UniverseInputError("Unknown built-in universe profile.", [f"Unknown profile key: {profile_key}"])

    if profile_key == "us_top_3000":
        provider: MarketDataProvider = YahooFinanceProvider()
    else:
        provider = _StaticProfileProvider()

    try:
        tickers = resolve_profile(provider, profile_key)
    except Exception as exc:
        raise UniverseInputError(
            "Unable to resolve the selected built-in profile.",
            [str(exc)],
        ) from exc

    return [
        ParsedTicker(
            position=index,
            raw_ticker=ticker,
            normalized_ticker=ticker,
            inclusion_metadata={"profile_key": profile_key},
        )
        for index, ticker in enumerate(dict.fromkeys(tickers), start=1)
    ]


class UniverseManagerService:
    def __init__(self, *, storage: ArtifactStorage | None = None) -> None:
        self.storage = storage or ArtifactStorage()

    def create_universe(
        self,
        *,
        workspace: Workspace,
        created_by,
        name: str,
        description: str,
        source_type: str,
        profile_key: str | None = None,
        manual_tickers: str | None = None,
        upload_file: UploadedFile | None = None,
    ) -> Universe:
        with transaction.atomic():
            entries, upload = self._prepare_source_payload(
                workspace=workspace,
                created_by=created_by,
                source_type=source_type,
                profile_key=profile_key,
                manual_tickers=manual_tickers,
                upload_file=upload_file,
            )
            universe = Universe.objects.create(
                workspace=workspace,
                created_by=created_by,
                name=name.strip(),
                description=description.strip(),
                source_type=source_type,
                profile_key=profile_key or "",
                source_upload=upload,
                entry_count=len(entries),
            )
            UniverseEntry.objects.bulk_create(self._build_entry_models(universe, entries))

        return universe

    def update_universe(
        self,
        *,
        universe: Universe,
        updated_by,
        name: str | None = None,
        description: str | None = None,
        source_type: str | None = None,
        profile_key: str | None = None,
        manual_tickers: str | None = None,
        upload_file: UploadedFile | None = None,
        source_changed: bool = False,
    ) -> Universe:
        if name is not None:
            universe.name = name.strip()
        if description is not None:
            universe.description = description.strip()

        if source_changed:
            resolved_source_type = source_type or universe.source_type
            with transaction.atomic():
                entries, upload = self._prepare_source_payload(
                    workspace=universe.workspace,
                    created_by=updated_by,
                    source_type=resolved_source_type,
                    profile_key=profile_key or universe.profile_key or None,
                    manual_tickers=manual_tickers,
                    upload_file=upload_file,
                )
                universe.source_type = resolved_source_type
                universe.profile_key = (profile_key or "") if resolved_source_type == Universe.SourceType.BUILT_IN else ""
                universe.source_upload = upload if resolved_source_type == Universe.SourceType.UPLOADED_FILE else None
                universe.entry_count = len(entries)
                universe.save()
                universe.entries.all().delete()
                UniverseEntry.objects.bulk_create(self._build_entry_models(universe, entries))
        else:
            universe.save()

        return universe

    def _prepare_source_payload(
        self,
        *,
        workspace: Workspace,
        created_by,
        source_type: str,
        profile_key: str | None,
        manual_tickers: str | None,
        upload_file: UploadedFile | None,
    ) -> tuple[list[ParsedTicker], UniverseUpload | None]:
        if source_type == Universe.SourceType.BUILT_IN:
            return resolve_builtin_profile_tickers(profile_key or ""), None

        if source_type == Universe.SourceType.MANUAL:
            return parse_ticker_text(manual_tickers or ""), None

        if source_type == Universe.SourceType.UPLOADED_FILE:
            if upload_file is None:
                raise UniverseInputError("Attach a newline-delimited ticker file.")
            entries, raw_bytes = parse_uploaded_ticker_file(upload_file)
            stored = self.storage.store_universe_upload(
                workspace=workspace,
                original_filename=upload_file.name,
                content=raw_bytes,
            )
            upload = UniverseUpload.objects.create(
                workspace=workspace,
                created_by=created_by,
                original_filename=upload_file.name,
                content_type=getattr(upload_file, "content_type", "") or "",
                storage_backend=stored.storage_backend,
                storage_key=stored.storage_key,
                checksum_sha256=stored.checksum_sha256,
                size_bytes=stored.size_bytes,
                metadata={"line_count": len(raw_bytes.decode("utf-8-sig").splitlines())},
            )
            return entries, upload

        raise UniverseInputError("Unsupported universe source type.", [source_type])

    @staticmethod
    def _build_entry_models(universe: Universe, entries: Iterable[ParsedTicker]) -> list[UniverseEntry]:
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
