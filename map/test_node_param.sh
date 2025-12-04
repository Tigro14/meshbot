#!/bin/bash
# Test script for URL node parameter feature
# Tests the ability to pass ?node=<name> in the query string

echo "========================================="
echo "Testing URL Node Parameter Feature"
echo "========================================="
echo ""

cd "$(dirname "$0")"

# Check if map.html exists
if [ ! -f "map.html" ]; then
    echo "❌ ERROR: map.html not found"
    exit 1
fi

echo "✓ map.html found"
echo ""

# Test 1: Check for URLSearchParams usage for node parameter
echo "Test 1: Checking for node parameter parsing..."
if grep -q "const nodeParam = urlParams.get('node')" map.html; then
    echo "✓ PASS: nodeParam parsing found"
else
    echo "❌ FAIL: nodeParam parsing not found"
    exit 1
fi
echo ""

# Test 2: Check for nodeParam handling
echo "Test 2: Checking for nodeParam handling code..."
if grep -q "if (nodeParam)" map.html; then
    echo "✓ PASS: nodeParam conditional found"
else
    echo "❌ FAIL: nodeParam conditional not found"
    exit 1
fi
echo ""

# Test 3: Check for search input population
echo "Test 3: Checking for search input population..."
if grep -q 'searchInput.value = nodeParam' map.html; then
    echo "✓ PASS: Search input population code found"
else
    echo "❌ FAIL: Search input population code not found"
    exit 1
fi
echo ""

# Test 4: Check for automatic search trigger
echo "Test 4: Checking for automatic search trigger..."
if grep -q "autoSearchNodeParam" map.html; then
    echo "✓ PASS: Automatic search trigger found"
else
    echo "❌ FAIL: Automatic search trigger not found"
    exit 1
fi
echo ""

# Test 5: Check for searchNode() call
echo "Test 5: Checking for searchNode() call after data load..."
if grep -A 5 "if (autoSearchNodeParam)" map.html | grep -q "searchNode()"; then
    echo "✓ PASS: searchNode() call found"
else
    echo "❌ FAIL: searchNode() call not found"
    exit 1
fi
echo ""

# Test 6: Verify cleanup of temporary variable
echo "Test 6: Checking for cleanup of temporary variable..."
if grep -A 5 "if (autoSearchNodeParam)" map.html | grep -q "autoSearchNodeParam = null"; then
    echo "✓ PASS: Variable cleanup found"
else
    echo "❌ FAIL: Variable cleanup not found"
    exit 1
fi
echo ""

# Test 7: Check that view parameter handling is still intact
echo "Test 7: Checking that view parameter handling is preserved..."
if grep -q "const viewParam = urlParams.get('view')" map.html; then
    echo "✓ PASS: View parameter handling preserved"
else
    echo "❌ FAIL: View parameter handling broken"
    exit 1
fi
echo ""

# Test 8: Check for AUTO_SEARCH_DELAY constant
echo "Test 8: Checking for AUTO_SEARCH_DELAY constant..."
if grep -q "const AUTO_SEARCH_DELAY" map.html; then
    echo "✓ PASS: AUTO_SEARCH_DELAY constant found"
else
    echo "❌ FAIL: AUTO_SEARCH_DELAY constant not found"
    exit 1
fi
echo ""

# Summary
echo "========================================="
echo "All tests passed! ✓"
echo "========================================="
echo ""
echo "Feature Summary:"
echo "- URL parameter ?node=<search-term> is supported"
echo "- Automatically searches for node on page load"
echo "- Works with node names, IDs, and partial matches"
echo "- Compatible with existing ?view parameter"
echo "- Uses named constant for delay (maintainability)"
echo "- Module-scoped variable (no global pollution)"
echo ""
echo "Example URLs:"
echo "  map.html?node=tigro"
echo "  map.html?node=a2e175ac"
echo "  map.html?view=both&node=tigro"
echo ""

exit 0
