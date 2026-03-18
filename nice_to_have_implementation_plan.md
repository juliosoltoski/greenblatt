# Nice-to-Have Implementation Plan: Greenblatt Web App

## 1. Purpose

This document continues development planning after the successful delivery of `M0` through `M10` in [implementation_plan.md](/home/jsoltoski/greenblatt/implementation_plan.md).

Its purpose is to:

- capture the best follow-on work now that the first deployable product exists
- include items that were explicitly scoped out of the original implementation plan
- improve product usability, trust, and operator experience before pursuing major new surface area
- create a cleaner documentation roadmap for contributors and future planning

This is not a rewrite plan. The current architecture remains the baseline:

- Django + DRF backend
- Next.js frontend
- Celery + Redis async execution
- PostgreSQL persistence
- object/artifact storage
- shared `src/greenblatt` core domain layer

## 2. Current Baseline

The product already supports:

- authenticated workspaces
- universe management
- async screens and backtests
- persisted results and exports
- templates, history, schedules, alerts, and notifications
- provider abstraction with multiple providers and fallback
- local Docker Compose deployment and staging-oriented hardening

The main shift now is from "make it work end to end" to "make it easier to use, easier to trust, and easier to operate."

## 3. Prioritization Principles

- Prefer UX simplification over adding more knobs.
- Favor product coherence and reduced user confusion over feature count.
- Tighten the existing screen/backtest workflows before adding adjacent surface area.
- Keep new work compatible with the current API and persistence model unless a strong product reason justifies change.
- Continue shipping in vertical slices with clear smoke paths.
- Separate infrastructure-at-scale planning from application feature planning.

## 4. Recommended Post-M10 Milestone Order

| Milestone | Outcome | Effort | Depends On |
| --- | --- | --- | --- |
| NH1 | documentation consolidation and contributor clarity | S | none |
| NH2 | frontend UX simplification and navigation cleanup | M | none |
| NH3 | dashboard, onboarding, presets, and safer defaults | M | NH2 |
| NH4 | analyst productivity and research workflow polish | M | NH2 |
| NH5 | collaboration, review, and read-only sharing | M | NH4 |
| NH6 | richer notifications and real-time progress UX | M | NH4 |
| NH7 | data quality, provider operations, and performance optimization | M | NH4 |
| NH8 | account, public-surface, and commercial readiness | L | NH5, NH6 |

Effort is relative only:

- `S`: small
- `M`: medium
- `L`: large

## 5. Milestone Details

### NH1. Documentation Consolidation

#### Goal

Make the docs set easier to navigate for developers, operators, and future planning.

#### Tasks

- Turn `README.md` into a clearer entry point with a short docs map.
- Mark [implementation_plan.md](/home/jsoltoski/greenblatt/implementation_plan.md) as the completed M0-M10 delivery record.
- Mark [product_plan.md](/home/jsoltoski/greenblatt/product_plan.md) as the product and architecture reference.
- Improve [technical_requirements.md](/home/jsoltoski/greenblatt/technical_requirements.md) formatting and clarify that it remains the investment and data logic baseline.
- Add a short contributor-oriented section covering "where to change what" across `src/greenblatt`, `backend`, `frontend`, and `infra`.
- Consolidate manual smoke paths so they are not scattered across multiple files.
- Add a changelog or release-notes convention before feature work continues.

#### Deliverables

- a clean docs map
- current-status notes in the major planning docs
- reduced duplication across setup and planning documents

#### Exit criteria

- A new contributor can identify the right doc in under two minutes.
- The documentation set has a clear separation between requirements, product architecture, completed roadmap, and future roadmap.

### NH2. Frontend UX Simplification and Navigation Cleanup

#### Goal

Reduce cognitive load and make the app feel more guided, especially for first-time users.

#### Tasks

