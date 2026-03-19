# Cloud Infrastructure Plan

This document is part 2 of the cloud rollout: the full live deployment target after the lower-cost staging-only phase is already in place.

For the cheaper first step focused on one staging environment and fewer than five users, see [cloud_staging_plan.md](/home/jsoltoski/greenblatt/cloud_staging_plan.md).

This document is the separate future plan for public-cloud infrastructure and full live deployment referenced in [README.md](/home/jsoltoski/greenblatt/README.md).

It assumes we are moving beyond the cheaper staging-first shape and are now designing the fuller live stack documented in [product_plan.md](/home/jsoltoski/greenblatt/product_plan.md), [infra/operations.md](/home/jsoltoski/greenblatt/infra/operations.md), [compose.yml](/home/jsoltoski/greenblatt/compose.yml), and [.github/workflows/release-staging.yml](/home/jsoltoski/greenblatt/.github/workflows/release-staging.yml):

- the app already runs as Docker containers
- routing already assumes one reverse proxy in front of the frontend and backend
- staging already uses immutable image tags and a scripted deploy/backup/rollback flow
- the current production gap is cloud packaging and managed service integration, not a missing application architecture

## 1. Recommended Target Cloud

### Choice

Choose `AWS` as the target public cloud.

### Why AWS

AWS is the cleanest fit for the full live shape this product needs:

- `Amazon RDS for PostgreSQL` for the system of record
- `Amazon ElastiCache` for Redis-compatible cache and Celery broker usage
- `Amazon S3` for exports, artifacts, and backups
- `AWS Secrets Manager` for application secrets
- `Amazon ECR` for container images
- `Route 53`, `ACM`, `CloudFront`, and `AWS WAF` for public ingress and edge controls
- `CloudWatch`, `AWS Backup`, and IAM/SSM for day-2 operations

The main reason not to choose the absolute cheapest raw-infrastructure option is that this project now needs a complete live stack, not just inexpensive virtual machines. A lower sticker-price platform still creates hidden cost if it forces extra tooling for secrets, WAF, or edge security.

### Cost Rationale

AWS is not the cheapest compute provider in raw VM terms, so cost control has to come from architecture choices:

- keep the current `Docker Compose` operating model initially
- avoid Kubernetes, EKS, ECS/Fargate, NAT gateways, and other fixed-cost layers on day one
- run the app tier on one ARM64 EC2 host first
- use managed Postgres and managed Redis-compatible cache so data services are not hand-operated
- scale vertically first, then split the worker tier only when queue pressure proves it is needed

### Why Not DigitalOcean As The Primary Target

DigitalOcean is still the strongest low-cost alternative and is worth acknowledging:

- Basic Droplets start at `$4/month`
- managed PostgreSQL starts around `$15.15/month`
- managed Valkey starts around `$15/month`
- Spaces starts at `$5/month`
- basic container registry is `$5/month`
- regional load balancers start at `$12/month`

That looks attractive for a first bill. The tradeoff is that a full live posture for secrets, WAF, and broader edge controls becomes a more custom design. That is an inference from DigitalOcean’s current product and pricing surface, which emphasizes Droplets, databases, load balancers, firewalls, DNS, and object storage rather than a fully integrated live-ops stack.

For this product, the better long-term decision is slightly higher infrastructure cost in exchange for one coherent control plane.

## 2. Target Topology And Ingress

### Recommended Topology

```text
Users
  -> CloudFront
    -> AWS WAF
      -> EC2 app host
        -> Caddy
          -> Next.js frontend container
          -> Django backend container
          -> Celery worker container
          -> Celery beat container

Backend / worker
  -> RDS PostgreSQL
  -> ElastiCache (Valkey or Redis OSS)
  -> S3
  -> Secrets Manager
  -> SES or external SMTP
```

### Network Layout

