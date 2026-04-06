"""Format conversion via LibreOffice (async) and catdoc fallback for .doc."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

LO_TIMEOUT = 120.0
MIN_INPUT_BYTES = 1000


def _soffice_bin() -> str:
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    return "soffice"


def _ext(name: str) -> str:
    return Path(name).suffix.lower()


async def _run_soffice_convert(input_path: Path, outdir: Path, target_ext: str) -> Path:
    bin_path = _soffice_bin()
    proc = await asyncio.create_subprocess_exec(
        bin_path,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        "--convert-to",
        target_ext,
        "--outdir",
        str(outdir),
        str(input_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=LO_TIMEOUT)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError("LibreOffice conversion timed out") from None
    if proc.returncode != 0:
        raise RuntimeError("LibreOffice conversion failed")

    base = input_path.stem
    # LibreOffice uses output name stem + target ext
    out_file = outdir / f"{base}.{target_ext}"
    if out_file.is_file():
        return out_file
    # Sometimes different casing
    for p in outdir.iterdir():
        if p.suffix.lower() == f".{target_ext}" and p.stem.lower() == base.lower():
            return p
    raise FileNotFoundError("Converted output not found after LibreOffice")


async def _catdoc_to_text(doc_path: Path) -> bytes:
    catdoc = shutil.which("catdoc")
    if not catdoc:
        raise RuntimeError("catdoc not installed and LibreOffice failed")
    proc = await asyncio.create_subprocess_exec(
        catdoc,
        "-w",
        str(doc_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"catdoc failed: {err.decode(errors='replace')}")
    return out


async def convert_to_docx(content: bytes, filename: str) -> tuple[bytes, str]:
    """
    Normalize to docx when needed (.doc / .odt / .rtf).
    Passes through .docx and .pdf unchanged.
    """
    ext = _ext(filename)
    if ext in (".docx", ".pdf"):
        if len(content) < MIN_INPUT_BYTES:
            logger.warning("Input file very small (%s bytes)", len(content))
        return content, filename

    if ext in (".doc", ".odt", ".rtf"):
        if len(content) < MIN_INPUT_BYTES:
            logger.warning("Input file very small (%s bytes)", len(content))
        with tempfile.TemporaryDirectory(prefix="orleu_conv_") as tmp:
            tdir = Path(tmp)
            src = tdir / Path(filename).name
            src.write_bytes(content)
            try:
                out = await _run_soffice_convert(src, tdir, "docx")
                return out.read_bytes(), out.name
            except (RuntimeError, FileNotFoundError, TimeoutError) as e:
                logger.warning("LibreOffice doc→docx failed: %s", e)
                if ext == ".doc":
                    txt = await _catdoc_to_text(src)
                    return txt, Path(filename).stem + ".txt"
                raise

    # Unknown extension — return as-is (extractor may still handle e.g. .txt)
    return content, filename


async def convert_docx_to_pdf(content: bytes) -> bytes | None:
    """docx → pdf via LibreOffice."""
    with tempfile.TemporaryDirectory(prefix="orleu_pdf_") as tmp:
        tdir = Path(tmp)
        src = tdir / "input.docx"
        src.write_bytes(content)
        try:
            out = await _run_soffice_convert(src, tdir, "pdf")
            return out.read_bytes()
        except (RuntimeError, FileNotFoundError, TimeoutError) as e:
            logger.warning("docx→pdf failed: %s", e)
            return None
