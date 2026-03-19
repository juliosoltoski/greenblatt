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

## 2026-03-19 - Cloud Planning And Commercial Polish Pass

- Product: added separate future plans for public-cloud/live deployment and commercial content cleanup, reduced the app chrome height, removed sticky overlap in the top navigation, and rewrote the public/login/dashboard copy to sound less like a scaffold.
- Platform: documented an AWS-based live deployment target with managed Postgres, Redis-compatible cache, object storage, secrets, edge controls, and an ECR-based pipeline while also calling out the current filesystem-only artifact storage gap.
- Verification: `npm run build`

## 2026-03-19 - Cloud Plan Split For Lower-Cost Staging First

- Product: split the cloud planning docs into a cheaper staging-only rollout for active development and a separate later full live deployment plan.
- Platform: the new staging-first plan defers CloudFront, WAF, ElastiCache, and S3-backed application artifacts in favor of one EC2 host, small RDS, local Redis, direct Caddy TLS, and Parameter Store while the app has fewer than five users.
- Verification: documentation-only update

## 2026-03-19 - Expanded Built-In Universes And Startup Sync

- Product: expanded the built-in universe catalog with larger regional packs for the UK, Australia, Canada, India, China/Hong Kong, and Benelux/Nordics, and added more U.S. sector starter universes with 100-plus names each.
- Platform: added startup and operator sync support through `python manage.py sync_builtin_universes`, plus a schema flag to keep system-managed built-ins separate from user-created saved universes.
- Verification: `PYTHONPATH=/home/jsoltoski/greenblatt/backend:/home/jsoltoski/greenblatt/src .venv/bin/python backend/manage.py test apps.universes`, `npm run build`