- One AWS region to start.
- One VPC per environment.
- One public subnet for the EC2 app host.
- Two private subnets across two Availability Zones for `RDS` and `ElastiCache`.
- Internet exposure only on the edge and the app host.
- Database and cache stay private with security-group-only access from the app host.

### Ingress Model

- `CloudFront` is the public entry point.
- `AWS WAF` attaches at the CloudFront layer.
- `Caddy` remains the app-level router on the host because it already understands the current `/`, `/api/*`, and `/admin/*` routing split.
- CloudFront sends traffic to the EC2 origin over HTTPS.

### Why This Topology Fits The Current Repo

It preserves the current deployment logic instead of forcing a platform rewrite:

- the current images remain valid
- the existing reverse-proxy model remains valid
- the existing deploy/backup/smoke/rollback scripts can be adapted rather than replaced

## 3. Managed Postgres, Redis, Object Storage, And Secrets

### PostgreSQL

Use `Amazon RDS for PostgreSQL`.

Initial production posture:

- single-region
- `Single-AZ` to control cost at first
- automated backups enabled
- point-in-time recovery enabled
- `gp3` storage

Later upgrade path:

- move production to `Multi-AZ` once uptime expectations and budget justify it
- add a read replica only if reporting or heavy read traffic proves necessary

### Redis

Use `Amazon ElastiCache`.

Recommendation:

- prefer `Valkey` unless a strict Redis OSS requirement appears
- treat it as Redis-compatible infrastructure for Celery broker, result backend, and Django cache use

Why:

- same operational role the app already expects
- managed patching and monitoring
- cheaper path than overbuilding a custom queue/cache tier

### Object Storage

Use `Amazon S3` for:

- exports
- serialized run artifacts
- uploaded source files
- backup archives

Required application gap to close before live cutover:

- the current backend only supports the `filesystem` artifact backend in [backend/apps/universes/services.py](/home/jsoltoski/greenblatt/backend/apps/universes/services.py) and related code paths
- production cloud rollout therefore requires a new S3-backed artifact storage implementation

That S3 work should happen before the live cutover, not during it.

### Secrets Management

Use:

- `AWS Secrets Manager` for real secrets
- optionally `SSM Parameter Store` for non-secret environment configuration

Operational pattern:

- GitHub Actions or a deploy CLI reads environment values from AWS
- the deploy step renders a temporary env file on the host
- containers receive environment variables exactly the way the app already expects them

This keeps the current configuration model intact while removing plaintext secrets from the repo and the server filesystem.

## 4. Container Registry And Deployment Pipeline

### Registry

Use `Amazon ECR` for:

- backend image
- frontend image

### Pipeline

Recommended target pipeline:

1. GitHub Actions runs tests and builds both images.
2. GitHub Actions authenticates to AWS via OIDC.
3. Images are pushed to ECR with immutable tags based on the commit SHA.
4. The deployment job updates the target environment by tag or digest.
5. The host runs:
   - image pull
   - `migrate`
   - `collectstatic`
   - service restart
   - smoke checks

### Deployment Mechanism

Use `AWS Systems Manager Run Command` or `Session Manager`, not long-lived SSH as the preferred steady-state path.

Why:

- better auditability
- no manual SSH key sprawl
- cleaner automation from GitHub Actions or local CLI

### Migration From Current Pipeline

The current [release-staging.yml](/home/jsoltoski/greenblatt/.github/workflows/release-staging.yml) flow should evolve like this:

- keep the current workflow structure
- replace `GHCR` image push with `ECR`
- replace SSH deployment with `SSM`
- keep immutable SHA tagging

## 5. DNS, TLS, CDN, WAF, And Edge Concerns

### DNS

Use `Route 53` for:

- the public zone
- `app.example.com`
- `staging.example.com`
- any future `api.example.com` split if needed

### TLS

Use `AWS Certificate Manager` for public certificates attached to integrated AWS services.

At the time of writing, ACM public certificates used with integrated AWS services are issued at no additional cost.

### CDN

Use `CloudFront`.

