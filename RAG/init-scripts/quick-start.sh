#!/bin/bash
# ============================================
# Quick Start Script for Database Setup
# ============================================
# This script provides easy commands for setting up and managing
# the AI Officer databases with sample executive data.
# ============================================

set -e

echo 'Bundled persona setup was retired. Follow docs/firstweek/ for private workspace setup. No database changes were made.' >&2
exit 1

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Print banner
print_banner() {
    echo -e "${CYAN}"
    echo "============================================"
    echo "  AI Officer - Database Quick Start"
    echo "============================================"
    echo -e "${NC}"
}

# Print menu
print_menu() {
    echo -e "${BLUE}Available Commands:${NC}"
    echo ""
    echo "  1) setup          - Fresh setup: start databases + load sample data"
    echo "  2) reset-and-load - Reset BOTH databases and load fresh sample data"
    echo "  3) status         - Check database status and data counts"
    echo "  4) load-sample    - Load sample executive data (without reset)"
    echo "  5) backup         - Create new backup dump from current data"
    echo "  6) logs           - View database logs"
    echo "  7) help           - Show detailed help"
    echo "  8) exit           - Exit"
    echo ""
}

# Fresh setup - start databases and load data
fresh_setup() {
    echo -e "${GREEN}Starting fresh database setup...${NC}"
    echo ""

    echo "This will:"
    echo "  1. Start PostgreSQL and Neo4j containers"
    echo "  2. Wait for databases to be ready"
    echo "  3. Load sample executive data with embeddings"
    echo ""

    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Setup cancelled"
        return 0
    fi

    echo ""
    echo -e "${GREEN}Starting database services...${NC}"
    cd "$PROJECT_ROOT"
    docker-compose up -d rag-postgres neo4j redis

    echo ""
    echo "Waiting for databases to be ready (this may take 30-60 seconds)..."
    sleep 10

    # Wait for postgres
    echo "Checking PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T rag-postgres pg_isready -U postgres > /dev/null 2>&1; then
            echo -e "${GREEN}PostgreSQL is ready${NC}"
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 2
    done

    # Wait for neo4j
    echo "Checking Neo4j..."
    for i in {1..30}; do
        if docker-compose exec -T neo4j cypher-shell -u neo4j -p neo4j123 "RETURN 1" > /dev/null 2>&1; then
            echo -e "${GREEN}Neo4j is ready${NC}"
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 2
    done

    echo ""
    echo -e "${GREEN}Loading sample data...${NC}"
    echo ""

    # Run the data loader via Docker
    docker-compose --profile init up load-sample-data

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  Fresh setup complete!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Start the API: docker-compose up -d rag-api"
    echo "  - Check status: ./quick-start.sh status"
    echo "  - Test API: http://localhost:8000/docs"
}

# Reset and load fresh data
reset_and_load() {
    echo -e "${YELLOW}WARNING: This will DELETE ALL DATA and load fresh sample data!${NC}"
    echo ""
    echo "This affects:"
    echo "  - PostgreSQL: All tables will be truncated"
    echo "  - Neo4j: All nodes and relationships will be deleted"
    echo ""

    read -p "Type 'RESET' to confirm: " confirm
    if [ "$confirm" != "RESET" ]; then
        echo "Reset cancelled"
        return 0
    fi

    echo ""
    echo "Options:"
    echo "  1) Reset and load with embeddings (slower, ~5-10 min)"
    echo "  2) Reset and load without embeddings (faster, ~1 min)"
    echo ""
    read -p "Select option (1-2): " load_option

    cd "$PROJECT_ROOT"

    case $load_option in
        1)
            echo ""
            echo -e "${GREEN}Resetting databases and loading data with embeddings...${NC}"
            docker-compose --profile reset up reset-databases
            ;;
        2)
            echo ""
            echo -e "${GREEN}Resetting databases and loading data without embeddings...${NC}"
            SKIP_EMBEDDINGS=true docker-compose --profile reset up reset-databases
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            return 1
            ;;
    esac

    echo ""
    echo -e "${GREEN}Reset and load complete!${NC}"
}

