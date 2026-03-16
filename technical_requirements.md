Technical Requirements Document: Automated Greenblatt "Magic Formula" Screener & Simulation Engine

1. Executive Project Charter & Investment Philosophy

The transition from qualitative, research-intensive business analysis to systematic, rules-based value investing represents a fundamental paradigm shift in risk management. This strategic pivot addresses the primary failure point of the human investor: the emotional and cognitive biases that distort decision-making during periods of high market volatility. The Joel Greenblatt "Magic Formula" remains the preeminent quantitative framework for this transition, distilling decades of Graham-and-Doddsville wisdom into a repeatable mathematical exercise. By identifying high-quality businesses through the lens of operational efficiency and acquiring them only when the market offers a significant "margin of safety," we can replace subjective sentiment with a disciplined algorithmic engine.

The following table delineates the intellectual lineage that informs our system architecture:

Investment Philosophy Core Focus Primary Metric / Mechanism
Graham "Margin of Safety" Cheapness Market price vs. Intrinsic value (P/E, P/B, or Net-Net).
Buffett "Moat" Quality Sustainable competitive advantage and high-quality "wonderful companies."
Greenblatt "Systematic Algorithm" Synthesis Mechanical integration of Quality (ROC) and Value (EY) to eliminate "tinkering."

The core mission of this project is to architect a robust Python-based system that leverages the Yahoo Finance infrastructure to automate the identification and ranking of global equities. By creating a cold, mathematical simulation engine, we ensure the investment process is a consistent exercise in capital allocation rather than a reaction to market noise.

2. Functional Requirements: The Dual-Factor Ranking Algorithm

To ensure the engine produces meaningful comparisons across companies with disparate tax jurisdictions and varying capital structures, the algorithm utilizes Earnings Before Interest and Taxes (EBIT). By using EBIT, the system standardizes operating performance, removing the distortions created by local tax rates and specific debt-financing decisions that do not reflect the core economic engine of the business.

The First Pillar: Return on Capital (ROC)

ROC serves as the definitive metric for business quality, measuring how efficiently a company utilizes its tangible assets to generate operating profits.

- Mathematical Formula: ROC = EBIT / (\text{Net Working Capital} + \text{Net Fixed Assets})
- Strategic Evaluation: The denominator represents the actual physical capital employed in the company's operations. Net Working Capital (Current Assets minus Current Liabilities) captures the liquidity required for day-to-day functions, while Net Fixed Assets (Property, Plant, and Equipment) represents long-term tangible investments. Crucially, the engine must exclude intangible assets such as goodwill. Goodwill is a historical accounting artifact of past acquisitions; removing it reveals the true economic profitability of the firm's current operational assets rather than its historical cost of buying other companies.

The Second Pillar: Earnings Yield (EY)

EY acts as the "cheapness" filter, providing a more robust valuation metric than the standard P/E ratio by accounting for the total cost of the business.

- Mathematical Formula: EY = EBIT / \text{Enterprise Value}
- Strategic Evaluation: Enterprise Value (EV) must be calculated comprehensively as: EV = \text{Market Cap} + \text{Total Debt} + \text{Minority Interest} + \text{Preferred Capital} - \text{Excess Cash}. By utilizing EV, the formula captures the true price an acquirer would pay to own the entire business, including its debt obligations. This identifies firms generating substantial operating earnings relative to their total enterprise cost.

The Composite Ranking Mechanism

The engine will execute a systematic ranking process across the defined universe:

1. Rank 1 to N based on descending ROC (highest efficiency = 1).
2. Rank 1 to N based on descending EY (highest yield = 1).
3. Calculate the Composite Score for each ticker (ROC Rank + EY Rank).
4. Sort the universe by the lowest Composite Score to identify the target portfolio (typically 20-30 stocks).

5. Technical Architecture: Yahoo Finance Data Integration

The system leverages Python’s yfinance and yahoo_fin libraries to facilitate rapid prototyping and provide access to a global multi-asset universe.

Data Extraction Protocol

The engine will initialize yfinance.Ticker objects using a requests.Session to maintain persistent identity. The following attributes are mandatory for formula calculation:

- .info: Extraction of Market Capitalization and basic metadata.
- .financials: Annual/Quarterly EBIT (Operating Income).
- .balance_sheet: Comprehensive extraction of Total Debt, Cash, Current Assets, Current Liabilities, and Net Fixed Assets (PP&E).

Ticker Symbology Standards

To ensure global compatibility, the symbology layer must handle multiple asset classes:

Asset Class Symbology Format Example
US Equities Standard Ticker AAPL, MSFT
International Stocks Ticker + "." + Exchange OR.PA (Paris), 600519.SS (Shanghai)
Market Indices Caret Prefix (^) ^GSPC (S&P 500)
Foreign Exchange Pair + "=X" EURUSD=X
Cryptocurrencies Symbol + "-USD" BTC-USD
Futures Contracts Symbol + "=F" GC=F (Gold)

Advanced Multi-Ticker Processing

For large-scale screens, such as the "US Top 3000," the engine must implement the following optimizations:

- Concurrency: Mandate the use of yf.download(tickers, threads=20) to mitigate I/O-bound latency.
- MultiIndex Handling: The library returns a MultiIndex DataFrame (Level 0: Price Types, Level 1: Tickers). The simulation engine must utilize the cross-section method (e.g., df.xs('Adj Close', level=0, axis=1)) to isolate price or fundamental data across the universe for ranking.

Resilience Layer

To bypass 429 "Too Many Requests" errors and TLS handshake blocks:

- Fingerprinting: Use curl_cffi to impersonate modern browser TLS fingerprints.
- Exponential Backoff: Implement a retry strategy where delay = backoff_factor \times 2^{retry_count - 1} to prevent IP blacklisting.

4. Simulation Parameters: Multi-Market & Sector Universes

Backtesting across varied regulatory environments is necessary to verify the global robustness of the "Quality at a Bargain" factor.

Universe Filtering Logic

Before ranking, the system must apply mandatory exclusions to avoid data distortion:

- Financial Institutions: Banks and insurance companies use debt as inventory; traditional ROC and EY metrics are structurally misleading for these firms.
- Utilities: Heavy regulation and massive fixed-asset bases distort operational efficiency.
- ADRs: Excluded to avoid complications with inconsistent accounting standards and reporting cycles.

Market Simulation Profiles

- US Top 3000: Utilize yahoo_fin to pull S&P 500 or Russell 3000 constituents.
- International Markets: Apply the algorithm to European (Benelux/Nordic), Indian (NIFTY 100), and Chinese (Shanghai/HK) markets where historical outperformance has been academically verified.
- Sector-Specific Sprints: Filter for "Tech" or "Healthcare" while maintaining Financial/Utility exclusions.

5. Advanced Simulation Overlays: Momentum & Tax Optimization

To mitigate "Value Trap" risks—where stocks appear cheap based on trailing data but are in permanent decline—the system incorporates a momentum filter.

Momentum Overlay Protocol

The engine will implement a secondary rank based strictly on 6-month price performance. Historical data in European markets demonstrates that while the Magic Formula alone produced a 183% return over 12 years, the addition of a 6-month momentum filter increased that return to 783%. This filter ensures the system avoids "falling knives" and captures stocks where the market is beginning to recognize the underlying quality.

Tax-Aware Rebalancing Logic

To maximize after-tax alpha, the system follows a 51/53 week rebalancing schedule:

- Sell Losers at 51 Weeks: Realize short-term capital losses to offset ordinary income.
- Sell Winners at 53 Weeks: Hold winning positions for over one year to qualify for long-term capital gains treatment.

6. System Constraints & Risk Mitigation

Success requires acknowledging the "Tracking Error" and structural traps inherent in trailing data.

Cyclicality and Peak Earnings Trap

Relying on trailing EBIT can lead the engine into "Peak Earnings Traps," particularly in cyclical sectors like steel, chemicals, or mining. These firms often appear to have the highest EY and lowest P/E at the peak of an economic cycle when their earnings are most unsustainable. The architect must remain aware that the formula may concentrate in these sectors precisely when they are most at risk of mean reversion.

Data Integrity & Lookback Constraints

The simulation engine must adhere to Yahoo Finance’s hard infrastructure limits:

- 1-Minute Intervals: Maximum lookback of 7 days.
- 2m to 90m Intervals: Maximum lookback of 60 days.
- 1-Hour Intervals: Maximum lookback of 730 days.
- Daily Intervals: Full historical access for trend analysis and long-term backtesting.

Legal & Ethical Boundaries

The system is designed for personal, non-commercial use only. The engine must adhere to a rate limit of 2,000 requests per hour per IP address to ensure continued access to the unofficial data feeds.

Conclusion: The automated Magic Formula engine is a tool for the disciplined. Its value lies not in the complexity of its mathematics, but in its ability to enforce a rigorous investment protocol during periods of market stress. Success requires the technical resilience to maintain the data pipeline and the psychological fortitude to stay the course during multi-year periods of tracking error.
