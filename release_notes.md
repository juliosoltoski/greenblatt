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
