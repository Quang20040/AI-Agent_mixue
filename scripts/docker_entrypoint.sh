#!/bin/sh
# Container start-up for BeverageOps AI.
#
# PERSIST_DIR (e.g. /var/data on a Render disk) holds everything the shop writes at runtime:
# the SQLite database, shift reports, OCR edit log, LangGraph checkpoints, audit log,
# chat attachments and uploaded evidence photos. Without PERSIST_DIR the app writes
# inside /app/data, which is lost on every redeploy (fine for a demo, not for a shop).
set -eu

# Render (and most hosts) mount a fresh persistent disk owned by root. Start as root only to
# hand the disk to the unprivileged app user, then drop privileges for everything else.
if [ "$(id -u)" = "0" ]; then
  if [ -n "${PERSIST_DIR:-}" ]; then
    mkdir -p "$PERSIST_DIR"
    chown -R appuser:appgroup "$PERSIST_DIR"
  fi
  exec setpriv --reuid=appuser --regid=appgroup --init-groups sh "$0" "$@"
fi

if [ -n "${PERSIST_DIR:-}" ]; then
  mkdir -p "$PERSIST_DIR/agent_private" "$PERSIST_DIR/chat_attachments" "$PERSIST_DIR/shift_uploads"
  # Seed once from the image; never overwrite data the shop has already written.
  if [ -z "${DATABASE_URL:-}" ] && [ ! -f "$PERSIST_DIR/beverageops.db" ] && [ -f /opt/seed_data/beverageops.db ]; then
    cp /opt/seed_data/beverageops.db "$PERSIST_DIR/beverageops.db"
  fi
  if [ ! -f "$PERSIST_DIR/shift_reports.json" ] && [ -f /opt/seed_data/shift_reports.json ]; then
    cp /opt/seed_data/shift_reports.json "$PERSIST_DIR/shift_reports.json"
  fi
  export DATABASE_URL="${DATABASE_URL:-sqlite:///$PERSIST_DIR/beverageops.db}"
  export SHIFT_DATA_FILE="${SHIFT_DATA_FILE:-$PERSIST_DIR/shift_reports.json}"
  export OCR_EDITS_LOG_FILE="${OCR_EDITS_LOG_FILE:-$PERSIST_DIR/agent_private/ocr_user_edits.jsonl}"
  export AGENT_CHECKPOINT_PATH="${AGENT_CHECKPOINT_PATH:-$PERSIST_DIR/agent_private/checkpoints.sqlite}"
  export AGENT_AUDIT_PATH="${AGENT_AUDIT_PATH:-$PERSIST_DIR/agent_private/audit.jsonl}"
  export CHAT_ATTACHMENTS_DIR="${CHAT_ATTACHMENTS_DIR:-$PERSIST_DIR/chat_attachments}"
  export SHIFT_UPLOADS_DIR="${SHIFT_UPLOADS_DIR:-$PERSIST_DIR/shift_uploads}"
else
  mkdir -p /app/data
  if [ ! -f /app/data/beverageops.db ] && [ -f /opt/seed_data/beverageops.db ]; then
    cp /opt/seed_data/beverageops.db /app/data/beverageops.db
  fi
  if [ ! -f /app/data/shift_reports.json ] && [ -f /opt/seed_data/shift_reports.json ]; then
    cp /opt/seed_data/shift_reports.json /app/data/shift_reports.json
  fi
fi

# First boot on a server: create the owner account from OWNER_USERNAME / OWNER_INITIAL_PASSWORD.
python scripts/provision_admin.py --from-env

exec streamlit run src/dashboard/app.py --server.port="${PORT:-8501}" --server.address=0.0.0.0 --server.headless=true
