# Cloud Staging Plan

This document is part 1 of the cloud rollout.

It is the lower-cost plan for running only `staging` while development continues and the app has fewer than five active users.

For the later full live stack, see [cloud_infrastructure_plan.md](/home/jsoltoski/greenblatt/cloud_infrastructure_plan.md).

## 1. Scope

This plan optimizes for:

- one cloud environment only: `staging`
- fewer than 5 real users
- active development still happening
- lowest practical monthly cost without creating a throwaway architecture

This plan does not try to deliver the full production edge posture yet.

What it intentionally defers:

- separate production environment
- CloudFront
- AWS WAF
- managed Redis / ElastiCache
- S3-backed application artifact storage
- multi-AZ infrastructure
- SSM-only deployment flow

## 2. Cloud Choice

Stay with `AWS`.

Reason:

- it still gives the cleanest path into the later live architecture
- the team can start small on EC2 and RDS without paying the cost of a full managed edge stack
- we avoid redoing the container registry, IAM, database, and network decisions later

The cost savings come from a smaller phase-1 shape, not from changing providers.

## 3. Recommended Staging Topology

```text
Developers / test users
  -> DNS record for staging.example.com
    -> EC2 public IP
      -> Caddy
        -> Next.js frontend container
        -> Django backend container
        -> Celery worker container
        -> Celery beat container
        -> Redis container

Backend / worker
  -> RDS PostgreSQL
  -> optional S3 backup bucket
  -> SSM Parameter Store
```

## 4. Network And Ingress

Use the smallest sensible layout:

- one AWS region
- one VPC
- one public subnet for the staging EC2 host
- one private database subnet group for `RDS`
- security groups that allow:
  - `80/443` to the EC2 host
  - database access only from the EC2 host

Ingress choice for phase 1:

- no CloudFront yet
- no WAF yet
- `Caddy` terminates TLS directly with Let's Encrypt
- `staging.example.com` points directly at the EC2 host

Why this is the right tradeoff now:

- fewer services to pay for
- fewer moving parts while the product is still changing
- matches the repo’s current reverse-proxy and Docker Compose operating model

## 5. Data And Secrets

### PostgreSQL

Use `Amazon RDS for PostgreSQL`, but keep it small:

- `Single-AZ`
- smallest practical burstable ARM or small general-purpose instance
- automated backups enabled
- point-in-time recovery enabled

Reason:

- Postgres is the one stateful component that should be managed even in staging
- it reduces operational risk without forcing the full production bill

### Redis

For this staging-only phase, run `Redis` as a container on the EC2 host.

Reason:

- saves the standing monthly ElastiCache cost
- supports Celery and caching immediately
- keeps the app configuration close to the current local/staging shape

Constraint:

- this is acceptable only because the environment is staging and low traffic
- move to `ElastiCache` before full live rollout

### Object Storage

Do not force S3-backed application artifacts in phase 1.

Use the current filesystem-backed artifact flow on the EC2 host for staging.

Optional addition:

- create one S3 bucket only for backups and manual exports

Reason:

- the app does not yet support S3-backed artifact storage
- staging can safely keep using filesystem artifacts while development continues
- this avoids doing cloud-storage application work before it is necessary

### Secrets

Use `SSM Parameter Store` for phase 1 instead of `Secrets Manager`.

Reason:

- lower cost
- enough for one staging environment
- easy to read from deploy scripts or render into an env file on the host

Move to `Secrets Manager` in the full live phase.

## 6. Compute Shape

Use one small ARM64 EC2 instance first.

Recommended starting posture:

- one `t4g.small` or `t4g.medium` class host
- gp3 EBS volume sized for logs, images, and artifacts
- Docker Compose stays as the process model

Everything runs on that host:

- `caddy`
- `frontend`
- `backend`
- `worker`
- `beat`
- `redis`

This is acceptable because:

- concurrency is low
- the goal is functional staging, not high availability
- the app is already containerized for exactly this model

## 7. Container Registry And Deploy Flow

