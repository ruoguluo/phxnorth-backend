#!/bin/bash
# PhxNorth Backend Deploy Script
# Usage: ./scripts/deploy.sh [environment]
# Environment: production (default), staging

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${1:-production}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${PROJECT_DIR}/logs/deploy_${TIMESTAMP}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local level="$1"
    shift
    local msg="$*"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"

    case "$level" in
        INFO)  echo -e "${BLUE}[INFO]${NC}  ${ts}  ${msg}" ;;
        OK)    echo -e "${GREEN}[OK]${NC}    ${ts}  ${msg}" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC}  ${ts}  ${msg}" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} ${ts}  ${msg}" ;;
    esac

    # Append to log file
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "[${level}] ${ts} ${msg}" >> "$LOG_FILE"
}

fail() {
    log ERROR "$@"
    log ERROR "Deployment FAILED. Check log: ${LOG_FILE}"
    exit 1
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    log INFO "Running pre-flight checks..."

    # Verify we're in the project directory
    if [[ ! -f "${PROJECT_DIR}/docker-compose.yml" ]]; then
        fail "docker-compose.yml not found in ${PROJECT_DIR}"
    fi

    # Verify docker is available
    if ! command -v docker &>/dev/null; then
        fail "docker is not installed or not in PATH"
    fi

    # Verify docker compose is available
    if ! docker compose version &>/dev/null; then
        fail "docker compose plugin is not available"
    fi

    # Verify environment file exists
    local env_file="${PROJECT_DIR}/.env.${ENVIRONMENT}"
    if [[ ! -f "$env_file" ]]; then
        fail "Environment file not found: ${env_file}"
    fi

    # Validate environment value
    if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "staging" ]]; then
        fail "Invalid environment: ${ENVIRONMENT}. Must be 'production' or 'staging'."
    fi

    log OK "Pre-flight checks passed"
}

# ---------------------------------------------------------------------------
# Step 1: Pull latest code
# ---------------------------------------------------------------------------
pull_code() {
    log INFO "Pulling latest code from origin..."
    cd "$PROJECT_DIR"

    local current_branch
    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    log INFO "Current branch: ${current_branch}"

    git pull origin "$current_branch" || fail "git pull failed"

    local commit
    commit="$(git rev-parse --short HEAD)"
    log OK "Code updated to commit ${commit}"
}

# ---------------------------------------------------------------------------
# Step 2: Database backup
# ---------------------------------------------------------------------------
backup_database() {
    log INFO "Running pre-deploy database backup..."

    local backup_dir="${PROJECT_DIR}/backups"
    "${SCRIPT_DIR}/backup-db.sh" "$backup_dir" || fail "Database backup failed"

    log OK "Database backup completed"
}

# ---------------------------------------------------------------------------
# Step 3: Build Docker images
# ---------------------------------------------------------------------------
build_images() {
    log INFO "Building Docker images for ${ENVIRONMENT}..."
    cd "$PROJECT_DIR"

    docker compose ${COMPOSE_FILES} \
        --env-file ".env.${ENVIRONMENT}" \
        build --no-cache || fail "Docker image build failed"

    log OK "Docker images built successfully"
}

# ---------------------------------------------------------------------------
# Step 4: Run database migrations
# ---------------------------------------------------------------------------
run_migrations() {
    log INFO "Running database migrations..."
    cd "$PROJECT_DIR"

    # Ensure postgres is up before migrating
    docker compose ${COMPOSE_FILES} \
        --env-file ".env.${ENVIRONMENT}" \
        up -d postgres

    # Wait for postgres to be healthy
    local retries=30
    while [[ $retries -gt 0 ]]; do
        if docker compose ${COMPOSE_FILES} exec -T postgres pg_isready -U phxnorth -d phxnorth &>/dev/null; then
            break
        fi
        retries=$((retries - 1))
        sleep 2
    done

    if [[ $retries -eq 0 ]]; then
        fail "PostgreSQL did not become ready in time"
    fi

    # Run alembic migrations via the api container
    docker compose ${COMPOSE_FILES} \
        --env-file ".env.${ENVIRONMENT}" \
        run --rm --no-deps api \
        poetry run alembic upgrade head || fail "Database migration failed"

    log OK "Database migrations applied"
}

# ---------------------------------------------------------------------------
# Step 5: Restart services
# ---------------------------------------------------------------------------
restart_services() {
    log INFO "Restarting services with docker compose..."
    cd "$PROJECT_DIR"

    # Bring everything up (will recreate changed containers)
    docker compose ${COMPOSE_FILES} \
        --env-file ".env.${ENVIRONMENT}" \
        up -d --remove-orphans || fail "docker compose up failed"

    log OK "Services started"
}

# ---------------------------------------------------------------------------
# Step 6: Wait for services to be healthy
# ---------------------------------------------------------------------------
wait_for_health() {
    log INFO "Waiting for services to become healthy..."

    local timeout=120
    local elapsed=0
    local interval=5

    while [[ $elapsed -lt $timeout ]]; do
        # Check if all services are healthy/running
        local unhealthy
        unhealthy=$(docker compose ${COMPOSE_FILES} ps --format json 2>/dev/null \
            | grep -c '"unhealthy"\|"starting"' || true)

        if [[ "$unhealthy" -eq 0 ]]; then
            # Double-check that all expected services are running
            local running
            running=$(docker compose ${COMPOSE_FILES} ps --status running --format json 2>/dev/null \
                | wc -l | tr -d ' ')

            if [[ "$running" -ge 5 ]]; then
                log OK "All services are healthy (${running} running)"
                return 0
            fi
        fi

        sleep "$interval"
        elapsed=$((elapsed + interval))
        log INFO "Waiting... (${elapsed}s / ${timeout}s)"
    done

    log WARN "Timed out waiting for all services to become healthy"
    docker compose ${COMPOSE_FILES} ps
    return 1
}

# ---------------------------------------------------------------------------
# Step 7: Health check verification
# ---------------------------------------------------------------------------
verify_health() {
    log INFO "Running health check verification..."

    "${SCRIPT_DIR}/health-check.sh" || {
        log WARN "Health check reported failures — review output above"
        return 1
    }

    log OK "Health check verification passed"
}

# ---------------------------------------------------------------------------
# Step 8: Deployment summary
# ---------------------------------------------------------------------------
print_summary() {
    local commit
    commit="$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"
    local branch
    branch="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Deployment Complete${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "  Environment : ${BLUE}${ENVIRONMENT}${NC}"
    echo -e "  Branch      : ${BLUE}${branch}${NC}"
    echo -e "  Commit      : ${BLUE}${commit}${NC}"
    echo -e "  Timestamp   : ${BLUE}${TIMESTAMP}${NC}"
    echo -e "  Log file    : ${LOG_FILE}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    log INFO "=== PhxNorth Backend Deployment ==="
    log INFO "Environment: ${ENVIRONMENT}"
    log INFO "Project dir: ${PROJECT_DIR}"
    echo ""

    preflight
    pull_code
    backup_database
    build_images
    run_migrations
    restart_services

    if wait_for_health; then
        verify_health
    fi

    print_summary
}

main "$@"
