# Deploy to AWS — sedhuhome.ai

Recommended architecture for a single-user app: **one EC2 instance running the
docker-compose stack, Caddy for automatic HTTPS, GoDaddy DNS pointing at an
Elastic IP.** ~$15–17/month all-in. The ECS Fargate path (bottom) costs 4–6× more
and adds nothing until you have real multi-user traffic.

```
GoDaddy DNS                         EC2 (t4g.small, Ubuntu 24.04)
sedhuhome.ai      A → Elastic IP    ┌──────────────────────────────┐
www.sedhuhome.ai  A → Elastic IP →  │ Caddy :443  (auto-TLS)       │
api.sedhuhome.ai  A → Elastic IP    │  ├─ sedhuhome.ai → frontend  │
                                    │  └─ api.…       → backend    │
                                    │ Next.js · FastAPI · Postgres │
                                    └──────────────────────────────┘
```

## 1. Launch the EC2 instance (~10 min, AWS console)

1. EC2 → Launch instance
   - Name: `options-signal`
   - AMI: **Ubuntu Server 24.04 LTS (arm64)**
   - Type: **t4g.small** (2 vCPU, 2 GB — ~$12/mo; t4g.micro $6/mo works but is tight for builds)
   - Key pair: create/download one (`options-signal.pem`)
   - Security group — inbound rules:
     - SSH (22) — **My IP only**
     - HTTP (80) — Anywhere (Caddy needs it for the Let's Encrypt challenge)
     - HTTPS (443) — Anywhere
   - Storage: 20 GB gp3
2. EC2 → Elastic IPs → **Allocate** → **Associate** with the instance.
   Write down the IP — call it `EIP` below.

## 2. Point GoDaddy DNS at the instance (~5 min)

GoDaddy → My Products → sedhuhome.ai → **DNS**. Delete the parked A records, add:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `EIP` | 600 |
| A | `www` | `EIP` | 600 |
| A | `api` | `EIP` | 600 |

Propagation is usually minutes. Verify: `dig +short A sedhuhome.ai` returns the EIP.

## 3. Install Docker on the instance

```sh
ssh -i options-signal.pem ubuntu@EIP

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit   # re-login so the group applies
```

## 4. Ship the app

From your Mac (project root):

```sh
rsync -az --exclude .git --exclude node_modules --exclude .venv \
  --exclude .next --exclude '*.png' --exclude dev.db \
  ./ ubuntu@EIP:~/options-signal/
```

`.env` is included by that rsync (it's your secrets file — it must reach the
server but **never** a git remote). Then on the instance, add the one
production-only secret:

```sh
ssh -i options-signal.pem ubuntu@EIP
cd options-signal
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" >> .env
```

## 5. Launch

```sh
docker compose -f docker-compose.prod.yml up -d --build
```

First build ~3–5 min. Caddy obtains certificates automatically once DNS resolves
(step 2 must be live first — that's the only ordering that matters).

Check:
- https://api.sedhuhome.ai/health → `{"status":"ok", ...}`
- https://sedhuhome.ai → dashboard
- ntfy/email alerts fire from the server exactly as they did locally

## 6. Operations

```sh
# logs
docker compose -f docker-compose.prod.yml logs -f backend

# deploy an update (after rsync-ing changes)
docker compose -f docker-compose.prod.yml up -d --build

# database backup
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U options options_alerts | gzip > backup-$(date +%F).sql.gz
```

Cost summary: t4g.small ~$12.20/mo + EBS 20 GB ~$1.60 + Elastic IP (attached:
free) ≈ **$14/mo**. Domain stays at GoDaddy — no Route 53 needed.

## Notes / gotchas

- **Market hours are US/Eastern in code** — the scanner is timezone-aware
  (`zoneinfo`), so the server's UTC clock is fine. No config needed.
- The scheduler runs inside the backend container; **don't scale backend to
  multiple replicas** or you'll double-fire alerts. One replica by design.
- `MARKET_HOURS_ONLY=true` (default) keeps API usage near zero overnight.
- SQLite is dev-only; the prod compose uses Postgres. Your local dev.db
  (watchlist, alert history) does NOT migrate automatically — re-add your
  tickers on the live site, or ask me for a one-shot export/import script.

## Later: the "real production" path (when actually needed)

Multi-user / always-on growth path, per the original blueprint: ECR images →
ECS Fargate services (backend, frontend) → ALB + ACM cert → RDS Postgres →
ElastiCache → Secrets Manager → CloudWatch. ~$80–120/mo before traffic.
Worth doing only when there are users besides you; the compose file splits
cleanly into two task definitions when that day comes.
