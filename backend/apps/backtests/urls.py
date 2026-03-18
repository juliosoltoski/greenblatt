from django.urls import path

from apps.backtests.views import (
    BacktestDetailView,
    BacktestEquityPointListView,
    BacktestExportDownloadView,
    BacktestJsonExportView,
    BacktestFinalHoldingListView,
    BacktestListCreateView,
    BacktestReviewTargetListView,
    BacktestTradeListView,
)


urlpatterns = [
    path("", BacktestListCreateView.as_view(), name="backtest-list-create"),
    path("<int:backtest_run_id>/", BacktestDetailView.as_view(), name="backtest-detail"),
    path("<int:backtest_run_id>/equity/", BacktestEquityPointListView.as_view(), name="backtest-equity"),
    path("<int:backtest_run_id>/trades/", BacktestTradeListView.as_view(), name="backtest-trades"),
    path("<int:backtest_run_id>/review-targets/", BacktestReviewTargetListView.as_view(), name="backtest-review-targets"),
    path("<int:backtest_run_id>/final-holdings/", BacktestFinalHoldingListView.as_view(), name="backtest-final-holdings"),
    path("<int:backtest_run_id>/export/", BacktestExportDownloadView.as_view(), name="backtest-export"),
    path("<int:backtest_run_id>/export/json/", BacktestJsonExportView.as_view(), name="backtest-export-json"),
]
