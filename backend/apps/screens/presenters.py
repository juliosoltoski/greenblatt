from __future__ import annotations

from apps.jobs.presenters import serialize_job
from apps.screens.models import ScreenExclusion, ScreenResultRow, ScreenRun
from apps.universes.presenters import serialize_universe
from apps.workspaces.presenters import serialize_workspace


def _provider_payload(screen_run: ScreenRun) -> dict[str, object | None] | None:
    summary = screen_run.summary if isinstance(screen_run.summary, dict) else {}
    summary_provider = summary.get("provider")
    if isinstance(summary_provider, dict):
        return summary_provider
    job_metadata = screen_run.job.metadata if isinstance(screen_run.job.metadata, dict) else {}
    result_payload = job_metadata.get("result")
    if isinstance(result_payload, dict) and isinstance(result_payload.get("provider"), dict):
        return result_payload["provider"]
    request_payload = job_metadata.get("request")
    if isinstance(request_payload, dict) and isinstance(request_payload.get("provider"), dict):
        return request_payload["provider"]
    return None


def serialize_screen_artifacts(screen_run: ScreenRun) -> list[dict[str, object | None]]:
    artifacts: list[dict[str, object | None]] = [
        {
            "kind": "json",
            "label": "Full run JSON",
            "filename": f"screen-run-{screen_run.id}.json",
            "download_url": f"/api/v1/screens/{screen_run.id}/export/json/",
        }
    ]
    if screen_run.has_export:
        artifacts.insert(
            0,
            {
                "kind": "csv",
                "label": "Ranked results CSV",
                "filename": screen_run.export_filename,
                "checksum_sha256": screen_run.export_checksum_sha256,
                "size_bytes": screen_run.export_size_bytes,
                "download_url": f"/api/v1/screens/{screen_run.id}/export/",
            },
        )
    return artifacts


def serialize_screen_result_row(row: ScreenResultRow) -> dict[str, object | None]:
    return {
        "id": row.id,
        "position": row.position,
        "ticker": row.ticker,
        "company_name": row.company_name or None,
        "sector": row.sector or None,
        "industry": row.industry or None,
        "market_cap": row.market_cap,
        "ebit": row.ebit,
        "net_working_capital": row.net_working_capital,
        "enterprise_value": row.enterprise_value,
        "return_on_capital": row.return_on_capital,
        "earnings_yield": row.earnings_yield,
        "momentum_6m": row.momentum_6m,
        "roc_rank": row.roc_rank,
        "ey_rank": row.ey_rank,
        "momentum_rank": row.momentum_rank,
        "composite_score": row.composite_score,
        "final_score": row.final_score,
        "row_payload": row.row_payload,
    }


def serialize_screen_exclusion(exclusion: ScreenExclusion) -> dict[str, object | None]:
    return {
        "id": exclusion.id,
        "ticker": exclusion.ticker,
        "reason": exclusion.reason,
    }


def serialize_screen_run(screen_run: ScreenRun) -> dict[str, object | None]:
    return {
        "id": screen_run.id,
        "workflow_kind": "screen",
        "workspace": serialize_workspace(screen_run.workspace),
        "created_by_id": screen_run.created_by_id,
        "source_template_id": screen_run.source_template_id,
        "universe": serialize_universe(screen_run.universe),
        "job": serialize_job(screen_run.job),
        "top_n": screen_run.top_n,
        "momentum_mode": screen_run.momentum_mode,
        "sector_allowlist": screen_run.sector_allowlist,
        "min_market_cap": screen_run.min_market_cap,
        "exclude_financials": screen_run.exclude_financials,
        "exclude_utilities": screen_run.exclude_utilities,
        "exclude_adrs": screen_run.exclude_adrs,
        "use_cache": screen_run.use_cache,
        "refresh_cache": screen_run.refresh_cache,
        "cache_ttl_hours": screen_run.cache_ttl_hours,
        "is_starred": screen_run.is_starred,
        "tags": screen_run.tags,
        "notes": screen_run.notes,
        "provider": _provider_payload(screen_run),
        "result_count": screen_run.result_count,
        "exclusion_count": screen_run.exclusion_count,
        "resolved_ticker_count": screen_run.resolved_ticker_count,
        "total_candidate_count": screen_run.total_candidate_count,
        "summary": screen_run.summary,
        "export": (
            {
                "storage_backend": screen_run.export_storage_backend,
                "storage_key": screen_run.export_storage_key,
                "filename": screen_run.export_filename,
                "checksum_sha256": screen_run.export_checksum_sha256,
                "size_bytes": screen_run.export_size_bytes,
                "download_url": f"/api/v1/screens/{screen_run.id}/export/",
            }
            if screen_run.has_export
            else None
        ),
        "artifacts": serialize_screen_artifacts(screen_run),
        "created_at": screen_run.created_at.isoformat(),
        "updated_at": screen_run.updated_at.isoformat(),
    }


def serialize_screen_run_bundle(
    screen_run: ScreenRun,
    *,
    result_rows: list[ScreenResultRow] | None = None,
    exclusions: list[ScreenExclusion] | None = None,
) -> dict[str, object | None]:
    return {
        "run": serialize_screen_run(screen_run),
        "results": [serialize_screen_result_row(row) for row in (result_rows or list(screen_run.result_rows.all()))],
        "exclusions": [serialize_screen_exclusion(exclusion) for exclusion in (exclusions or list(screen_run.exclusions.all()))],
    }
