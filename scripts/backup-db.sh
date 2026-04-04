#!/bin/bash
# PhxNorth Backend - PostgreSQL Database Backup
# Usage: ./scripts/backup-db.sh [output_dir]
#
# Creates a timestamped, gzip-compressed pg_dump backup via docker compose.
# Rotates old backups, keeping the most recent 7 by default.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${1:-${PROJECT_DIR}/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DB_NAME="phxnorth"
DB_USER="phxnorth"
BACKUP_FILE="phxnorth_${TIMESTAMP}.sql.gz"
KEEP_COUNT="${KEEP_COUNT:-7}"
COMPOSE_CMD="docker compose"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
}

fail() {
    log ERROR "$@"
    exit 1
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
preflight() {
    cd "$PROJECT_DIR"

    # Ensure docker compose is available
    if ! $COMPOSE_CMD version &>/dev/null; then
        fail "docker compose is not available"
    fi

    # Ensure postgres container is running
    local pg_running
    pg_running=$($COMPOSE_CMD ps --status running --format "{{.Service}}" 2>/dev/null \
        | grep -c "postgres" || echo "0")

    if [[ "$pg_running" -eq 0 ]]; then
        fail "PostgreSQL container is not running. Start services first."
    fi

    # Create output directory
    mkdir -p "$OUTPUT_DIR"
}

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
create_backup() {
    local backup_path="${OUTPUT_DIR}/${BACKUP_FILE}"

    log INFO "Starting database backup..."
    log INFO "Database : ${DB_NAME}"
    log INFO "Output   : ${backup_path}"

    # Run pg_dump inside the postgres container, pipe through gzip
    $COMPOSE_CMD exec -T postgres \
        pg_dump -U "$DB_USER" -d "$DB_NAME" \
            --no-owner \
            --no-acl \
            --clean \
            --if-exists \
        2>/dev/null \
        | gzip > "$backup_path"

    # Verify the backup was created and is non-empty
    if [[ ! -s "$backup_path" ]]; then
        rm -f "$backup_path"
        fail "Backup file is empty — pg_dump may have failed"
    fi

    local size
    size=$(du -h "$backup_path" | cut -f1)
    log OK "Backup created: ${backup_path} (${size})"
}

# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------
rotate_backups() {
    log INFO "Rotating backups (keeping last ${KEEP_COUNT})..."

    local count
    count=$(find "$OUTPUT_DIR" -maxdepth 1 -name "phxnorth_*.sql.gz" -type f | wc -l | tr -d ' ')

    if [[ "$count" -le "$KEEP_COUNT" ]]; then
        log INFO "Only ${count} backup(s) found, no rotation needed"
        return
    fi

    local to_remove
    to_remove=$((count - KEEP_COUNT))

    # Remove oldest backups (sorted by name, which is timestamp-based)
    find "$OUTPUT_DIR" -maxdepth 1 -name "phxnorth_*.sql.gz" -type f \
        | sort \
        | head -n "$to_remove" \
        | while read -r old_backup; do
            log INFO "Removing old backup: $(basename "$old_backup")"
            rm -f "$old_backup"
        done

    log OK "Rotated ${to_remove} old backup(s)"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local remaining
    remaining=$(find "$OUTPUT_DIR" -maxdepth 1 -name "phxnorth_*.sql.gz" -type f | wc -l | tr -d ' ')

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Database Backup Complete${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "  File      : ${BACKUP_FILE}"
    echo -e "  Directory : ${OUTPUT_DIR}"
    echo -e "  Backups   : ${remaining} stored"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log INFO "=== PhxNorth Database Backup ==="

    preflight
    create_backup
    rotate_backups
    print_summary
}

main "$@"
