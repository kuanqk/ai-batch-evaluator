"""Plain XML text extraction from docx (zip)."""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET


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