- Audit the current app shell and group navigation by user intent rather than implementation history.
- Add a simpler top-level structure such as `Home`, `Research`, `Assets`, `Automation`, and `Settings`.
- Review every major page for information overload and move advanced options behind progressive disclosure.
- Collapse rarely used launch parameters into an "Advanced settings" panel.
- Standardize page headers, breadcrumbs, primary actions, empty states, error states, and loading states.
- Reduce visual density in tables by improving defaults, column selection, and result summaries.
- Add lightweight contextual help text where the product currently assumes domain knowledge.
- Improve mobile and small-screen behavior for forms, charts, and tables.
- Run an accessibility pass on focus states, color contrast, keyboard navigation, and semantic headings.

#### Deliverables

- simplified navigation
- cleaner launch forms
- more consistent page layout system
- accessibility and responsive improvements

#### Exit criteria

- A first-time user can find universes, screens, backtests, and schedules without explanation.
- Advanced settings no longer overwhelm the default screen or backtest launch flow.

### NH3. Dashboard, Onboarding, and Safe Defaults

#### Goal

Help users understand what to do next and reduce bad runs caused by weak defaults.

#### Tasks

- Build a real home/dashboard page instead of relying on deep links.
- Show recent runs, saved universes, saved templates, provider status, and quick actions.
- Add a getting-started checklist for new workspaces.
- Add starter presets for common screen and backtest workflows.
- Add provider-aware guidance when a user chooses large universes or expensive parameter combinations.
- Add benchmark, portfolio-size, and candidate-limit recommendations based on common safe usage.
- Add sample/demo content or one-click starter universes/templates for onboarding.
- Surface the most important run outcomes in plain language before the user reaches dense tables.

#### Deliverables

- dashboard
- onboarding checklist
- presets and safer defaults
- reduced trial-and-error in launch flows

#### Exit criteria

- New users can get to a first successful run without reading several pages of documentation.
- Common launch mistakes are prevented or at least warned early.

### NH4. Analyst Productivity and Research Workflow Polish

#### Goal

Make repeated research work faster and more structured for active users.

#### Tasks

- Improve run comparison for both screens and backtests.
- Add saved filters, saved table layouts, and remembered column choices.
- Add run notes, tags, and lightweight annotations.
- Add richer summary views such as benchmark-relative performance, drawdown summary, turnover summary, and exclusion breakdowns.
- Add favoriting or bookmarking for universes, templates, and important runs.
- Add "promote to template", "clone as draft", and "rerun with edits" shortcuts where appropriate.
- Add stronger artifact discoverability from run detail pages.
- Add support for exporting comparison bundles and analyst notes.

#### Deliverables

- better comparison workflows
- saved user preferences for dense data views
- stronger research organization

#### Exit criteria

- Active users can revisit and compare prior work without rebuilding context manually.
- Run history becomes an organized research record rather than a raw log.

### NH5. Collaboration, Review, and Read-Only Sharing

#### Goal

Add team-friendly workflows without changing the core product shape.

#### Tasks

- Improve workspace collaboration UX for owners, admins, analysts, and viewers.
- Add comments or discussion threads on runs and templates.
- Add review/approval states for important templates or scheduled strategies.
- Add read-only share links inside a workspace or for explicitly approved recipients.
- Add activity feed and audit-friendly timeline views for important changes.
- Add pinning and curated collections for teams that maintain multiple universes and templates.

#### Items previously scoped out and now eligible

- read-only share links

#### Deliverables

- collaboration affordances
- review workflow
- controlled sharing model

#### Exit criteria

- Teams can discuss, review, and distribute research outputs without leaving the product.
- Sharing does not require exposing Django admin or raw exports as the primary mechanism.

### NH6. Richer Notifications and Real-Time Progress UX

#### Goal

Make long-running workflows feel more responsive and improve outbound alert usefulness.

#### Tasks

- Add notification preferences at user and workspace level.
- Expand destinations beyond email to Slack and generic webhooks.
- Add digest notifications for scheduled activity and failures.
- Add SSE or WebSocket progress updates for active jobs instead of polling-only UX.
- Add live job timeline events and clearer retry/failure messaging in the UI.
- Add cancel, retry, and relaunch actions where operationally safe.
- Surface provider failures and rate-limit events more clearly to end users.

#### Items previously scoped out and now eligible

- Slack/webhook alerts
- real-time streaming status over SSE or WebSockets

#### Deliverables

