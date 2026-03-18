from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone
from rest_framework import serializers

from apps.backtests.models import BacktestRun
from apps.backtests.serializers import BacktestLaunchSerializer
from apps.backtests.services import BacktestLaunchRequest, BacktestRunService
from apps.screens.models import ScreenRun
from apps.screens.serializers import ScreenLaunchSerializer
from apps.screens.services import ScreenLaunchRequest, ScreenRunService
from apps.strategy_templates.models import StrategyTemplate
from apps.universes.models import Universe
from apps.workspaces.models import Workspace


@dataclass(frozen=True, slots=True)
class StrategyTemplateDefinition:
    workspace: Workspace
    created_by: object
    name: str
    description: str
    workflow_kind: str
    universe: Universe
    config: dict[str, object]
    source_screen_run: ScreenRun | None = None
    source_backtest_run: BacktestRun | None = None


def screen_config_from_run(screen_run: ScreenRun) -> dict[str, object]:
    return {
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
    }


def backtest_config_from_run(backtest_run: BacktestRun) -> dict[str, object]:
    return {
        "start_date": backtest_run.start_date.isoformat(),
        "end_date": backtest_run.end_date.isoformat(),
        "initial_capital": backtest_run.initial_capital,
        "portfolio_size": backtest_run.portfolio_size,
        "review_frequency": backtest_run.review_frequency,
        "benchmark": backtest_run.benchmark,
        "momentum_mode": backtest_run.momentum_mode,
        "sector_allowlist": backtest_run.sector_allowlist,
        "min_market_cap": backtest_run.min_market_cap,
        "use_cache": backtest_run.use_cache,
        "refresh_cache": backtest_run.refresh_cache,
        "cache_ttl_hours": backtest_run.cache_ttl_hours,
    }


def _screen_config_payload(validated_data: dict[str, object]) -> dict[str, object]:
    return {
        "top_n": validated_data["top_n"],
        "momentum_mode": validated_data["momentum_mode"],
        "sector_allowlist": validated_data.get("sector_allowlist", []),
        "min_market_cap": validated_data.get("min_market_cap"),
        "exclude_financials": validated_data["exclude_financials"],
        "exclude_utilities": validated_data["exclude_utilities"],
        "exclude_adrs": validated_data["exclude_adrs"],
        "use_cache": validated_data["use_cache"],
        "refresh_cache": validated_data["refresh_cache"],
        "cache_ttl_hours": validated_data["cache_ttl_hours"],
    }


def _backtest_config_payload(validated_data: dict[str, object]) -> dict[str, object]:
    return {
        "start_date": validated_data["start_date"].isoformat(),
        "end_date": validated_data["end_date"].isoformat(),
        "initial_capital": validated_data["initial_capital"],
        "portfolio_size": validated_data["portfolio_size"],
        "review_frequency": validated_data["review_frequency"],
        "benchmark": validated_data["benchmark"],
        "momentum_mode": validated_data["momentum_mode"],
        "sector_allowlist": validated_data.get("sector_allowlist", []),
        "min_market_cap": validated_data.get("min_market_cap"),
        "use_cache": validated_data["use_cache"],
        "refresh_cache": validated_data["refresh_cache"],
        "cache_ttl_hours": validated_data["cache_ttl_hours"],
    }


def normalize_template_config(workflow_kind: str, config: dict[str, object]) -> dict[str, object]:
    payload = {"workspace_id": 1, "universe_id": 1, **config}
    if workflow_kind == StrategyTemplate.WorkflowKind.SCREEN:
        serializer = ScreenLaunchSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return _screen_config_payload(serializer.validated_data)
    if workflow_kind == StrategyTemplate.WorkflowKind.BACKTEST:
        serializer = BacktestLaunchSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return _backtest_config_payload(serializer.validated_data)
    raise serializers.ValidationError({"workflow_kind": "Unsupported workflow kind."})


class StrategyTemplateService:
    def create_template(self, definition: StrategyTemplateDefinition) -> StrategyTemplate:
        return StrategyTemplate.objects.create(
            workspace=definition.workspace,
            created_by=definition.created_by,
            name=definition.name,
            description=definition.description,
            workflow_kind=definition.workflow_kind,
            universe=definition.universe,
            config=definition.config,
            source_screen_run=definition.source_screen_run,
            source_backtest_run=definition.source_backtest_run,
        )

    def update_template(
        self,
        template: StrategyTemplate,
        *,
        name: str | None = None,
        description: str | None = None,
        universe: Universe | None = None,
        config: dict[str, object] | None = None,
    ) -> StrategyTemplate:
        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if universe is not None:
            template.universe = universe
        if config is not None:
            template.config = normalize_template_config(template.workflow_kind, config)
        template.save()
        return template

    def launch_template(
        self,
        template: StrategyTemplate,
        *,
        launched_by,
        schedule_id: int | None = None,
        trigger_source: str = "template_launch",
    ):
        if template.workflow_kind == StrategyTemplate.WorkflowKind.SCREEN:
            payload = {"workspace_id": template.workspace_id, "universe_id": template.universe_id, **template.config}
            serializer = ScreenLaunchSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            run = ScreenRunService().launch_screen(
                ScreenLaunchRequest(
                    workspace=template.workspace,
                    created_by=launched_by,
                    universe=template.universe,
                    top_n=serializer.validated_data["top_n"],
                    momentum_mode=serializer.validated_data["momentum_mode"],
                    sector_allowlist=serializer.validated_data.get("sector_allowlist", []),
                    min_market_cap=serializer.validated_data.get("min_market_cap"),
                    exclude_financials=serializer.validated_data["exclude_financials"],
                    exclude_utilities=serializer.validated_data["exclude_utilities"],
                    exclude_adrs=serializer.validated_data["exclude_adrs"],
                    use_cache=serializer.validated_data["use_cache"],
                    refresh_cache=serializer.validated_data["refresh_cache"],
                    cache_ttl_hours=serializer.validated_data["cache_ttl_hours"],
                )
            )
            run.source_template = template
            run.save(update_fields=["source_template", "updated_at"])
        else:
            payload = {"workspace_id": template.workspace_id, "universe_id": template.universe_id, **template.config}
            serializer = BacktestLaunchSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            run = BacktestRunService().launch_backtest(
                BacktestLaunchRequest(
                    workspace=template.workspace,
                    created_by=launched_by,
                    universe=template.universe,
                    start_date=serializer.validated_data["start_date"],
                    end_date=serializer.validated_data["end_date"],
                    initial_capital=serializer.validated_data["initial_capital"],
                    portfolio_size=serializer.validated_data["portfolio_size"],
                    review_frequency=serializer.validated_data["review_frequency"],
                    benchmark=serializer.validated_data["benchmark"],
                    momentum_mode=serializer.validated_data["momentum_mode"],
                    sector_allowlist=serializer.validated_data.get("sector_allowlist", []),
                    min_market_cap=serializer.validated_data.get("min_market_cap"),
                    use_cache=serializer.validated_data["use_cache"],
                    refresh_cache=serializer.validated_data["refresh_cache"],
                    cache_ttl_hours=serializer.validated_data["cache_ttl_hours"],
                )
            )
            run.source_template = template
            run.save(update_fields=["source_template", "updated_at"])
        run.job.metadata = {
            **run.job.metadata,
            "strategy_template_id": template.id,
            "trigger_source": trigger_source,
        }
        if schedule_id is not None:
            run.job.metadata["run_schedule_id"] = schedule_id
        run.job.save(update_fields=["metadata", "updated_at"])
        template.last_used_at = timezone.now()
        template.save(update_fields=["last_used_at", "updated_at"])
        return run
