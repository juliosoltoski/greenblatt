from __future__ import annotations

from apps.strategy_templates.models import StrategyTemplate
from apps.universes.presenters import serialize_universe
from apps.workspaces.presenters import serialize_workspace


def serialize_strategy_template(template: StrategyTemplate) -> dict[str, object | None]:
    return {
        "id": template.id,
        "workspace": serialize_workspace(template.workspace),
        "created_by_id": template.created_by_id,
        "name": template.name,
        "description": template.description,
        "workflow_kind": template.workflow_kind,
        "universe": serialize_universe(template.universe),
        "config": template.config,
        "source_screen_run_id": template.source_screen_run_id,
        "source_backtest_run_id": template.source_backtest_run_id,
        "last_used_at": template.last_used_at.isoformat() if template.last_used_at else None,
        "created_at": template.created_at.isoformat(),
        "updated_at": template.updated_at.isoformat(),
    }

