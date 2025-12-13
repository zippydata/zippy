#!/bin/bash
# ZDS CLI Data Pipeline Example
#
# This script demonstrates using ZDS CLI in data pipelines:
# - Reading from stdin
# - JSONL processing
# - Piping between commands
# - Integration with jq
#
# Prerequisites: Build the CLI first with `cargo build`
# Also requires: jq (for JSON processing)
# Run: bash examples/cli/03_data_pipeline.sh

set -e

# Setup
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZIPPY="$PROJECT_ROOT/target/debug/zippy"
DATA_DIR="$SCRIPT_DIR/../data/cli_03_pipeline"

# Check if CLI is built
if [ ! -f "$ZIPPY" ]; then
    echo "Building CLI..."
    cd "$PROJECT_ROOT" && cargo build --quiet
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Warning: jq not installed. Some examples will be skipped."
    echo "Install with: brew install jq (macOS) or apt install jq (Linux)"
    HAS_JQ=false
else
    HAS_JQ=true
fi

# Clean and setup
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "============================================================"
echo "ZDS CLI Data Pipeline Example"
echo "============================================================"
echo ""

# ============================================================
# Example 1: Put from stdin
# ============================================================
echo ">>> Example 1: Put document from stdin"
$ZIPPY init "$DATA_DIR" -c events

# Using heredoc
echo '{"type": "click", "page": "/home", "user_id": "u001"}' | $ZIPPY put "$DATA_DIR" -c events event_001
echo '{"type": "view", "page": "/products", "user_id": "u002"}' | $ZIPPY put "$DATA_DIR" -c events event_002
echo '{"type": "purchase", "page": "/checkout", "user_id": "u001", "amount": 99.99}' | $ZIPPY put "$DATA_DIR" -c events event_003

echo "Created 3 events from stdin"
$ZIPPY stats "$DATA_DIR"
echo ""

# ============================================================
# Example 2: Scan to JSONL and process with jq
# ============================================================
echo ">>> Example 2: Scan as JSONL"
echo "$ zippy scan ... --jsonl"
$ZIPPY scan "$DATA_DIR" -c events --jsonl
echo ""

if [ "$HAS_JQ" = true ]; then
    echo ">>> Filter with jq (purchases only)"
    echo '$ zippy scan ... --jsonl | jq '"'"'select(.type == "purchase")'"'"
    $ZIPPY scan "$DATA_DIR" -c events --jsonl | jq 'select(.type == "purchase")'
    echo ""

    echo ">>> Extract fields with jq"
    echo '$ zippy scan ... --jsonl | jq '"'"'{user: .user_id, action: .type}'"'"
    $ZIPPY scan "$DATA_DIR" -c events --jsonl | jq '{user: .user_id, action: .type}'
    echo ""
fi

# ============================================================
# Example 3: Batch import from JSONL file
# ============================================================
echo ">>> Example 3: Batch import from JSONL"

# Create sample JSONL data
cat > "$DATA_DIR/users.jsonl" << 'EOF'
{"name": "Alice", "email": "alice@example.com", "role": "admin"}
{"name": "Bob", "email": "bob@example.com", "role": "user"}
{"name": "Charlie", "email": "charlie@example.com", "role": "user"}
{"name": "Diana", "email": "diana@example.com", "role": "moderator"}
EOF

echo "Created users.jsonl with 4 records"

# Import each line
i=1
while read -r line; do
    echo "$line" | $ZIPPY put "$DATA_DIR" -c users "user_$(printf '%03d' $i)"
    i=$((i + 1))
done < "$DATA_DIR/users.jsonl"

echo "Imported $(($i - 1)) users"
$ZIPPY scan "$DATA_DIR" -c users
echo ""

# ============================================================
# Example 4: Export and transform
# ============================================================
echo ">>> Example 4: Export and transform"

if [ "$HAS_JQ" = true ]; then
    echo ">>> Export users with transformed fields"
    echo '$ zippy scan ... --jsonl | jq '"'"'{id: input_line_number, ...}'"'"
    $ZIPPY scan "$DATA_DIR" -c users --jsonl | jq -s 'to_entries | map({id: .key, name: .value.name, email: .value.email})'
    echo ""
fi

# ============================================================
# Example 5: Cross-collection aggregation
# ============================================================
echo ">>> Example 5: Cross-collection analysis"
echo ""
echo "Collections in store:"
$ZIPPY list "$DATA_DIR"
echo ""

echo "Document counts:"
echo "  events: $($ZIPPY scan "$DATA_DIR" -c events --jsonl | wc -l | tr -d ' ')"
echo "  users: $($ZIPPY scan "$DATA_DIR" -c users --jsonl | wc -l | tr -d ' ')"
echo ""

# ============================================================
# Example 6: Create backup script
# ============================================================
echo ">>> Example 6: Create backup with timestamp"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$DATA_DIR/backup_$TIMESTAMP.zds"

$ZIPPY pack "$DATA_DIR" "$BACKUP_FILE"
echo "Created backup: $BACKUP_FILE"
echo "Size: $(ls -lh "$BACKUP_FILE" | awk '{print $5}')"
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
echo "Pipeline example completed successfully!"
echo ""
echo "Demonstrated:"
echo "  - Reading JSON from stdin"
echo "  - JSONL output for streaming"
echo "  - Integration with jq for filtering/transformation"
echo "  - Batch import from files"
echo "  - Cross-collection workflows"
echo "  - Automated backups"
echo ""
echo "Data saved to: $DATA_DIR"
echo "============================================================"