- richer alert routing
- real-time job feedback
- less page-refresh-driven workflow

#### Exit criteria

- Long-running screens and backtests no longer feel opaque while executing.
- Users can route important alerts to channels they actually monitor.

### NH7. Data Quality, Provider Operations, and Performance Optimization

#### Goal

Improve trust in results, reduce provider pain, and keep the product responsive as usage grows.

#### Tasks

- Add explicit provider diagnostics and operator-facing failure summaries.
- Add cache-warm and data-refresh policies for common universes and templates.
- Add provider cost/rate-limit awareness where a non-free provider is configured.
- Improve result validation and anomaly detection for suspicious provider payloads.
- Add better handling for stale fundamentals, thin history, delistings, and symbol changes.
- Evaluate Parquet or other compact artifact formats for large result sets.
- Improve queue separation and performance tuning for heavy backtests.
- Add frontend performance work for large tables and charts, including virtualization where needed.
- Add multi-provider routing in the UI only if there is a clear operator or analyst use case.

#### Items previously scoped out and now eligible

- multi-provider routing in the UI

#### Deliverables

- better provider observability
- faster repeat runs
- improved handling of data edge cases

#### Exit criteria

- Provider issues are diagnosable without diving directly into logs.
- Heavy result pages remain usable and responsive.

### NH8. Account, Public Surface, and Commercial Readiness

#### Goal

Prepare the product for broader external exposure if and when that becomes desirable.

#### Tasks

- Add user profile and account settings cleanup.
- Add social login only if it clearly improves onboarding for the target audience.
- Create a proper public landing page and product marketing surface separate from the authenticated app.
- Add read-only public/demo pages only when product positioning requires them.
- Evaluate billing, subscriptions, quotas, and plan enforcement if commercialization begins.
- Add stronger legal/compliance messaging around data-provider usage and research-only positioning.
- Review admin/support tooling for a multi-customer environment.

#### Items previously scoped out and now eligible

- social login
- public landing pages
- billing

#### Deliverables

- external-facing product surface
- clearer account management
- commercialization readiness backlog

#### Exit criteria

- The team can decide to expose the product more broadly without scrambling to design first-touch user flows.

## 6. Still Deliberately Deferred

These items are worth tracking, but they should remain out of the near-term application roadmap unless strategy changes:

- brokerage integration and auto-trading
- real-time streaming quotes as a core product feature
- intraday backtesting
- native mobile apps
- deep enterprise data-vendor integrations beyond the current provider abstraction needs

## 7. UX Cleanup Checklist

This checklist should be reused across multiple milestones:

- reduce duplicated controls between launch, detail, and history pages
- prefer plain-language summaries before dense financial tables
- hide advanced settings until the user asks for them
- standardize empty/loading/error/partial-failure states
- add sensible defaults and recommended presets
- minimize unnecessary polling and page churn
- improve accessibility and keyboard navigation
- keep charts and tables readable on laptop-sized screens

## 8. Documentation Actions To Do Now

These should happen immediately while the M0-M10 context is still fresh:

- update `README.md` to include a documentation map and current status snapshot
- add status notes to the original plan documents
- clarify the role of `technical_requirements.md`
- keep smoke-test instructions current with the implemented app
- note which roadmap is active for future work

## 9. Separate Future Plan: Public Cloud and Full Live Deployment

Do not overload this document with cloud-infrastructure design.

Create a separate future plan for public-cloud infrastructure and full live deployment. That document should cover:

- target cloud choice and rationale
- network topology and ingress
- managed Postgres, Redis, object storage, and secrets management
- container registry and deployment pipeline
- DNS, TLS, CDN, WAF, and edge concerns
- observability stack and incident response
- backup, disaster recovery, and multi-environment strategy
- cost controls, scaling model, and rollback plan

Suggested later filename:

- `cloud_infrastructure_plan.md`

## 10. Immediate Next Step

Start with `NH1` and `NH2` together:

1. clean up the docs set and make the roadmap state explicit
2. audit the current frontend for navigation and information overload
3. simplify launch flows before adding more advanced features
4. use that cleanup to inform the dashboard and onboarding work in `NH3`
