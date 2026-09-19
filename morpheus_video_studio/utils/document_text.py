"""
Document text extraction helpers for quick-create inputs.
"""

import re
import shutil
import subprocess
import tempfile
import zipfile
from importlib.util import find_spec
from pathlib import Path
from xml.etree import ElementTree as ET


PDF_TEXT_TOOL = Path("/Users/mofacejojo/pdf-to-images-tool/extract-pdf-text")


def extract_text_from_document(path: str | Path, max_chars: int = 24000) -> str:
    """Extract readable text from common document formats."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".csv", ".json"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    elif suffix == ".pdf":
        text = _extract_pdf_text(file_path)
    elif suffix == ".docx":
        text = _extract_docx_text(file_path)
    elif suffix == ".pptx":
        text = _extract_pptx_text(file_path)
    elif suffix == ".xlsx":
        text = _extract_xlsx_text(file_path)
    elif suffix == ".ppt":
        text = _extract_ppt_text(file_path)
    elif suffix in {".doc", ".rtf", ".html", ".htm", ".odt"}:
        text = _extract_with_textutil(file_path)
    else:
        raise ValueError(f"暂不支持的文档格式：{suffix or file_path.name}")

    text = _normalize_text(text)
    if not text:
        raise RuntimeError(f"没有从文档中提取到可用文本：{file_path.name}")
    return text[:max_chars]


def _extract_pdf_text(path: Path) -> str:
    text = _extract_pdf_text_with_opendataloader(path)
    if text:
        return text
    if PDF_TEXT_TOOL.exists():
        result = subprocess.run(
            [str(PDF_TEXT_TOOL), str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout
    return _extract_with_textutil(path)


def _extract_pdf_text_with_opendataloader(path: Path) -> str:
    if find_spec("opendataloader_pdf") is None:
        return ""

    try:
        import opendataloader_pdf

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            opendataloader_pdf.convert(
                input_path=str(path),
                output_dir=str(out_dir),
                format="markdown",
                quiet=True,
            )
            candidates = sorted(out_dir.glob(f"{path.stem}*.md")) + sorted(
                out_dir.glob(f"{path.stem}*.markdown")
            )
            if not candidates:
                candidates = sorted(out_dir.glob("*.md")) + sorted(out_dir.glob("*.markdown"))
            for candidate in candidates:
                text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    return text
    except Exception:
        return ""
    return ""


def _extract_with_textutil(path: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        subprocess.run(
            ["textutil", "-convert", "txt", "-output", str(out_dir / "out.txt"), str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return (out_dir / "out.txt").read_text(encoding="utf-8", errors="ignore")


def _extract_ppt_text(path: Path) -> str:
    text = _extract_with_office_text(path)
    if text:
        return text
    return _extract_with_textutil(path)


def _extract_with_office_text(path: Path) -> str:
    converter = _find_office_converter()
    if not converter:
        return ""

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        subprocess.run(
            [
                converter,
                "--headless",
                "--convert-to",
                "txt",
                "--outdir",
                str(out_dir),
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        candidates = sorted(out_dir.glob(f"{path.stem}*.txt")) or sorted(out_dir.glob("*.txt"))
        for candidate in candidates:
            text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                return text
    return ""


def _find_office_converter() -> str:
    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return found

    mac_candidates = [
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/Applications/OpenOffice.app/Contents/MacOS/soffice",
    ]
    for candidate in mac_candidates:
        if Path(candidate).exists():
            return candidate
    return ""


def _extract_docx_text(path: Path) -> str:
    parts = []
    with zipfile.ZipFile(path) as archive:
        names = [
            name for name in archive.namelist()
            if name == "word/document.xml"
            or name.startswith("word/header")
            or name.startswith("word/footer")
        ]
        for name in names:
            parts.append(_xml_text(archive.read(name)))
    return "\n".join(parts)


def _extract_pptx_text(path: Path) -> str:
    parts = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            name for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for idx, name in enumerate(slide_names, start=1):
            text = _xml_text(archive.read(name))
            if text:
                parts.append(f"第{idx}页幻灯片：{text}")
    return "\n".join(parts)


def _extract_xlsx_text(path: Path) -> str:
    parts = []
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_strings = _xml_text_items(archive.read("xl/sharedStrings.xml"))

        sheet_names = sorted(
            name for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for idx, name in enumerate(sheet_names, start=1):
            values = _xml_text_items(archive.read(name))
            resolved = []
            for value in values:
                if value.isdigit() and shared_strings:
                    str_idx = int(value)
                    if 0 <= str_idx < len(shared_strings):
                        resolved.append(shared_strings[str_idx])
                        continue
                resolved.append(value)
            if resolved:
                parts.append(f"第{idx}个工作表：{' '.join(resolved)}")
    return "\n".join(parts)


def _xml_text(xml_bytes: bytes) -> str:
    return " ".join(_xml_text_items(xml_bytes))


def _xml_text_items(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    values = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            values.append(elem.text.strip())
    return values


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()
