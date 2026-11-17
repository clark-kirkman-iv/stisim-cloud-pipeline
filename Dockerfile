# ==========================================
# STAGE 1: Developer Base (Editable Engine + Tools)
# ==========================================
FROM python:3.14-slim AS developer

WORKDIR /app

# Create non-root user to match prod permissions and avoid host file ownership issues
RUN useradd -m appuser && chown -R appuser:appuser /app

# Install system compilation and version control tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone stisim framework, install in editable mode, and reset empty mount point
RUN git clone https://github.com/starsimhub/stisim /stisim \
    && pip install --no-cache-dir -e /stisim[dev] \
    && rm -rf /stisim \
    && mkdir /stisim \
    && chown -R appuser:appuser /stisim

# Switch to non-root user and standardize workspace
USER appuser
WORKDIR /app/workspace

# ==========================================
# STAGE 2: Production Engine (Clean & Minimal)
# ==========================================
FROM python:3.14-slim AS production

WORKDIR /app

# Create identical non-root user for cloud compliance
RUN useradd -m appuser && chown -R appuser:appuser /app

# Install standard stisim package from PyPI
RUN pip install --no-cache-dir stisim

# Switch to non-root user and standardize workspace
USER appuser
WORKDIR /app/workspace
COPY --chown=appuser:appuser run_stisim.py /app/workspace/

# ==========================================
# STAGE 3: Test Runner (Production + Pytest)
# ==========================================
FROM production AS test

RUN pip install --no-cache-dir --user pytest
ENV PATH="/home/appuser/.local/bin:${PATH}"