Use `Amazon ECR` now, even in staging.

Reason:

- it avoids reworking image distribution later
- it aligns phase 1 and phase 2

Recommended staging pipeline:

1. GitHub Actions builds backend and frontend images.
2. GitHub Actions pushes immutable SHA tags to ECR.
3. GitHub Actions deploys to the EC2 staging host.
4. The host pulls the new images and runs:
   - `migrate`
   - `collectstatic`
   - container restart
   - smoke checks

Phase-1 deploy access:

- keep SSH if that is the fastest path for staging
- SSM can wait for the full live phase

The important thing is to keep immutable image tags and scripted deployment.

## 8. DNS, TLS, CDN, And Edge

Phase-1 recommendation:

- one DNS record only: `staging.example.com`
- point it directly to the EC2 host
- let `Caddy` obtain and renew Let's Encrypt certificates

Do not add yet:

- CloudFront
- AWS WAF
- advanced CDN policy work

Reason:

- the traffic level does not justify the extra fixed complexity
- staging should validate the app, not the final public edge posture

## 9. Observability And Incident Handling

Keep observability simple:

- `CloudWatch` for EC2 and RDS metrics
- basic host and container logs
- `Sentry` for backend and Celery exceptions
- use the existing health endpoints for smoke checks

Minimum alerts:

- EC2 down or unreachable
- RDS unavailable
- repeated 5xx responses
- failed deploy smoke check

Incident response for phase 1:

1. confirm app health
2. check recent deploy
3. inspect backend logs and Sentry
4. roll back to the last working image tag if needed

## 10. Backup And Recovery

Use a light but real backup posture:

- RDS automated backups on
- manual RDS snapshot before each staging deploy that changes schema
- periodic EBS snapshot of the EC2 host
- optional tarball or export copy to S3 for filesystem artifacts if they matter

Targets for staging can be modest:

- restore the database
- restore the host or rebuild it from the deploy scripts
- accept some artifact loss if the files are non-critical

## 11. Cost Controls

This phase stays cheap by design:

- one environment only
- one EC2 host
- one small single-AZ RDS instance
- Redis on the host, not ElastiCache
- no CloudFront
- no WAF
- no multi-AZ
- no NAT gateway
- Parameter Store instead of Secrets Manager

## 12. What Changes When We Move To Full Live

The later move to [cloud_infrastructure_plan.md](/home/jsoltoski/greenblatt/cloud_infrastructure_plan.md) should add:

- separate `production`
- CloudFront
- AWS WAF
- ElastiCache
- S3-backed application artifact storage
- Secrets Manager
- stronger deploy access controls through SSM
- tighter backup, rollback, and DR expectations

## 13. Step By Step For You

For this phase I only need the following from you:

1. Create the `AWS` account.
2. Enable MFA for the root user.
3. Choose one region.
   Recommended default: `us-east-1` for US-based usage.
4. Decide one staging domain.
   Recommended: `staging.yourdomain.com`
5. Install AWS CLI v2 on the deployment machine.
6. Give me CLI access on this machine.
7. Confirm your preferred month-one cost posture is “lowest-cost staging only”.

## 14. What I Can Do After That

Once you have that ready, I can provision:

- one staging VPC
- one staging EC2 host
- one small RDS PostgreSQL instance
- one ECR registry path for backend and frontend images
- one Parameter Store namespace for staging config
- DNS and TLS for `staging`
- the first cloud staging deploy path

## Sources Validated On 2026-03-19

- AWS RDS for PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- Amazon ECR pricing: https://aws.amazon.com/ecr/pricing/
- AWS Systems Manager pricing: https://aws.amazon.com/systems-manager/pricing/
- AWS Systems Manager Parameter Store pricing: https://aws.amazon.com/systems-manager/pricing/
- Amazon EC2 On-Demand pricing: https://aws.amazon.com/ec2/pricing/on-demand/
- Amazon EBS pricing: https://aws.amazon.com/ebs/pricing/
