from greenblatt.providers.yahoo import YahooFinanceProvider


def test_rank_nasdaq_stock_rows_filters_non_equities_and_sorts_by_market_cap() -> None:
    rows = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "marketCap": "500000000000.00"},
        {"symbol": "AAPL", "name": "Apple Inc. Common Stock", "marketCap": "3700000000000.00"},
        {"symbol": "BRK.A", "name": "Berkshire Hathaway Inc. Class A Common Stock", "marketCap": "1000000000000.00"},
        {"symbol": "XYZW", "name": "Example Holdings Warrant", "marketCap": "9000000000.00"},
        {"symbol": "MSFT", "name": "Microsoft Corporation Common Stock", "marketCap": "2900000000000.00"},
        {"symbol": "ABC", "name": "Example Depositary Shares", "marketCap": "8000000000.00"},
    ]

    ranked = YahooFinanceProvider._rank_nasdaq_stock_rows(rows)

    assert ranked[:3] == ["AAPL", "MSFT", "BRK-A"]
    assert "SPY" not in ranked
    assert "XYZW" not in ranked
    assert "ABC" not in ranked


def test_parse_pipe_delimited_rows_skips_file_creation_footer() -> None:
    text = "\n".join(
        [
            "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol",
            "AAPL|Apple Inc. Common Stock|Q|AAPL|N|100|N|AAPL",
            "File Creation Time: 0313202611:01||||||",
        ]
    )

    rows = YahooFinanceProvider._parse_pipe_delimited_rows(text)

    assert rows == [
        {
            "ACT Symbol": "AAPL",
            "Security Name": "Apple Inc. Common Stock",
            "Exchange": "Q",
            "CQS Symbol": "AAPL",
            "ETF": "N",
            "Round Lot Size": "100",
            "Test Issue": "N",
            "NASDAQ Symbol": "AAPL",
        }
    ]


def test_normalize_symbol_preserves_exchange_suffixes_and_converts_us_class_shares() -> None:
    provider = YahooFinanceProvider(use_cache=False)

    assert provider._normalize_symbol("ASML.AS") == "ASML.AS"
    assert provider._normalize_symbol("600519.SS") == "600519.SS"
    assert provider._normalize_symbol("NOVO-B.CO") == "NOVO-B.CO"
    assert provider._normalize_symbol("BRK.B") == "BRK-B"
    assert provider._normalize_symbol("BF.B") == "BF-B"
