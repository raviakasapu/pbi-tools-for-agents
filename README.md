# PBI Compiler Service

A small, standalone FastAPI service that accepts a ZIP containing a Power BI project folder (with a `pbit/` subfolder) and compiles it into a `.pbit` using `pbi-tools`.

Supports two input modes:
- Upload a ZIP file directly.
- Provide a URL to a ZIP file to fetch and compile.


Returns a ZIP response containing:
- The compiled `.pbit` file
- `compile-output.txt` (captured console output)
- `extracted.zip` (optional, the working folder used during compilation)

## Requirements

- The `pbi-tools` Linux x86_64 binary must be available in the container or host PATH.
  - Expected files:
    - `pbi-tools.core` (executable)
    - `libgit2-*.so` (shipped alongside the binary)
  - This service expects them under `/pbi-tools` at runtime; the Dockerfile adds that path to `PATH` and `LD_LIBRARY_PATH`.
  - By default, these binaries are NOT committed to this repo; you must supply them by one of the methods below:
    - Copy them into `pbi-compiler-service/assets/pbi-tools/` before building
    - Provide a zipped bundle via Docker build arg `PBI_TOOLS_URL` (the Dockerfile downloads and unpacks to `/pbi-tools`)
    - Ensure `pbi-tools.core` is present in the base image PATH

## Local Run

1. (Optional) Place `assets/pbi-tools/` in this repo with `pbi-tools.core` and shared libs.
2. Create a virtualenv and install deps:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

3. Run the API:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

4. Test with cURL (file upload):

```bash
curl -X POST http://localhost:8000/compile \
  -F "file=@/path/to/your.zip" \
  -F "name=my_report" \
  -o result.zip
```

Or by URL:

```bash
curl -X POST http://localhost:8000/compile \
  -F "url=https://example.com/your.zip" \
  -F "name=my_report" \
  -o result.zip
```

## Docker

Build and run locally:

```bash
docker build -t pbi-compiler-service .
docker run --rm -p 8000:8000 pbi-compiler-service
```

## Railway Deployment

- Add environment variables as needed (optional):
  - `PBI_TOOLS_PATH=/pbi-tools` (default is added in Dockerfile)
  - `PBI_TOOLS_EXECUTABLE=pbi-tools.core`
  - `WORK_TIMEOUT_SECONDS=120` (compile timeout)
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Ensure the `pbi-tools` assets are included in the image:
  - EITHER commit `pbi-compiler-service/assets/pbi-tools/` (contains `pbi-tools.core` + libs)
  - OR set Docker build arg `PBI_TOOLS_URL` to a zip of the pbi-tools folder
  - OR ensure your base image already provides `pbi-tools.core` and libs on PATH

### GitHub Actions Deploy

This repo includes a workflow: `.github/workflows/pbi-compiler-railway.yml`.

Configure the following GitHub Secrets in your repository settings:

- `RAILWAY_TOKEN` (required): Your Railway account token.
- `RAILWAY_PROJECT_ID` (recommended): Target project ID.
- `RAILWAY_SERVICE_ID` or `RAILWAY_SERVICE_NAME` (recommended): Target service.
- `RAILWAY_ENVIRONMENT_ID` or `RAILWAY_ENVIRONMENT_NAME` (optional).

The workflow triggers on pushes to `main` for changes under `pbi-compiler-service/**` or can be run manually via Workflow Dispatch. It deploys the subdirectory using the Railway CLI.

Supplying pbi-tools in CI/CD:
- The workflow attempts to copy `Bi-Migrator-API/assets/pbi-tools` into `pbi-compiler-service/assets/pbi-tools` if present in this monorepo.
- Alternatively, configure your Railway Docker build to use `PBI_TOOLS_URL` to fetch a zipped bundle of the pbi-tools folder.

## ZIP Format Expected

- The root of the ZIP should contain a `pbit/` directory with contents compatible with `pbi-tools compile -folder <pbit_dir>`.
- If the ZIP root does not have `pbit/`, the service tries to find the first subdirectory that does.

## Notes

- The service returns HTTP 400 for invalid inputs and HTTP 500 for compilation failures.
- Increase `WORK_TIMEOUT_SECONDS` if compiling larger projects.