Caching policy:

- cache static assets aggressively
- bypass or keep very short TTLs for authenticated HTML and JSON responses
- cache public assets and file downloads where safe

### WAF

Use `AWS WAF` with:

- AWS managed core rules
- explicit rate limiting on login and run-launch endpoints
- country or IP allow/deny controls only if there is a real abuse case

### Edge Choice Detail

AWS now offers `CloudFront` flat-rate plans that bundle CDN, WAF, DNS, TLS certificate, and logging into a predictable monthly charge. That is attractive for cost control.

Recommended stance:

- start with normal pay-as-you-go components if we want maximum flexibility
- evaluate `CloudFront Pro` if the included limits fit the application and predictable edge billing matters more than per-service tuning

### Admin And Sensitive Surfaces

- do not make `/admin/` broadly discoverable from public marketing copy
- consider WAF IP restrictions or stronger identity controls for admin later
- keep metrics protected by token or private networking

## 6. Observability Stack And Incident Response

### Minimum Viable Live Observability

Use:

- `CloudWatch Metrics` for EC2, RDS, ElastiCache, and CloudFront
- `CloudWatch Logs` for host and container logs
- `Sentry` for backend and Celery application errors
- the existing `/metrics/` endpoint for app metrics

### Suggested Logging Pattern

- keep the app’s existing structured JSON logging
- ship container logs to CloudWatch through either the Docker `awslogs` driver or a lightweight collector like `Fluent Bit`

### Suggested Alerting

Alert on:

- repeated 5xx responses
- EC2 disk pressure
- RDS CPU, storage, and connection pressure
- ElastiCache memory or eviction issues
- failed migrations or smoke tests during deploy
- repeated failed Celery tasks

### Incident Response

Define a simple first version:

- `SEV1`: full outage or login/research launch broken
- `SEV2`: degraded runs, provider failures, or partial delivery issues
- `SEV3`: non-blocking defects

Response path:

1. alarm fires
2. check CloudWatch and Sentry
3. confirm app health endpoints
4. decide rollback vs forward fix
5. record root cause in repo docs after recovery

## 7. Backup, Disaster Recovery, And Multi-Environment Strategy

### Environments

Recommended target environments:

- `local`: unchanged Docker Compose developer environment
- `staging`: cloud environment with production-like routing and secrets, but reduced size
- `production`: isolated live environment

Preferred long-term separation:

- separate AWS accounts for staging and production

Acceptable first live step if budget matters:

- one AWS account with strict tags, separate VPCs, and separate secrets

### Backup Strategy

- `RDS`: automated backups plus manual pre-deploy snapshots
- `S3`: versioning enabled and lifecycle rules for colder retention
- `EC2`: AMI or EBS snapshot before major host changes
- `ElastiCache`: snapshots only if the cache holds state worth preserving; otherwise treat it as rebuildable

### Disaster Recovery Target

Launch posture:

- single-region
- no active/active multi-region
- documented restore procedure
- quarterly restore drill

Suggested initial targets:

- `RPO`: 15 minutes or better via RDS point-in-time recovery
- `RTO`: 4 hours or better for a full environment restore

### Restore Discipline

- rehearse database restore on staging
- verify artifact restore separately from database restore
- keep one known-good backup before every production deploy

## 8. Cost Controls, Scaling Model, And Rollback Plan

### Cost Controls

- no Kubernetes at launch
- no NAT gateway at launch
- one ARM64 EC2 app host first
- single-AZ RDS first
- smallest practical ElastiCache footprint first
- S3 lifecycle rules for older artifacts and backups
- AWS Budgets and Cost Anomaly Detection enabled on day one

### Scaling Model

Start:

- one EC2 host running `caddy`, `frontend`, `backend`, `worker`, and `beat`
- one RDS PostgreSQL instance
- one ElastiCache cluster or serverless cache

Scale in this order:

