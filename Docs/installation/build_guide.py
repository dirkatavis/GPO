from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


@dataclass
class Block:
    kind: str
    data: Any


def load_reportlab() -> dict[str, Any]:
    """Load reportlab modules lazily so missing dependency errors are user-friendly."""
    try:
        colors = importlib.import_module("reportlab.lib.colors")
        pagesizes = importlib.import_module("reportlab.lib.pagesizes")
        styles_mod = importlib.import_module("reportlab.lib.styles")
        units = importlib.import_module("reportlab.lib.units")
        platypus = importlib.import_module("reportlab.platypus")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'reportlab'. Install it with: py -3 -m pip install reportlab"
        ) from exc

    return {
        "colors": colors,
        "LETTER": pagesizes.LETTER,
        "ParagraphStyle": styles_mod.ParagraphStyle,
        "getSampleStyleSheet": styles_mod.getSampleStyleSheet,
        "inch": units.inch,
        "Preformatted": platypus.Preformatted,
        "Paragraph": platypus.Paragraph,
        "SimpleDocTemplate": platypus.SimpleDocTemplate,
        "Spacer": platypus.Spacer,
        "Table": platypus.Table,
        "TableStyle": platypus.TableStyle,
    }


def build_styles(rl: dict[str, Any]) -> Any:
    colors = rl["colors"]
    ParagraphStyle = rl["ParagraphStyle"]
    getSampleStyleSheet = rl["getSampleStyleSheet"]
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="WizardTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#123A5A"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading2Custom",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#123A5A"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Heading3Custom",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ListItem",
            parent=styles["Body"],
            leftIndent=16,
            bulletIndent=6,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Quote",
            parent=styles["Body"],
            leftIndent=14,
            textColor=colors.HexColor("#374151"),
            italic=True,
            spaceBefore=2,
            spaceAfter=4,
        )
    )

    return styles


def inline_md_to_html(text: str) -> str:
    safe = escape(text)

    safe = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", safe)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", safe)

    return safe


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]


def parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown(text: str) -> list[Block]:
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip("\n")

        if not line.strip():
            i += 1
            continue

        if line.strip().startswith("```"):
            fence = line.strip()[:3]
            lang = line.strip()[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(fence):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            blocks.append(Block("code", {"lang": lang, "text": "\n".join(code_lines)}))
            continue

        if is_table_line(line):
            table_lines = [line]
            i += 1
            while i < len(lines) and is_table_line(lines[i]):
                table_lines.append(lines[i])
                i += 1
            rows = [parse_table_row(tl) for tl in table_lines]
            filtered: list[list[str]] = []
            for idx, row in enumerate(rows):
                if idx == 1 and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in row):
                    continue
                filtered.append(row)
            if filtered:
                blocks.append(Block("table", filtered))
            continue

        if line.lstrip().startswith(">"):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                content = re.sub(r"^\s*>\s?", "", lines[i])
                quote_lines.append(content)
                i += 1

            joined = "\n".join(quote_lines).strip()
            tag_match = re.match(
                r"^\s*(?:\[(REASSURANCE|TIP|SUCCESS|ERROR)\]|(REASSURANCE|TIP|SUCCESS|ERROR)\s*:)\s*(.*)$",
                joined,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if tag_match:
                tag = (tag_match.group(1) or tag_match.group(2) or "").upper()
                body = (tag_match.group(3) or "").strip()
                blocks.append(Block("callout", {"tag": tag, "text": body}))
            else:
                blocks.append(Block("blockquote", joined))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            blocks.append(Block("heading", {"level": level, "text": title}))
            i += 1
            continue

        if re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+", line):
            items: list[dict[str, Any]] = []
            while i < len(lines):
                m = re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+(.+)$", lines[i])
                if not m:
                    break
                items.append({"checked": m.group(1).lower() == "x", "text": m.group(2).strip()})
                i += 1
            blocks.append(Block("checklist", items))
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            items: list[str] = []
            while i < len(lines):
                m = re.match(r"^\s*\d+\.\s+(.+)$", lines[i])
                if not m:
                    break
                items.append(m.group(1).strip())
                i += 1
            blocks.append(Block("olist", items))
            continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines):
                m = re.match(r"^\s*[-*]\s+(.+)$", lines[i])
                if not m:
                    break
                items.append(m.group(1).strip())
                i += 1
            blocks.append(Block("ulist", items))
            continue

        para_lines = [line.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                i += 1
                break
            if (
                nxt.strip().startswith("```")
                or is_table_line(nxt)
                or nxt.lstrip().startswith(">")
                or re.match(r"^(#{1,6})\s+", nxt)
                or re.match(r"^\s*\d+\.\s+", nxt)
                or re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+", nxt)
                or re.match(r"^\s*[-*]\s+", nxt)
            ):
                break
            para_lines.append(nxt.strip())
            i += 1
        blocks.append(Block("paragraph", " ".join(para_lines)))

    return blocks


def callout_colors(tag: str, rl: dict[str, Any]) -> tuple[Any, Any]:
    colors = rl["colors"]
    mapping = {
        "REASSURANCE": (colors.HexColor("#D1FAE5"), colors.HexColor("#065F46")),
        "TIP": (colors.HexColor("#FEF3C7"), colors.HexColor("#92400E")),
        "SUCCESS": (colors.HexColor("#D1FAE5"), colors.HexColor("#065F46")),
        "ERROR": (colors.HexColor("#FEE2E2"), colors.HexColor("#991B1B")),
    }
    return mapping.get(tag, (colors.HexColor("#E5E7EB"), colors.HexColor("#374151")))


def add_branded_header(story: list[Any], styles: Any, title: str, rl: dict[str, Any]) -> None:
    colors = rl["colors"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    Paragraph = rl["Paragraph"]
    Spacer = rl["Spacer"]
    inch = rl["inch"]

    ribbon = Table(
        [["GLASS ORCHESTRATOR", datetime.now().strftime("Generated %Y-%m-%d %H:%M")]],
        colWidths=[4.8 * inch, 2.2 * inch],
    )
    ribbon.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#123A5A")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(ribbon)
    story.append(Spacer(1, 10))
    story.append(Paragraph(inline_md_to_html(title), styles["WizardTitle"]))
    story.append(Paragraph("Configuration Wizard", styles["Meta"]))


def render_pdf(md_path: Path, pdf_path: Path, rl: dict[str, Any]) -> None:
    colors = rl["colors"]
    ParagraphStyle = rl["ParagraphStyle"]
    Preformatted = rl["Preformatted"]
    Paragraph = rl["Paragraph"]
    SimpleDocTemplate = rl["SimpleDocTemplate"]
    Spacer = rl["Spacer"]
    Table = rl["Table"]
    TableStyle = rl["TableStyle"]
    LETTER = rl["LETTER"]
    inch = rl["inch"]

    print("[1/4] Loading Markdown...")
    text = md_path.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    styles = build_styles(rl)

    print("[2/4] Building document layout...")
    story: list[Any] = []

    title = "SETUP GUIDE"
    if blocks and blocks[0].kind == "heading" and blocks[0].data.get("level") == 1:
        title = blocks[0].data.get("text", title)
        blocks = blocks[1:]

    add_branded_header(story, styles, title, rl)

    step_counter = 0

    for block in blocks:
        if block.kind == "heading":
            level = int(block.data["level"])
            text_value = str(block.data["text"])

            if level == 2 and re.match(r"^Step\b", text_value, flags=re.IGNORECASE):
                step_counter += 1
                title_text = re.sub(r"^Step\s*\d*\s*:?\s*", "", text_value, flags=re.IGNORECASE).strip()
                if not title_text:
                    title_text = text_value
                step_table = Table(
                    [[f"STEP {step_counter}", title_text]],
                    colWidths=[1.1 * inch, 5.9 * inch],
                )
                step_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#123A5A")),
                            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E8EEF3")),
                            ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                            ("TEXTCOLOR", (1, 0), (1, 0), colors.HexColor("#123A5A")),
                            ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                            ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 11),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B7C7D7")),
                        ]
                    )
                )
                story.append(Spacer(1, 8))
                story.append(step_table)
                story.append(Spacer(1, 6))
            elif level == 2:
                story.append(Paragraph(inline_md_to_html(text_value), styles["Heading2Custom"]))
            elif level == 3:
                story.append(Paragraph(inline_md_to_html(text_value), styles["Heading3Custom"]))
            else:
                story.append(Paragraph(inline_md_to_html(text_value), styles["Body"]))
            continue

        if block.kind == "paragraph":
            story.append(Paragraph(inline_md_to_html(str(block.data)), styles["Body"]))
            continue

        if block.kind == "olist":
            for idx, item in enumerate(block.data, start=1):
                story.append(Paragraph(f"{idx}. {inline_md_to_html(item)}", styles["ListItem"]))
            story.append(Spacer(1, 2))
            continue

        if block.kind == "ulist":
            for item in block.data:
                story.append(Paragraph(f"- {inline_md_to_html(item)}", styles["ListItem"]))
            story.append(Spacer(1, 2))
            continue

        if block.kind == "checklist":
            for item in block.data:
                marker = "[x]" if item["checked"] else "[ ]"
                story.append(Paragraph(f"{marker} {inline_md_to_html(item['text'])}", styles["ListItem"]))
            story.append(Spacer(1, 2))
            continue

        if block.kind == "code":
            lang = block.data.get("lang", "")
            if lang:
                story.append(Paragraph(f"<b>{escape(lang)}</b>", styles["Meta"]))
            code_block = Preformatted(
                block.data.get("text", ""),
                ParagraphStyle(
                    name="Code",
                    fontName="Courier",
                    fontSize=8.6,
                    leading=11,
                    leftIndent=8,
                    rightIndent=8,
                ),
            )
            frame = Table([[code_block]], colWidths=[7.0 * inch])
            frame.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(frame)
            story.append(Spacer(1, 6))
            continue

        if block.kind == "table":
            rows: list[list[str]] = block.data
            if not rows:
                continue
            normalized = []
            width = max(len(r) for r in rows)
            for row in rows:
                padded = row + [""] * (width - len(row))
                normalized.append([Paragraph(inline_md_to_html(c), styles["Body"]) for c in padded])

            table = Table(normalized, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#123A5A")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 8))
            continue

        if block.kind == "blockquote":
            story.append(Paragraph(inline_md_to_html(str(block.data)), styles["Quote"]))
            continue

        if block.kind == "callout":
            tag = str(block.data.get("tag", "")).upper()
            content = str(block.data.get("text", ""))
            bg, fg = callout_colors(tag, rl)
            callout_text = Paragraph(
                f"<b>{escape(tag)}</b><br/>{inline_md_to_html(content)}",
                ParagraphStyle(
                    name=f"Callout_{tag}",
                    parent=styles["Body"],
                    textColor=fg,
                    fontSize=10,
                    leading=13,
                ),
            )
            box = Table([[callout_text]], colWidths=[7.0 * inch])
            box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), bg),
                        ("BOX", (0, 0), (-1, -1), 1, fg),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(box)
            story.append(Spacer(1, 6))
            continue

    print("[3/4] Rendering PDF...")
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="SETUP GUIDE",
        author="GlassOrchestrator",
    )
    doc.build(story)
    print(f"[4/4] Done. PDF created at: {pdf_path}")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    md_path = script_dir / "SETUP_GUIDE.md"
    pdf_path = script_dir / "SETUP_GUIDE.pdf"

    print("=== SETUP GUIDE PDF BUILDER ===")
    print(f"Working directory: {script_dir}")

    if not md_path.exists():
        print(f"ERROR: Could not find '{md_path.name}' in {script_dir}")
        return 1

    try:
        rl = load_reportlab()
        render_pdf(md_path, pdf_path, rl)
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"ERROR: Failed to build PDF: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - final fallback for unknown runtime errors.
        print(f"ERROR: Unexpected failure while building PDF: {exc}")
        return 1


if __name__ == "__main__":
    code = main()
    try:
        input("Press Enter to close...")
    except EOFError:
        pass
    raise SystemExit(code)
