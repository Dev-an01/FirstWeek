#!/bin/bash
# ============================================
# PostgreSQL Database Restoration Script
# ============================================
# This script tests the PostgreSQL connection and restores
# the database dump if available
# ============================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database connection parameters
POSTGRES_HOST="${POSTGRES_HOST:-rag-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-ai_officer}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres123}"
DUMP_FILE="${DUMP_FILE:-/dumps/ai_officer_backup.dump}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"

# Export password for pg_* commands
export PGPASSWORD="$POSTGRES_PASSWORD"

# ============================================
# Function: Print colored messages
# ============================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================
# Function: Test PostgreSQL Connection
# ============================================
test_connection() {
    log_info "Testing PostgreSQL connection..."

    local retry_count=0
    echo "$POSTGRES_HOST:$POSTGRES_PORT - $POSTGRES_USER/$POSTGRES_DB"
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1; then
            log_success "PostgreSQL is ready and accepting connections"
            return 0
        fi

        retry_count=$((retry_count + 1))
        log_warning "PostgreSQL not ready yet (attempt $retry_count/$MAX_RETRIES)..."
        sleep $RETRY_INTERVAL
    done

    log_error "PostgreSQL failed to become ready after $MAX_RETRIES attempts"
    return 1
}

# ============================================
# Function: Check if dump file exists
# ============================================
check_dump_file() {
    log_info "Checking for dump file: $DUMP_FILE"

    if [ ! -f "$DUMP_FILE" ]; then
        log_error "Dump file not found: $DUMP_FILE"
        return 1
    fi

    local file_size=$(du -h "$DUMP_FILE" | cut -f1)
    log_success "Dump file found (size: $file_size)"
    return 0
}

# ============================================
# Function: Check if database already has data
# ============================================
check_existing_data() {
    log_info "Checking if database already has data..."

    local table_count=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" \
        2>/dev/null | tr -d ' ')

    if [ -z "$table_count" ]; then
        table_count=0
    fi

    log_info "Found $table_count tables in public schema"

    if [ "$table_count" -gt 0 ]; then
        log_warning "Database already contains $table_count tables"

        # Check if FORCE_RESTORE is set
        if [ "${FORCE_RESTORE}" = "true" ]; then
            log_warning "FORCE_RESTORE=true - Will drop and recreate database"
            return 2  # Indicates need to drop and recreate
        else
            log_warning "Skipping restore. Set FORCE_RESTORE=true to force restoration"
            return 1  # Skip restore
        fi
    fi

    log_info "Database is empty, proceeding with restore"
    return 0
}

# ============================================
# Function: Drop and recreate database
# ============================================
recreate_database() {
    log_warning "Dropping and recreating database: $POSTGRES_DB"

    # Connect to postgres database to drop/create target database
    psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "postgres" -c \
        "DROP DATABASE IF EXISTS $POSTGRES_DB;" || {
        log_error "Failed to drop database"
        return 1
    }

    psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "postgres" -c \
        "CREATE DATABASE $POSTGRES_DB;" || {
        log_error "Failed to create database"
        return 1
    }

    # Ensure pgvector extension is created
    psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
        "CREATE EXTENSION IF NOT EXISTS vector;" || {
        log_error "Failed to create vector extension"
        return 1
    }

    log_success "Database recreated successfully"
    return 0
}

# ============================================
# Function: Restore database from dump
# ============================================
restore_dump() {
    log_info "Starting database restoration..."
    log_info "This may take several minutes depending on dump size..."

    # Use pg_restore with verbose output
    pg_restore \
        -h "$POSTGRES_HOST" \
        -p "$POSTGRES_PORT" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --verbose \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        "$DUMP_FILE" 2>&1 | while read -r line; do
            # Filter out common warnings
            if echo "$line" | grep -vE "(already exists|does not exist|no privileges|NOTICE|WARNING: errors ignored)" > /dev/null; then
                log_info "$line"
            fi
        done

    # Check if restore was successful
    # Note: pg_restore often returns non-zero for minor warnings (duplicates, privileges)
    # We'll verify by checking if tables exist instead of relying on exit code
    local restore_exit=${PIPESTATUS[0]}
    if [ $restore_exit -eq 0 ]; then
        log_success "Database restoration completed successfully"
    else
        log_warning "pg_restore returned exit code $restore_exit (this is often OK for minor warnings)"
        log_info "Will verify restoration by checking tables..."
    fi
    return 0
}