1. increase worker concurrency
2. split worker onto its own EC2 host
3. scale RDS vertically
4. scale ElastiCache vertically
5. introduce an ALB or additional app host only when the web tier actually becomes the bottleneck

This keeps the first live bill controlled while leaving a clean path to higher capacity.

### Rollback Plan

Rollback must use:

- immutable ECR image tags
- backward-compatible migrations whenever possible
- pre-deploy database snapshot
- post-deploy smoke test before reopening traffic

Standard rollback flow:

1. select last known-good backend and frontend tags
2. redeploy previous tags through the same deployment mechanism
3. rerun smoke tests
4. inspect logs and key dashboards
5. restore database only if rollback alone cannot recover the service

## 9. Required Application Work Before Live Cutover

This repo is close, but not cloud-ready without a short set of infrastructure-facing product changes:

- add S3-backed artifact storage
- add production env support for AWS object storage and secrets retrieval
- remove hardcoded localhost admin links from the frontend
- add a production deploy env template distinct from the current staging example
- adapt backup scripts to use RDS and S3 instead of local Postgres and MinIO volumes

## 10. Step By Step For You To Kick This Off

This is the short version of what I need from you.

1. Create an `AWS` account.
2. Turn on MFA for the root user immediately.
3. Tell me the main region you want.
   Recommended default: `us-east-1` if your primary users are in the United States.
4. Decide the domain names.
   Minimum recommendation: `app.yourdomain.com` for production and `staging.yourdomain.com` for staging.
5. Install `aws` CLI v2 on the machine where we will deploy from.
6. Create a temporary bootstrap IAM user or role for setup.
   Fastest path: an admin-level bootstrap identity for the first provisioning pass, then we replace it with least-privilege roles.
7. Give me CLI access on this machine.
   In practice that means we run `aws configure` or export temporary credentials in the shell session.
8. Confirm whether you want email from `SES` or an external SMTP provider.
9. Confirm whether the existing GitHub repository can use GitHub Actions OIDC into AWS.
10. Tell me your budget comfort level for month one.
    This changes whether we start with single-AZ only or spend extra for stronger HA immediately.

### What You Should Send Me Once Your AWS Account Exists

Send me:

- AWS account ID
- chosen AWS region
- production domain
- staging domain
- confirmation that MFA is enabled
- confirmation that AWS CLI access works on this machine
- whether I should wire SES now or later
- whether I should keep staging and production in one account for the first cut

### What I Can Do After That

Once you have done the steps above, I can provision and wire:

- ECR
- VPC and security groups
- RDS PostgreSQL
- ElastiCache
- S3 bucket layout
- Secrets Manager entries
- EC2 host bootstrap
- CloudFront and WAF
- Route 53 records
- the first live deployment path

## Sources Validated On 2026-03-19

- AWS RDS for PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- Amazon ElastiCache pricing: https://aws.amazon.com/elasticache/pricing/
- Amazon S3 pricing: https://aws.amazon.com/s3/pricing/
- AWS Secrets Manager pricing: https://aws.amazon.com/secrets-manager/pricing/
- Amazon ECR pricing: https://aws.amazon.com/ecr/pricing/
- Amazon Route 53 pricing: https://aws.amazon.com/route53/pricing/
- AWS WAF pricing: https://aws.amazon.com/waf/pricing/
- AWS Certificate Manager pricing: https://aws.amazon.com/certificate-manager/pricing/
- Amazon CloudFront pricing: https://aws.amazon.com/cloudfront/pricing/
- DigitalOcean Droplet pricing: https://www.digitalocean.com/pricing/droplets
- DigitalOcean Managed Databases pricing: https://www.digitalocean.com/pricing/managed-databases
- DigitalOcean Spaces pricing: https://www.digitalocean.com/pricing/spaces-object-storage
- DigitalOcean Container Registry pricing: https://www.digitalocean.com/pricing/container-registry
- DigitalOcean Load Balancer pricing: https://www.digitalocean.com/pricing/load-balancers
