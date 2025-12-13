#!/bin/bash
# ZDS CLI Pack/Unpack Example
#
# This script demonstrates ZDS archive operations:
# - Packing a store into a .zds archive
# - Unpacking a .zds archive
# - Working with packed data
#
# Prerequisites: Build the CLI first with `cargo build`
# Run: bash examples/cli/02_pack_unpack.sh

set -e

# Setup
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZIPPY="$PROJECT_ROOT/target/debug/zippy"
DATA_DIR="$SCRIPT_DIR/../data/cli_02_pack"

# Check if CLI is built
if [ ! -f "$ZIPPY" ]; then
    echo "Building CLI..."
    cd "$PROJECT_ROOT" && cargo build --quiet
fi

# Clean and setup
rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"

echo "============================================================"
echo "ZDS CLI Pack/Unpack Example"
echo "============================================================"
echo ""

# ============================================================
# Step 1: Create a store with data
# ============================================================
echo ">>> Step 1: Create a store with sample data"
$ZIPPY init "$DATA_DIR/source" -c products

# Add products
for i in {1..100}; do
    price=$(echo "scale=2; $RANDOM / 100" | bc)
    $ZIPPY put "$DATA_DIR/source" -c products "prod_$(printf '%03d' $i)" \
        --data "{\"name\": \"Product $i\", \"price\": $price, \"category\": \"Category $((i % 5 + 1))\"}"
done

echo "Created 100 products"
$ZIPPY stats "$DATA_DIR/source"
echo ""

# ============================================================
# Step 2: Pack into archive
# ============================================================
echo ">>> Step 2: Pack into .zds archive"
echo "$ zippy pack $DATA_DIR/source $DATA_DIR/products.zds"
$ZIPPY pack "$DATA_DIR/source" "$DATA_DIR/products.zds"
echo ""

# Show file sizes
echo "File sizes:"
echo "  Source folder: $(du -sh "$DATA_DIR/source" | cut -f1)"
echo "  Archive: $(ls -lh "$DATA_DIR/products.zds" | awk '{print $5}')"
echo ""

# ============================================================
# Step 3: Unpack the archive
# ============================================================
echo ">>> Step 3: Unpack the archive"
echo "$ zippy unpack $DATA_DIR/products.zds $DATA_DIR/restored"
$ZIPPY unpack "$DATA_DIR/products.zds" "$DATA_DIR/restored"
echo ""

# ============================================================
# Step 4: Verify restored data
# ============================================================
echo ">>> Step 4: Verify restored data"
echo "$ zippy validate $DATA_DIR/restored"
$ZIPPY validate "$DATA_DIR/restored"
echo ""

echo ">>> Compare statistics"
echo "Original:"
$ZIPPY stats "$DATA_DIR/source" --json
echo ""
echo "Restored:"
$ZIPPY stats "$DATA_DIR/restored" --json
echo ""

# ============================================================
# Step 5: Query restored data
# ============================================================
echo ">>> Step 5: Query restored data"
echo "$ zippy scan $DATA_DIR/restored -c products -l 5 --fields name,price"
$ZIPPY scan "$DATA_DIR/restored" -c products -l 5 --fields name,price
echo ""

# ============================================================
# Summary
# ============================================================
echo "============================================================"
echo "Pack/Unpack example completed successfully!"
echo ""
echo "Files created:"
echo "  - $DATA_DIR/source/        (original store)"
echo "  - $DATA_DIR/products.zds   (packed archive)"
echo "  - $DATA_DIR/restored/      (unpacked store)"
echo "============================================================"
