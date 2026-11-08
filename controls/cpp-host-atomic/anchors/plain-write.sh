#!/bin/bash
# Constructed blind alternative: ignores defer and follows target symlinks.
mkdir -p "$(dirname "$2")"
cat > "$2"
