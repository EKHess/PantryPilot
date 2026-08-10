"""Small, dependency-free PDF generator for printable grocery checklists."""

from datetime import date


def _pdf_text(value: str) -> str:
    """Convert text to WinAnsi-compatible, escaped PDF string content."""
    encoded = value.encode("cp1252", "replace").decode("cp1252")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(lines: list[tuple[str, int, bool]]) -> bytes:
    commands = ["BT"]
    y = 750
    for text, size, bold in lines:
        font = "F2" if bold else "F1"
        commands.append(f"/{font} {size} Tf 54 {y} Td ({_pdf_text(text)}) Tj")
        commands.append(f"-54 {-size - 8} Td")
        y -= size + 8
    commands.append("ET")
    return "\n".join(commands).encode("cp1252")


def grocery_list_pdf(lists: list[dict], title: str = "Grocery Lists") -> bytes:
    """Build a PDF with store headings and an empty checkbox for every item."""
    pages: list[list[tuple[str, int, bool]]] = []
    current = [(title, 20, True), (f"Generated {date.today():%B %d, %Y}", 10, False)]

    for grocery_list in lists:
        needed = 1 + len(grocery_list["items"])
        if len(current) + needed > 31:
            pages.append(current)
            current = [(title + " (continued)", 18, True)]
        current.append((grocery_list["name"], 15, True))
        for item in grocery_list["items"]:
            current.append((f"[ ]  {item['name']}    Qty {item['quantity']}", 11, False))
    pages.append(current)

    objects: list[bytes] = []
    page_ids = []
    # Object IDs: catalog, pages tree, two fonts, then page/content pairs.
    for index, lines in enumerate(pages):
        page_id = 5 + index * 2
        content_id = page_id + 1
        page_ids.append(page_id)
        stream = _page_stream(lines)
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode(),
                b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            ]
        )
    base_objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Kids "
            f"[{' '.join(f'{page} 0 R' for page in page_ids)}] "
            f"/Count {len(page_ids)} >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    objects = base_objects + objects

    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, obj in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{object_id} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(document)
