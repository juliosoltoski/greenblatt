# Release Notes

## Convention

Each entry should be short and should capture:

- what changed for users
- operational notes such as migrations, env vars, or deploy sequencing
- the manual smoke path that was used

Recommended format:

```md
## YYYY-MM-DD - Short Title

- Product: user-visible behavior changes
- Platform: deployment, schema, queue, provider, or env notes
- Verification: automated coverage and manual smoke path summary
```

## 2026-03-18 - NH1 And NH2 Kickoff

- Product: added a shared `/app` navigation chrome, simplified the universe/screen/backtest launch flows, and reduced the amount of milestone-era UI copy shown to end users.
- Platform: consolidated contributor, smoke-test, and release-note documentation so setup and verification guidance are no longer scattered through multiple planning files.
- Verification: `docker build -t greenblatt-frontend:latest ./frontend`

## 2026-03-18 - NH5 And NH6 Collaboration And Notification UX

- Product: added workspace collaboration flows with comments, curated collections, review states, read-only share links, activity feed, live job timelines, cancel actions on active runs, and a fuller alerts page for email, Slack webhook, generic webhook, and digest preferences.
- Platform: introduced persisted job events and cancellation metadata, digest delivery via the hourly `automation.send_notification_digests` Celery Beat task, and new collaboration/notification APIs without adding a new deployment service.
- Verification: `python manage.py test apps.automation apps.jobs apps.collaboration apps.strategy_templates`, `python manage.py test`, `python manage.py makemigrations --check --dry-run`, and `docker build -t greenblatt-frontend:latest ./frontend`
