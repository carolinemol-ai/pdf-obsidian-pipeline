#!/bin/bash
# Watches ~/Downloads for new PDFs and triggers the processor

DOWNLOADS="$HOME/Downloads"
PROCESSOR="$HOME/.claude/scripts/pdf-processor.py"

echo "[$(date)] PDF watcher started — watching $DOWNLOADS"

/opt/homebrew/bin/fswatch "$DOWNLOADS" | while read filepath; do
    if [[ "$filepath" == *.pdf || "$filepath" == *.PDF ]]; then
        echo "[$(date)] New PDF detected: $filepath"
        /usr/local/bin/python3 "$PROCESSOR" "$filepath" &
    fi
done
