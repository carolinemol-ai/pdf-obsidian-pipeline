#!/bin/bash
# Usage: manage-pdf-processor.sh {start|stop|restart|status|logs|test <pdf>}

LABEL="com.carolinework.pdf-processor"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/.claude/scripts/pdf-processor.log"

case "$1" in
    start)
        launchctl load "$PLIST"
        echo "PDF processor started."
        ;;
    stop)
        launchctl unload "$PLIST"
        echo "PDF processor stopped."
        ;;
    restart)
        launchctl unload "$PLIST" 2>/dev/null
        launchctl load "$PLIST"
        echo "PDF processor restarted."
        ;;
    status)
        if launchctl list | grep -q "$LABEL"; then
            echo "Running"
        else
            echo "Stopped"
        fi
        ;;
    logs)
        tail -50 "$LOG"
        ;;
    test)
        if [ -z "$2" ]; then
            echo "Usage: manage-pdf-processor.sh test <path-to-pdf>"
            exit 1
        fi
        echo "Testing with: $2"
        python3 "$HOME/.claude/scripts/pdf-processor.py" "$2"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|test <pdf>}"
        exit 1
        ;;
esac
