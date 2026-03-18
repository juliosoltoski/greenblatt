from django.urls import path

from apps.strategy_templates.views import StrategyTemplateDetailView, StrategyTemplateLaunchView, StrategyTemplateListCreateView


urlpatterns = [
    path("", StrategyTemplateListCreateView.as_view(), name="strategy-template-list-create"),
    path("<int:template_id>/", StrategyTemplateDetailView.as_view(), name="strategy-template-detail"),
    path("<int:template_id>/launch/", StrategyTemplateLaunchView.as_view(), name="strategy-template-launch"),
]

