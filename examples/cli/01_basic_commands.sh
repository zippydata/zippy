#!/bin/bash
# ZDS CLI Basic Commands Example
#
# This script demonstrates basic ZDS CLI operations:
# - Initializing stores
# - CRUD operations (put, get, delete)
# - Listing and scanning
# - Store statistics
#
# Prerequisites: Build the CLI first with `cargo build`
# Run: bash examples/cli/01_basic_commands.sh

set -e

# Setup
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZIPPY="$PROJECT_ROOT/target/debug/zippy"
DATA_DIR="$SCRIPT_DIR/../data/cli_01_basic"

# Check if CLI is built
if [ ! -f "$ZIPPY" ]; then
    echo "Building CLI..."
    cd "$PROJECT_ROOT" && cargo build --quiet
fi

# Clean and setup
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "============================================================"
echo "ZDS CLI Basic Commands Example"
echo "============================================================"
echo ""

# ============================================================
# Example 1: Initialize a store
# ============================================================
echo ">>> Example 1: Initialize a store"
echo "$ zippy init $DATA_DIR -c users"
$ZIPPY init "$DATA_DIR" -c users
echo ""

# ============================================================
# Example 2: Put documents
# ============================================================
echo ">>> Example 2: Put documents"
echo "$ zippy put ... --data '{...}'"

$ZIPPY put "$DATA_DIR" -c users user_001 --data '{"name": "Alice Smith", "email": "alice@example.com", "age": 28}'
$ZIPPY put "$DATA_DIR" -c users user_002 --data '{"name": "Bob Jones", "email": "bob@example.com", "age": 35}'
$ZIPPY put "$DATA_DIR" -c users user_003 --data '{"name": "Charlie Brown", "email": "charlie@example.com", "age": 42}'

echo "Added 3 users"
echo ""

# ============================================================
# Example 3: Get a document
# ============================================================
echo ">>> Example 3: Get a document"
echo "$ zippy get $DATA_DIR -c users user_001 --pretty"
$ZIPPY get "$DATA_DIR" -c users user_001 --pretty
echo ""

# ============================================================
# Example 4: List collections
# ============================================================
echo ">>> Example 4: List collections"
echo "$ zippy list $DATA_DIR"
$ZIPPY list "$DATA_DIR"
echo ""

# ============================================================
# Example 5: Scan documents
# ============================================================
echo ">>> Example 5: Scan all documents"
echo "$ zippy scan $DATA_DIR -c users"
$ZIPPY scan "$DATA_DIR" -c users
echo ""

echo ">>> Scan with limit"
echo "$ zippy scan $DATA_DIR -c users -l 2"
$ZIPPY scan "$DATA_DIR" -c users -l 2
echo ""

echo ">>> Scan with field projection"
echo "$ zippy scan $DATA_DIR -c users --fields name,email"
$ZIPPY scan "$DATA_DIR" -c users --fields name,email
echo ""

echo ">>> Scan as JSONL"
echo "$ zippy scan $DATA_DIR -c users --jsonl"
$ZIPPY scan "$DATA_DIR" -c users --jsonl
echo ""

# ============================================================
# Example 6: Show statistics
# ============================================================
echo ">>> Example 6: Show statistics"
echo "$ zippy stats $DATA_DIR"
$ZIPPY stats "$DATA_DIR"
echo ""

echo ">>> Stats as JSON"
echo "$ zippy stats $DATA_DIR --json"
$ZIPPY stats "$DATA_DIR" --json
echo ""

# ============================================================
# Example 7: Delete a document
# ============================================================
echo ">>> Example 7: Delete a document"
echo "$ zippy delete $DATA_DIR -c users user_002"
$ZIPPY delete "$DATA_DIR" -c users user_002
echo ""

echo ">>> Verify deletion"
echo "$ zippy scan $DATA_DIR -c users --fields name"
$ZIPPY scan "$DATA_DIR" -c users --fields name
echo ""

# ============================================================
# Example 8: Validate store
# ============================================================
echo ">>> Example 8: Validate store"
echo "$ zippy validate $DATA_DIR"
$ZIPPY validate "$DATA_DIR"
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
echo "Example completed successfully!"
echo "Data saved to: $DATA_DIR"
echo "============================================================"