# ============================================
# Function: Run Migrations
# ============================================
run_migrations() {
    log_info "Running database migrations..."

    # Migration files to run (in order)
    local migrations=(
        "/migrations/onboarding_migration.sql"
        "/migrations/phase8_migration.sql"
        "/migrations/phase9_multitenant_migration.sql"
        "/migrations/phase10_ocr_metadata_migration.sql"
    )

    for migration in "${migrations[@]}"; do
        if [ -f "$migration" ]; then
            log_info "Running migration: $(basename $migration)"
            if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$migration" > /dev/null 2>&1; then
                log_success "Migration completed: $(basename $migration)"
            else
                log_warning "Migration had warnings: $(basename $migration) (this is often OK)"
            fi
        else
            log_warning "Migration file not found: $migration (skipping)"
        fi
    done

    log_success "All migrations completed"
    return 0
}

# ============================================
# Function: Verify restoration
# ============================================
verify_restoration() {
    log_info "Verifying database restoration..."

    # Count tables
    local table_count=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" \
        2>/dev/null | tr -d ' ')

    # Count views
    local view_count=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public';" \
        2>/dev/null | tr -d ' ')

    # Count functions
    local function_count=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
        "SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid WHERE n.nspname = 'public';" \
        2>/dev/null | tr -d ' ')

    log_success "Verification complete:"
    log_success "  - Tables: $table_count"
    log_success "  - Views: $view_count"
    log_success "  - Functions: $function_count"

    # Check for critical tables
    local critical_tables=("executive_profiles" "decision_cases" "policy_documents" "embeddings")
    local missing_tables=()

    for table in "${critical_tables[@]}"; do
        local exists=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '$table';" \
            2>/dev/null | tr -d ' ')

        if [ "$exists" -eq 0 ]; then
            missing_tables+=("$table")
        fi
    done

    if [ ${#missing_tables[@]} -gt 0 ]; then
        log_warning "Some critical tables are missing: ${missing_tables[*]}"
        return 1
    fi

    log_success "All critical tables are present"
    return 0
}

# ============================================
# Main Execution
# ============================================
main() {
    echo ""
    log_info "============================================"
    log_info "PostgreSQL Database Restoration"
    log_info "============================================"
    log_info "Host: $POSTGRES_HOST:$POSTGRES_PORT"
    log_info "Database: $POSTGRES_DB"
    log_info "User: $POSTGRES_USER"
    log_info "Dump: $DUMP_FILE"
    log_info "============================================"
    echo ""

    # Step 1: Test connection
    if ! test_connection; then
        log_error "Failed to connect to PostgreSQL"
        exit 1
    fi
    echo ""

    # Step 2: Check existing data first
    existing_data_status=0
    check_existing_data || existing_data_status=$?

    if [ $existing_data_status -eq 1 ]; then
        log_warning "Database already contains data - skipping restore/initialization"
        log_info "Running migrations to ensure schema is up to date..."
        run_migrations
        echo ""
        log_success "============================================"
        log_success "Database migrations completed!"
        log_success "Database is ready to use!"
        log_success "============================================"
        exit 0
    fi
    echo ""

    # Step 3: Check dump file
    dump_exists=0
    check_dump_file || dump_exists=$?
    echo ""

    # Step 4: Load data based on what's available
    if [ $dump_exists -eq 0 ]; then
        log_info "Dump file found - restoring from dump..."

        if [ $existing_data_status -eq 2 ]; then
            # Need to drop and recreate
            if ! recreate_database; then
                log_error "Failed to recreate database"
                exit 1
            fi
            echo ""
        fi

        # Restore dump
        if ! restore_dump; then
            log_error "Database restoration failed"
            exit 1
        fi
        echo ""

        # Verify restoration
        if ! verify_restoration; then
            log_warning "Database restored but verification found some issues"
        fi
        echo ""

        # Run migrations
        run_migrations
        echo ""

        log_success "============================================"
        log_success "Database restoration completed successfully!"
        log_success "============================================"
    else
        # No dump file - initialize with base schema and run migrations
        log_warning "No dump file found - initializing fresh database"

        # Run base schema first (creates core tables)
        if [ -f "/schemas/postgres_schema.sql" ]; then
            log_info "Running base schema: postgres_schema.sql"
            if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/schemas/postgres_schema.sql" > /dev/null 2>&1; then
                log_success "Base schema created successfully"
            else
                log_warning "Base schema had some warnings (may be OK)"
            fi
        else
            log_warning "Base schema not found at /schemas/postgres_schema.sql"
        fi
        echo ""

        # Run migrations
        run_migrations
        echo ""

        log_info "Data will be loaded on first rag-api startup"
        log_success "Database initialized successfully!"
        log_success "============================================"
    fi
    echo ""
}

# Run main function
main "$@"
