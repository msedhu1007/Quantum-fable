#!/usr/bin/env bash
# One-command production deploy → https://sedhuhome.ai
#
#   ./deploy/deploy.sh              # full deploy (sync + build + restart + verify)
#   ./deploy/deploy.sh --logs       # just tail live backend logs
#   ./deploy/deploy.sh --status     # container status + health, no deploy
#
# Override defaults via env vars:  SERVER_IP=… KEY=… ./deploy/deploy.sh
set -euo pipefail

SERVER_IP="${SERVER_IP:-100.58.135.254}"
KEY="${KEY:-$HOME/Downloads/sedhu-ec2-key.pem}"
REMOTE="ubuntu@$SERVER_IP"
SSH="ssh -i $KEY -o ConnectTimeout=10"
APP_DIR="options-signal"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }
die() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

[ -f "$KEY" ] || die "SSH key not found at $KEY"

case "${1:-}" in
  --logs)
    exec $SSH "$REMOTE" "cd $APP_DIR && sudo docker compose -f docker-compose.prod.yml logs -f --tail=100 backend"
    ;;
  --status)
    $SSH "$REMOTE" "cd $APP_DIR && sudo docker compose -f docker-compose.prod.yml ps"
    printf "\nhealth: " && curl -s --noproxy '*' --max-time 10 "https://api.sedhuhome.ai/health" && echo
    exit 0
    ;;
esac

say "Pre-flight: backend import check"
( cd "$ROOT/backend" && source .venv/bin/activate && python -c "from app.main import app" ) \
  || die "backend does not import — fix before deploying"

say "Pre-flight: frontend typecheck"
( cd "$ROOT/frontend" && npm run --silent typecheck ) || die "typecheck failed — fix before deploying"

# The server's .env carries POSTGRES_PASSWORD (not present in the local .env).
# rsync overwrites .env, so capture the password first and restore it after —
# losing it bricks the backend against the already-initialized DB volume.
say "Preserving server-side DB password"
PG_PASS=$($SSH "$REMOTE" "grep '^POSTGRES_PASSWORD=' $APP_DIR/.env 2>/dev/null | cut -d= -f2-" || true)

say "Syncing project → $REMOTE:~/$APP_DIR"
rsync -az --delete -e "ssh -i $KEY" \
  --exclude .git --exclude node_modules --exclude .venv --exclude .next \
  --exclude '*.png' --exclude dev.db --exclude '*.pem' \
  --exclude .playwright-cli --exclude .playwright-mcp \
  "$ROOT/" "$REMOTE:~/$APP_DIR/"

say "Building + restarting containers (this is the slow part)"
$SSH "$REMOTE" "cd $APP_DIR && \
  if [ -n '$PG_PASS' ]; then echo 'POSTGRES_PASSWORD=$PG_PASS' >> .env; \
  else echo \"POSTGRES_PASSWORD=\$(openssl rand -hex 16)\" >> .env; fi; \
  sudo docker compose -f docker-compose.prod.yml up -d --build --quiet-pull 2>&1 | tail -6"

say "Pruning old images (keeps disk from filling)"
$SSH "$REMOTE" "sudo docker image prune -f --filter 'until=24h' > /dev/null && df -h / | tail -1"

say "Verifying live site"
ok=true
code=""
for i in 1 2 3 4 5 6; do
  sleep 5
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" --max-time 15 https://sedhuhome.ai/dashboard || true)
  health=$(curl -s --noproxy '*' --max-time 15 https://api.sedhuhome.ai/health || true)
  if [ "$code" = "200" ] && echo "$health" | grep -q '"status":"ok"'; then break; fi
done
[ "$code" = "200" ] && echo "  ✓ https://sedhuhome.ai/dashboard → 200" || { echo "  ✗ dashboard → $code"; ok=false; }
echo "$health" | grep -q '"status":"ok"' && echo "  ✓ https://api.sedhuhome.ai/health → ok" || { echo "  ✗ health: $health"; ok=false; }

$ok && say "Deploy complete — https://sedhuhome.ai" || die "Deployed but verification failed — run ./deploy/deploy.sh --logs"
