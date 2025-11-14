import io
import os
import platform
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple, List


def zip_path_contents(path: Path | os.PathLike | str) -> io.BytesIO:
    buffer = io.BytesIO()
    if isinstance(path, (str, os.PathLike)):
        path = Path(path)
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zipped:
        for file in path.rglob('*'):
            zipped.write(file, arcname=file.relative_to(path))
    buffer.seek(0)
    buffer.name = 'extracted.zip'
    return buffer


def _candidate_executables() -> List[str]:
    exe = os.getenv('PBI_TOOLS_EXECUTABLE')
    candidates: List[str] = []
    if exe:
        candidates.append(exe)
    # Try common names in order
    candidates.extend(['pbi-tools.core', 'pbi-tools'])
    # On Windows, add .exe variants
    if platform.system().lower() == 'windows':
        candidates = [c if c.endswith('.exe') else c + '.exe' for c in candidates]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            unique.append(c)
            seen.add(c)
    return unique


def compile_pbit_from_pbi_tools(directory: str, output_file_name: Optional[str] = None,
                                timeout_seconds: int = 60) -> Tuple[Optional[str], Optional[int]]:
    """Run pbi-tools compile on a folder, trying multiple executable names."""
    extra_args = []
    if output_file_name:
        extra_args = ['-outPath', output_file_name]

    env = os.environ.copy()
    pbi_tools_path = env.get('PBI_TOOLS_PATH')
    if pbi_tools_path:
        env['PATH'] = f"{pbi_tools_path}:{env.get('PATH', '')}"
        env['LD_LIBRARY_PATH'] = f"{pbi_tools_path}:{env.get('LD_LIBRARY_PATH', '')}"

    last_err = None
    for executable_name in _candidate_executables():
        try:
            process = subprocess.run([
                executable_name, 'compile', '-folder', directory,
                '-format', 'PBIT', '-overwrite', *extra_args
            ], capture_output=True, text=True, cwd=directory, timeout=timeout_seconds, env=env)
            return process.stdout + ("\n" + process.stderr if process.stderr else ''), process.returncode
        except subprocess.TimeoutExpired as e:
            return f"TIMEOUT: {e}", None
        except FileNotFoundError as e:
            last_err = e
            continue
    return f"EXEC NOT FOUND: {last_err}", None


def perform_pbi_compilation(root_directory: str | os.PathLike | Path, file_name: Optional[str] = None,
                            timeout_seconds: int = 60) -> Tuple[Optional[io.BytesIO], Optional[io.BytesIO], Optional[str]]:
    """
    Compile using pbi-tools: expects <root>/pbit/* structure.

    Returns: (pbit_file, extracted_zip, console_output)
    """
    buffer = io.BytesIO()
    if isinstance(root_directory, (str, os.PathLike)):
        root_directory = Path(root_directory)

    if not file_name:
        file_name = root_directory.name

    pbit_dir = Path(root_directory).resolve() / file_name / 'pbit'
    pbit_dir.mkdir(parents=True, exist_ok=True)
    output_file_name = file_name + ".pbit"
    console_output, _ = compile_pbit_from_pbi_tools(
        directory=str(pbit_dir), output_file_name=output_file_name, timeout_seconds=timeout_seconds
    )
    output_file_path = pbit_dir / output_file_name
    file_exists = Path(output_file_path).exists()
    extracted_files = zip_path_contents(root_directory)
    if not file_exists:
        return None, extracted_files, console_output
    with open(output_file_path, 'rb') as content:
        buffer.write(content.read())
    buffer.seek(0)
    buffer.name = output_file_name
    return buffer, extracted_files, console_output


def _has_pbixproj_structure(path: Path) -> bool:
    """Check if a directory contains Power BI project structure (Model and/or Report folders)."""
    return (path / 'Model').exists() or (path / 'Report').exists()


def compile_pbi_from_zip(zip_file: io.BytesIO, timeout_seconds: int = 60) -> Tuple[
    Optional[io.BytesIO], Optional[io.BytesIO], Optional[str]
]:
    """Compile a pbi-tools project from a ZIP and return (pbit, extracted, logs)."""
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as temp_dir:
        zf = zipfile.ZipFile(zip_file)
        zf.extractall(temp_dir)

        extracted_path = Path(temp_dir).resolve()
        pbit_dir = None
        root_dir = None
        
        # Strategy 1: Check if extracted_path itself has the pbixproj structure
        if _has_pbixproj_structure(extracted_path):
            pbit_dir = extracted_path
            root_dir = extracted_path
        # Strategy 2: Check if there's a 'pbit' folder that contains the structure
        elif (extracted_path / 'pbit').exists() and (extracted_path / 'pbit').is_dir():
            if _has_pbixproj_structure(extracted_path / 'pbit'):
                pbit_dir = extracted_path / 'pbit'
                root_dir = extracted_path
        # Strategy 3: Look in subdirectories
        else:
            directories = [item for item in extracted_path.iterdir() if item.is_dir()]
            for directory in directories:
                # Check if directory has pbixproj structure directly
                if _has_pbixproj_structure(directory):
                    pbit_dir = directory
                    root_dir = directory
                    break
                # Check if directory has a 'pbit' subfolder with the structure
                pbit_path = directory / 'pbit'
                if pbit_path.exists() and pbit_path.is_dir() and _has_pbixproj_structure(pbit_path):
                    pbit_dir = pbit_path
                    root_dir = directory
                    break
            
            # Fallback: use first directory
            if not pbit_dir and len(directories) >= 1:
                pbit_dir = directories[0]
                root_dir = directories[0]
        
        if not pbit_dir or not root_dir:
            return None, None, "No suitable Power BI project directory found in ZIP (missing 'Model' or 'Report' folders)."

        output_file_name = Path(pbit_dir).stem + ".pbit"
        console_output, _ = compile_pbit_from_pbi_tools(
            directory=str(pbit_dir), output_file_name=output_file_name, timeout_seconds=timeout_seconds
        )
        output_file_path = pbit_dir / output_file_name
        file_exists = Path(output_file_path).exists()
        extracted_files = zip_path_contents(extracted_path)
        if not file_exists:
            return None, extracted_files, console_output

        with open(output_file_path, 'rb') as content:
            buffer.write(content.read())
        buffer.seek(0)
        buffer.name = output_file_name
        return buffer, extracted_files, console_output