# Check database status
check_status() {
    echo -e "${BLUE}Checking database status...${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    # Check if postgres is running
    if docker-compose ps rag-postgres 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}[OK]${NC} PostgreSQL is running"

        # Check table counts
        echo ""
        echo "PostgreSQL Data Counts:"
        docker-compose exec -T rag-postgres psql -U postgres -d ai_officer -t -c "
            SELECT 'Executive Profiles: ' || COUNT(*) FROM executive_profiles
            UNION ALL
            SELECT 'Decision Cases: ' || COUNT(*) FROM decision_cases
            UNION ALL
            SELECT 'Policy Documents: ' || COUNT(*) FROM policy_documents
            UNION ALL
            SELECT 'Document Sections: ' || COUNT(*) FROM document_sections
            UNION ALL
            SELECT 'Embeddings: ' || COUNT(*) FROM embeddings;
        " 2>/dev/null | grep -v "^$" || echo "  (Could not query tables)"
    else
        echo -e "${RED}[DOWN]${NC} PostgreSQL is not running"
    fi

    echo ""

    # Check if neo4j is running
    if docker-compose ps neo4j 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}[OK]${NC} Neo4j is running"

        # Check node counts
        echo ""
        echo "Neo4j Node Counts:"
        docker-compose exec -T neo4j cypher-shell -u neo4j -p neo4j123 \
            "MATCH (n) RETURN labels(n)[0] AS Label, count(n) AS Count ORDER BY Count DESC LIMIT 10" \
            2>/dev/null | tail -n +2 || echo "  (Could not query nodes)"
    else
        echo -e "${RED}[DOWN]${NC} Neo4j is not running"
    fi

    echo ""

    # Check if redis is running
    if docker-compose ps redis 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}[OK]${NC} Redis is running"
    else
        echo -e "${YELLOW}[DOWN]${NC} Redis is not running (optional)"
    fi

    echo ""

    # Check if API is running
    if docker-compose ps rag-api 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}[OK]${NC} RAG API is running"
        echo "  API URL: http://localhost:8000"
        echo "  Docs: http://localhost:8000/docs"
    else
        echo -e "${YELLOW}[DOWN]${NC} RAG API is not running"
        echo "  Start with: docker-compose up -d rag-api"
    fi
}

# Load sample data (without reset)
load_sample_data() {
    echo -e "${GREEN}Loading sample executive data...${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    # Check if postgres is running
    if ! docker-compose ps rag-postgres 2>/dev/null | grep -q "Up"; then
        echo -e "${RED}Error: PostgreSQL is not running${NC}"
        echo "Run: docker-compose up -d rag-postgres"
        return 1
    fi

    echo "Options:"
    echo "  1) Load with embeddings (slower, ~5-10 min)"
    echo "  2) Load without embeddings (fast, ~30 sec)"
    echo "  3) Force reload all data (overwrite existing)"
    echo ""
    read -p "Select option (1-3): " load_option

    case $load_option in
        1)
            echo ""
            echo -e "${GREEN}Loading data with embeddings...${NC}"
            docker-compose --profile init up load-sample-data
            ;;
        2)
            echo ""
            echo -e "${GREEN}Loading data without embeddings...${NC}"
            SKIP_EMBEDDINGS=true docker-compose --profile init up load-sample-data
            ;;
        3)
            echo ""
            echo -e "${YELLOW}Force reloading all data...${NC}"
            FORCE_LOAD=true docker-compose --profile init up load-sample-data
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            return 1
            ;;
    esac

    echo ""
    echo -e "${GREEN}sample data loading complete!${NC}"
}

# Create backup
create_backup() {
    echo -e "${BLUE}Creating database backup...${NC}"
    echo ""

    cd "$PROJECT_ROOT"

    # Check if postgres is running
    if ! docker-compose ps rag-postgres 2>/dev/null | grep -q "Up"; then
        echo -e "${RED}Error: PostgreSQL is not running${NC}"
        return 1
    fi

    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_file="RAG/dumps/ai_officer_backup_${timestamp}.dump"

    echo "Creating backup: $backup_file"
    docker-compose exec -T rag-postgres pg_dump -U postgres -d ai_officer -F c > "$backup_file"

    echo ""
    echo -e "${GREEN}Backup created successfully!${NC}"
    echo "File: $backup_file"
    echo "Size: $(du -h "$backup_file" | cut -f1)"

    echo ""
    read -p "Replace main ai_officer_backup.dump with this backup? (yes/no): " replace

    if [ "$replace" = "yes" ]; then
        cp "$backup_file" "RAG/dumps/ai_officer_backup.dump"
        echo -e "${GREEN}RAG/dumps/ai_officer_backup.dump updated${NC}"
    fi
}

