#!/bin/bash
# Script to run unit tests for Little Dorrit Editor
#
# Usage: ./scripts/run_tests.sh [test_path]
# - test_path: Optional path to specific tests (default: tests/)
# 
# Examples:
#   ./scripts/run_tests.sh                # Run all tests
#   ./scripts/run_tests.sh tests/test_evaluate.py  # Run specific test file
#   ./scripts/run_tests.sh tests/test_evaluate.py::test_match_edits_exact_match  # Run specific test case

set -e

# Get command line arguments or use default
TEST_PATH=${1:-"tests/"}

# Check if we're in a uv environment by checking for UV_VIRTUALENV
if [ -z "${UV_VIRTUALENV}" ]; then
    # Not in a uv environment, so install dev dependencies first
    echo "Installing dev dependencies and running tests..."
    uv pip install -e ".[dev]"
    uv run pytest "${TEST_PATH}" -v
else
    # Already in a uv environment, use pytest directly
    echo "Running tests with pytest directly..."
    pytest "${TEST_PATH}" -v
fi

# If we get here, tests passed
echo "All tests passed successfully!"