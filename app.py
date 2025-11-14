import io
import os
import zipfile
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, UploadFile, Form, HTTPException, File
from fastapi.responses import StreamingResponse, JSONResponse

from helper import compile_pbi_from_zip


app = FastAPI(title="PBI Compiler Service", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


def _make_result_zip(pbit: Optional[io.BytesIO], extracted: Optional[io.BytesIO], logs: Optional[str], name: str) -> io.BytesIO:
    out = io.BytesIO()
    with zipfile.ZipFile(out, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        if pbit:
            pbit.seek(0)
            # Prefer provided name, then fall back to the buffer's name
            pbit_base = name if name else (getattr(pbit, 'name', None) or 'result')
            zf.writestr(f"compiled/{pbit_base}.pbit", pbit.read())
        if extracted:
            extracted.seek(0)
            zf.writestr("extracted.zip", extracted.read())
        if logs:
            zf.writestr("compile-output.txt", logs)
    out.seek(0)
    out.name = f"{name or 'result'}.zip"
    return out


@app.post("/compile")
def compile_endpoint(
    file: Optional[UploadFile] = File(default=None),
    url: Optional[str] = Form(default=None),
    name: Optional[str] = Form(default=None),
    return_extracted: bool = Form(default=True),
):
    if not file and not url:
        raise HTTPException(status_code=400, detail="Provide either a file upload or a url.")

    # Load ZIP into memory
    data = io.BytesIO()
    src_name = "result"
    try:
        if file:
            file.file.seek(0)
            data.write(file.file.read())
            src_name = Path(getattr(file, 'filename', 'result')).stem
        else:
            resp = requests.get(url, timeout=60)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download ZIP from URL: HTTP {resp.status_code}")
            data.write(resp.content)
            src_name = Path(url).stem or "result"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read ZIP: {e}")

    data.seek(0)
    # Validate it's a zip
    try:
        zipfile.ZipFile(data)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Uploaded content is not a valid ZIP.")

    # Compile
    timeout = int(os.getenv('WORK_TIMEOUT_SECONDS', '120'))
    data.seek(0)
    pbit, extracted, logs = compile_pbi_from_zip(data, timeout_seconds=timeout)

    if not pbit and not extracted:
        raise HTTPException(status_code=500, detail=f"Compilation failed. Logs: {logs}")

    # Build response ZIP
    res_name = name or src_name or 'result'
    res_zip = _make_result_zip(pbit, extracted if return_extracted else None, logs, res_name)

    headers = {
        'Content-Disposition': f'attachment; filename="{res_zip.name}"'
    }
    return StreamingResponse(res_zip, media_type='application/zip', headers=headers)
