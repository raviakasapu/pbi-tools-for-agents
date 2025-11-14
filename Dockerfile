# Optional: Build pbi-tools as a .NET Global Tool
FROM python:3.13-slim

WORKDIR /app

# Install minimal deps (curl useful for debugging)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip \
  && rm -rf /var/lib/apt/lists/*

# Copy app
COPY requirements.txt ./
RUN python -m venv .venv \
  && .venv/bin/pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

# If assets/pbi-tools present in the repo, copy into image and add to PATH
ARG PBI_TOOLS_URL=""
RUN if [ -n "$PBI_TOOLS_URL" ]; then \
      echo "Downloading pbi-tools bundle from $PBI_TOOLS_URL" && \
      mkdir -p /pbi-tools && \
      curl -sSL "$PBI_TOOLS_URL" -o /tmp/pbi-tools.zip && \
      unzip -q /tmp/pbi-tools.zip -d /pbi-tools && \
      rm -f /tmp/pbi-tools.zip; \
    fi \
  && if [ -d "assets/pbi-tools" ]; then mkdir -p /pbi-tools && cp -r assets/pbi-tools/* /pbi-tools/; fi \
  && if [ -f "/pbi-tools/pbi-tools.core" ]; then chmod +x /pbi-tools/pbi-tools.core; fi

ENV PATH="/app/.venv/bin:/pbi-tools:$PATH" \
    LD_LIBRARY_PATH="/pbi-tools:${LD_LIBRARY_PATH}" \
    PBI_TOOLS_PATH="/pbi-tools" \
    PBI_TOOLS_EXECUTABLE="pbi-tools.core"

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
