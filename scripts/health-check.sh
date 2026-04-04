#!/bin/bash
# PhxNorth Backend Health Check Verification
# Verifies all services are healthy after deployment
# Usage: ./scripts/health-check.sh
#
# Checks: API health, PostgreSQL, Redis, Kafka, Celery workers

set -uo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
API_URL="${API_URL:-http://localhost:8000}"
COMPOSE_CMD="docker compose"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Tracking
PASS=0
FAIL=0
CHECKS=()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
check_pass() {
    local name="$1"
    local detail="${2:-}"
    PASS=$((PASS + 1))
    CHECKS+=("${GREEN}PASS${NC}  ${name}${detail:+  (${detail})}")
    echo -e "  ${GREEN}PASS${NC}  ${name}${detail:+  (${detail})}"
}

check_fail() {
    local name="$1"
    local detail="${2:-}"
    FAIL=$((FAIL + 1))
    CHECKS+=("${RED}FAIL${NC}  ${name}${detail:+  (${detail})}")
    echo -e "  ${RED}FAIL${NC}  ${name}${detail:+  (${detail})}"
}

# ---------------------------------------------------------------------------
# 1. API Health Endpoint
# ---------------------------------------------------------------------------
check_api() {
    echo ""
    echo "Checking API health..."

    local response
    local http_code

    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout 5 --max-time 10 \
        "${API_URL}/api/v1/health" 2>/dev/null) || true

    if [[ "$http_code" == "200" ]]; then
        response=$(curl -s --connect-timeout 5 --max-time 10 \
            "${API_URL}/api/v1/health" 2>/dev/null)
        check_pass "API /api/v1/health" "HTTP ${http_code}"
    else
        check_fail "API /api/v1/health" "HTTP ${http_code:-timeout}"
    fi
}

# ---------------------------------------------------------------------------
# 2. PostgreSQL
# ---------------------------------------------------------------------------
check_postgres() {
    echo ""
    echo "Checking PostgreSQL..."

    local output
    output=$($COMPOSE_CMD exec -T postgres pg_isready -U phxnorth -d phxnorth 2>&1) || true

    if echo "$output" | grep -q "accepting connections"; then
        check_pass "PostgreSQL" "accepting connections"
    else
        check_fail "PostgreSQL" "${output}"
    fi

    # Additional: verify we can run a query
    local query_result
    query_result=$($COMPOSE_CMD exec -T postgres \
        psql -U phxnorth -d phxnorth -t -c "SELECT 1;" 2>&1) || true

    if echo "$query_result" | grep -q "1"; then
        check_pass "PostgreSQL query" "SELECT 1 succeeded"
    else
        check_fail "PostgreSQL query" "query failed"
    fi
}

# ---------------------------------------------------------------------------
# 3. Redis
# ---------------------------------------------------------------------------
check_redis() {
    echo ""
    echo "Checking Redis..."

    local output
    output=$($COMPOSE_CMD exec -T redis redis-cli ping 2>&1) || true

    if echo "$output" | grep -q "PONG"; then
        check_pass "Redis" "PONG"
    else
        check_fail "Redis" "${output}"
    fi

    # Check Redis info for connected clients
    local clients
    clients=$($COMPOSE_CMD exec -T redis redis-cli info clients 2>&1 \
        | grep "connected_clients" | tr -d '\r' || true)

    if [[ -n "$clients" ]]; then
        check_pass "Redis clients" "${clients}"
    else
        check_fail "Redis clients" "could not retrieve client info"
    fi
}

# ---------------------------------------------------------------------------
# 4. Kafka
# ---------------------------------------------------------------------------
check_kafka() {
    echo ""
    echo "Checking Kafka..."

    local output
    output=$($COMPOSE_CMD exec -T kafka \
        kafka-topics --bootstrap-server localhost:9092 --list 2>&1) || true

    if [[ $? -eq 0 ]] && ! echo "$output" | grep -qi "error\|exception\|refused"; then
        local topic_count
        topic_count=$(echo "$output" | grep -c '.' || echo "0")
        check_pass "Kafka broker" "${topic_count} topics listed"
    else
        check_fail "Kafka broker" "${output}"
    fi

    # Verify broker API is responsive
    local api_output
    api_output=$($COMPOSE_CMD exec -T kafka \
        kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1 | head -1) || true

    if echo "$api_output" | grep -qi "ApiVersion\|ApiKeys"; then
        check_pass "Kafka API" "broker API responsive"
    else
        check_fail "Kafka API" "broker API not responsive"
    fi
}

# ---------------------------------------------------------------------------
# 5. Celery Workers
# ---------------------------------------------------------------------------
check_celery() {
    echo ""
    echo "Checking Celery workers..."

    # Check if celery-worker container(s) are running
    local worker_count
    worker_count=$($COMPOSE_CMD ps --status running --format "{{.Service}}" 2>/dev/null \
        | grep -c "celery-worker" || echo "0")

    if [[ "$worker_count" -gt 0 ]]; then
        check_pass "Celery workers" "${worker_count} worker container(s) running"
    else
        check_fail "Celery workers" "no worker containers running"
    fi

    # Check if celery-beat container is running
    local beat_running
    beat_running=$($COMPOSE_CMD ps --status running --format "{{.Service}}" 2>/dev/null \
        | grep -c "celery-beat" || echo "0")

    if [[ "$beat_running" -gt 0 ]]; then
        check_pass "Celery beat" "scheduler running"
    else
        check_fail "Celery beat" "scheduler not running"
    fi

    # Attempt a celery inspect ping (may not work if broker isn't connected yet)
    local ping_result
    ping_result=$($COMPOSE_CMD exec -T celery-worker \
        poetry run celery -A app.workers.celery_app inspect ping 2>&1 || true)

    if echo "$ping_result" | grep -q "pong\|OK"; then
        check_pass "Celery inspect ping" "workers responding"
    else
        check_fail "Celery inspect ping" "workers not responding (may still be starting)"
    fi
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local total=$((PASS + FAIL))

    echo ""
    echo "========================================="
    echo "  Health Check Summary"
    echo "========================================="
    echo ""

    for check in "${CHECKS[@]}"; do
        echo -e "  ${check}"
    done

    echo ""
    echo "-----------------------------------------"
    echo -e "  Total : ${total}"
    echo -e "  ${GREEN}Pass${NC}  : ${PASS}"
    echo -e "  ${RED}Fail${NC}  : ${FAIL}"
    echo "-----------------------------------------"

    if [[ $FAIL -gt 0 ]]; then
        echo ""
        echo -e "  ${YELLOW}WARNING: ${FAIL} check(s) failed${NC}"
        echo ""
        return 1
    else
        echo ""
        echo -e "  ${GREEN}All checks passed${NC}"
        echo ""
        return 0
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    cd "$PROJECT_DIR"

    echo "========================================="
    echo "  PhxNorth Health Check"
    echo "========================================="

    check_api
    check_postgres
    check_redis
    check_kafka
    check_celery

    print_summary
}

main "$@"
