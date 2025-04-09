#!/bin/bash

# Hardcoded path to the TOML file
TOML_FILE="config/models.toml"

rg '^\[.*\]' --no-line-number --no-filename "$TOML_FILE" \
  | sed -E 's/^\["?([^"]+)"?\]$/\1/' \
  | shuf \
  | xargs

