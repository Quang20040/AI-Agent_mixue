# ==============================================================================
# BeverageOps AI — Dockerfile (Multi-stage build, Non-root, Production Ready)
# Chi nhánh Mixue 39 Tôn Quang Phiệt
# ==============================================================================

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Minimal runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime dependencies for psycopg2 and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Copy installed packages from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Ho_Chi_Minh

# Copy application code and database seeds
COPY --chown=appuser:appgroup . /app
RUN mkdir -p /app/data /app/backups /opt/seed_data \
    && if [ -f /app/data/beverageops.db ]; then cp /app/data/beverageops.db /opt/seed_data/beverageops.db; fi \
    && if [ -f /app/data/shift_reports.json ]; then cp /app/data/shift_reports.json /opt/seed_data/shift_reports.json; fi \
    && chown -R appuser:appgroup /app /opt/seed_data

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD sh -c 'curl -f http://localhost:${PORT:-8501}/_stcore/health || exit 1'

CMD ["sh", "-c", "mkdir -p /app/data && if [ ! -f /app/data/beverageops.db ] && [ -f /opt/seed_data/beverageops.db ]; then cp /opt/seed_data/beverageops.db /app/data/beverageops.db; fi && if [ ! -f /app/data/shift_reports.json ] && [ -f /opt/seed_data/shift_reports.json ]; then cp /opt/seed_data/shift_reports.json /app/data/shift_reports.json; fi && exec streamlit run src/dashboard/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true"]
