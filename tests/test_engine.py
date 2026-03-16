from greenblatt.engine import MagicFormulaEngine, compute_enterprise_value, compute_return_on_capital
from greenblatt.models import ScreenConfig, SecuritySnapshot


def make_snapshot(
    ticker: str,
    *,
    sector: str = "Technology",
    industry: str = "Software",
    is_adr: bool = False,
    market_cap: float = 100.0,
    ebit: float = 10.0,
    current_assets: float = 50.0,
    current_liabilities: float = 10.0,
    cash_and_equivalents: float = 0.0,
    total_debt: float = 0.0,
    net_pp_e: float = 50.0,
    momentum_6m: float | None = None,
) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=f"{ticker} Holdings",
        sector=sector,
        industry=industry,
        is_adr=is_adr,
        market_cap=market_cap,
        ebit=ebit,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        cash_and_equivalents=cash_and_equivalents,
        total_debt=total_debt,
        net_pp_e=net_pp_e,
        momentum_6m=momentum_6m,
    )


def test_core_formula_helpers_match_greenblatt_definitions() -> None:
    snapshot = make_snapshot(
        "AAA",
        market_cap=220,
        ebit=50,
        current_assets=60,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=40,
        net_pp_e=60,
    )

    roc, nwc = compute_return_on_capital(snapshot)
    ev = compute_enterprise_value(snapshot)

    assert nwc == 40
    assert round(roc, 6) == 0.5
    assert ev == 250


def test_screen_excludes_financials_utilities_and_adrs_and_ranks_remaining_names() -> None:
    snapshots = [
        make_snapshot(
            "AAA",
            market_cap=220,
            ebit=50,
            current_assets=60,
            current_liabilities=20,
            total_debt=40,
            net_pp_e=60,
        ),
        make_snapshot(
            "BBB",
            market_cap=140,
            ebit=40,
            current_assets=50,
            current_liabilities=10,
            total_debt=20,
            net_pp_e=60,
        ),
        make_snapshot(
            "CCC",
            market_cap=130,
            ebit=30,
            current_assets=45,
            current_liabilities=15,
            total_debt=20,
            net_pp_e=70,
        ),
        make_snapshot("FIN", sector="Financial Services", industry="Banks", market_cap=200),
        make_snapshot("UTL", sector="Utilities", industry="Regulated Electric", market_cap=200),
        make_snapshot("ADR", is_adr=True, market_cap=200),
    ]

    result = MagicFormulaEngine().screen(snapshots, ScreenConfig(top_n=10))

    assert [security.ticker for security in result.ranked] == ["BBB", "AAA", "CCC"]
    reasons = {record.ticker: record.reason for record in result.excluded}
    assert reasons["FIN"] == "financial institution excluded"
    assert reasons["UTL"] == "utility excluded"
    assert reasons["ADR"] == "adr excluded"


def test_momentum_overlay_breaks_composite_ties() -> None:
    snapshots = [
        make_snapshot(
            "AAA",
            market_cap=220,
            ebit=50,
            current_assets=60,
            current_liabilities=20,
            total_debt=40,
            net_pp_e=60,
            momentum_6m=0.05,
        ),
        make_snapshot(
            "BBB",
            market_cap=140,
            ebit=40,
            current_assets=50,
            current_liabilities=10,
            total_debt=20,
            net_pp_e=60,
            momentum_6m=0.30,
        ),
    ]

    result = MagicFormulaEngine().screen(snapshots, ScreenConfig(top_n=2, momentum_mode="overlay"))

    assert [security.ticker for security in result.ranked] == ["BBB", "AAA"]
    assert result.ranked[0].momentum_rank == 1
    assert result.ranked[0].final_score < result.ranked[1].final_score


def test_momentum_filter_keeps_only_top_half_of_names() -> None:
    snapshots = [
        make_snapshot("AAA", market_cap=120, ebit=30, total_debt=10, net_pp_e=40, momentum_6m=0.40),
        make_snapshot("BBB", market_cap=120, ebit=28, total_debt=10, net_pp_e=40, momentum_6m=0.30),
        make_snapshot("CCC", market_cap=120, ebit=26, total_debt=10, net_pp_e=40, momentum_6m=0.10),
        make_snapshot("DDD", market_cap=120, ebit=24, total_debt=10, net_pp_e=40, momentum_6m=-0.20),
    ]

    result = MagicFormulaEngine().screen(snapshots, ScreenConfig(top_n=10, momentum_mode="filter"))

    assert [security.ticker for security in result.ranked] == ["AAA", "BBB"]
    reasons = {record.ticker: record.reason for record in result.excluded}
    assert reasons["CCC"] == "filtered by momentum overlay"
    assert reasons["DDD"] == "filtered by momentum overlay"
