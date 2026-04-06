"""DOCX repair and plain XML text extraction."""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET


def fix_broken_docx(path: str) -> bool:
    """
    Removes NULL image references in .rels files inside a docx zip (in-place).
    Returns True if any file was modified.
    """
    try:
        with zipfile.ZipFile(path, "r") as zin:
            names = zin.namelist()
            rel_updates: dict[str, bytes] = {}
            for name in names:
                if not name.endswith(".rels"):
                    continue
                data = zin.read(name)
                if b"NULL" not in data:
                    continue
                new_data = data.replace(b'Target="../NULL"', b'Target=""')
                new_data = new_data.replace(b"../NULL", b"")
                if new_data != data:
                    rel_updates[name] = new_data
            if not rel_updates:
                return False
            out_buf = io.BytesIO()
            with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for name in names:
                    if name in rel_updates:
                        zout.writestr(name, rel_updates[name])
                    else:
                        zout.writestr(name, zin.read(name))
        with open(path, "wb") as f:
            f.write(out_buf.getvalue())
        return True
    except (zipfile.BadZipFile, OSError):
        return False


def _strip_xml_to_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    texts: list[str] = []

    def walk(elem: ET.Element) -> None:
        if elem.text and elem.text.strip():
            texts.append(elem.text.strip())
        for child in elem:
            walk(child)
            if child.tail and child.tail.strip():
                texts.append(child.tail.strip())

    walk(root)
    return "\n".join(texts)


def extract_text_from_docx_xml(content: bytes) -> str:
    """Extract visible text from docx (word/document.xml) via zip + XML."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            try:
                xml_bytes = zf.read("word/document.xml")
            except KeyError:
                return ""
    except zipfile.BadZipFile:
        return ""

    text = _strip_xml_to_text(xml_bytes)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
