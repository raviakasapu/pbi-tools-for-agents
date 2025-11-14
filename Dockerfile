# Optional: Build pbi-tools as a .NET Global Tool
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS dotnet
RUN dotnet tool install -g pbi-tools || true

# Runtime for .NET tools
FROM mcr.microsoft.com/dotnet/runtime:8.0 AS dotnetruntime

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

# Add .NET runtime and the pbi-tools global tool (if present in builder)
COPY --from=dotnetruntime /usr/share/dotnet /usr/share/dotnet
COPY --from=dotnet /root/.dotnet/tools /root/.dotnet/tools

ENV PATH="/app/.venv/bin:/pbi-tools:/root/.dotnet/tools:/usr/share/dotnet:$PATH" \
    LD_LIBRARY_PATH="/pbi-tools:${LD_LIBRARY_PATH}" \
    PBI_TOOLS_PATH="/pbi-tools" \
    PBI_TOOLS_EXECUTABLE=""

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
