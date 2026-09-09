#!/bin/bash
# Snapshot the SQLite database (warnings, role links, CTF challenges/scoreboard)
# to ~/backups, keeping the most recent 14 copies. Meant to run from cron.
set -euo pipefail

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$BOT_DIR/data/bot.sqlite3"
DEST_DIR="$HOME/backups"
KEEP=14

if [ ! -f "$SRC" ]; then
    echo "No database found at $SRC yet, skipping backup."
    exit 0
fi

mkdir -p "$DEST_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
dest="$DEST_DIR/bot-$timestamp.sqlite3"

# .backup performs a safe, consistent copy even while the bot has the DB open.
sqlite3 "$SRC" ".backup '$dest'"

# Keep only the most recent $KEEP backups.
ls -1t "$DEST_DIR"/bot-*.sqlite3 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "Backed up to $dest"