# View logs
view_logs() {
    echo -e "${BLUE}Viewing database logs...${NC}"
    echo ""
    echo "Select service:"
    echo "  1) PostgreSQL"
    echo "  2) Neo4j"
    echo "  3) RAG API"
    echo "  4) All services"
    echo ""
    read -p "Select option (1-4): " log_option

    cd "$PROJECT_ROOT"

    case $log_option in
        1)
            docker-compose logs --tail=100 rag-postgres
            ;;
        2)
            docker-compose logs --tail=100 neo4j
            ;;
        3)
            docker-compose logs --tail=100 rag-api
            ;;
        4)
            docker-compose logs --tail=50 rag-postgres neo4j rag-api
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
}

# Show help
show_help() {
    cat << EOF
${CYAN}============================================
AI Officer Database Quick Start - Help
============================================${NC}

${BLUE}FOR TEAMMATES - FIRST TIME SETUP:${NC}

  ${GREEN}./quick-start.sh setup${NC}
    Complete fresh setup for new team members:
    1. Starts PostgreSQL, Neo4j, and Redis containers
    2. Waits for databases to be ready
    3. Loads sample executive data with embeddings

    This is the recommended way to get started!

${BLUE}COMMANDS:${NC}

  ${GREEN}setup${NC}
    Fresh setup for new team members.
    Starts databases and loads all sample data.

  ${GREEN}reset-and-load${NC}
    Reset BOTH databases and load fresh sample data.
    Use when you need to completely refresh your data.
    WARNING: This deletes all existing data!

  ${GREEN}status${NC}
    Check database status and show data counts.
    Verifies PostgreSQL, Neo4j, Redis, and API are running.

  ${GREEN}load-sample${NC}
    Load sample data without resetting databases.
    Use when adding to existing data or updating.

  ${GREEN}backup${NC}
    Create a new backup dump of current database.
    Saves to RAG/dumps/ directory.

  ${GREEN}logs${NC}
    View logs from database services.

${BLUE}DOCKER COMMANDS:${NC}

  # Fresh setup with sample data
  docker-compose up -d rag-postgres neo4j redis
  docker-compose --profile init up load-sample-data

  # Reset and reload everything
  docker-compose --profile reset up reset-databases

  # Start the API
  docker-compose up -d rag-api

  # View all running services
  docker-compose ps

${BLUE}ENVIRONMENT VARIABLES:${NC}

  SKIP_EMBEDDINGS=true   Skip embedding generation (faster)
  FORCE_LOAD=true        Overwrite existing data
  LOAD_DATA=false        Skip data loading after reset

${BLUE}DATA LOCATIONS:${NC}

  Executive Profile:  RAG/test_data/executive_profiles/sample_profile.json
  Voiceprint:         RAG/test_data/voiceprints/sample_profile_voiceprint.json
  Policies:           RAG/test_data/policies/*.md
  Meeting Notes:      RAG/test_data/documents/meeting_notes/*.md
  Presentations:      RAG/test_data/documents/presentations/*.md
  Entities:           RAG/test_data/entities/*.json
  Slack Messages:     RAG/docs/sample_data/slack messages.md

${BLUE}EXAMPLES:${NC}

  # New team member setup
  ./quick-start.sh setup

  # Check what's in the database
  ./quick-start.sh status

  # Refresh all data
  ./quick-start.sh reset-and-load

  # Quick load without embeddings (for testing)
  SKIP_EMBEDDINGS=true docker-compose --profile init up load-sample-data

EOF
}

# Interactive mode
interactive_mode() {
    while true; do
        print_menu
        read -p "Select option (1-8): " choice
        echo ""

        case $choice in
            1)
                fresh_setup
                ;;
            2)
                reset_and_load
                ;;
            3)
                check_status
                ;;
            4)
                load_sample_data
                ;;
            5)
                create_backup
                ;;
            6)
                view_logs
                ;;
            7)
                show_help
                ;;
            8)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                ;;
        esac

        echo ""
        read -p "Press Enter to continue..."
        clear
        print_banner
    done
}

# Main
main() {
    print_banner

    if [ $# -eq 0 ]; then
        # No arguments - interactive mode
        interactive_mode
    else
        # Command line mode
        case $1 in
            setup)
                fresh_setup
                ;;
            reset-and-load)
                reset_and_load
                ;;
            status)
                check_status
                ;;
            load-sample)
                load_sample_data
                ;;
            backup)
                create_backup
                ;;
            logs)
                view_logs
                ;;
            help|--help|-h)
                show_help
                ;;
            *)
                echo -e "${RED}Unknown command: $1${NC}"
                echo ""
                echo "Available commands:"
                echo "  setup, reset-and-load, status, load-sample, backup, logs, help"
                echo ""
                echo "Run without arguments for interactive mode"
                exit 1
                ;;
        esac
    fi
}

main "$@"
