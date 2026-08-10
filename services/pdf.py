"""Small, dependency-free PDF generator for printable grocery checklists."""

from datetime import date


def _pdf_text(value: str) -> str:
    """Convert text to WinAnsi-compatible, escaped PDF string content."""
    encoded = value.encode("cp1252", "replace").decode("cp1252")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _rgb(color: str) -> tuple[float, float, float]:
    """Convert a CSS hexadecimal color to PDF RGB components."""
    try:
        return tuple(int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    except (AttributeError, TypeError, ValueError):
        return (0.0, 0.0, 0.0)


def _page_stream(lines: list[tuple[str, int, bool, str, bool]]) -> bytes:
    commands = ["BT"]
    y = 750
    for text, size, bold, color, checkbox in lines:
        font = "F2" if bold else "F1"
        red, green, blue = _rgb(color)
        text_x = 54
        if checkbox:
            # Draw a genuine vector checkbox rather than approximating one
            # with bracket characters. It stays crisp when printed or zoomed.
            commands.extend(
                [
                    "ET",
                    "0.000 0.000 0.000 RG",
                    f"54 {y - 2} 10 10 re S",
                    "BT",
                ]
            )
            text_x = 70
        commands.append(f"{red:.3f} {green:.3f} {blue:.3f} rg")
        # Tm sets an absolute text position. Using Td here would make each
        # position relative to the previous line and push list items off-page.
        commands.append(
            f"/{font} {size} Tf 1 0 0 1 {text_x} {y} Tm ({_pdf_text(text)}) Tj"
        )
        y -= size + 8
    commands.append("ET")
    return "\n".join(commands).encode("cp1252")


def grocery_list_pdf(
    lists: list[dict], title: str = "Grocery Lists", font_size: int = 12
) -> bytes:
    """Build a PDF with store headings and an empty checkbox for every item."""
    black = "#000000"
    page_line_limit = max(4, 620 // (font_size + 8))
    pages: list[list[tuple[str, int, bool, str, bool]]] = []
    current = [
        (title, font_size + 9, True, black, False),
        (
            f"Generated {date.today():%B %d, %Y}",
            max(8, font_size - 2),
            False,
            black,
            False,
        ),
    ]

    for grocery_list in lists:
        store_heading = (
            grocery_list["name"],
            font_size + 4,
            True,
            grocery_list.get("color", black),
            False,
        )
        if len(current) >= page_line_limit:
            pages.append(current)
            current = [(title + " (continued)", font_size + 7, True, black, False)]
        current.append(store_heading)
        for item in grocery_list["items"]:
            if len(current) >= page_line_limit:
                pages.append(current)
                current = [
                    (title + " (continued)", font_size + 7, True, black, False),
                    store_heading,
                ]
            current.append(
                (
                    f"{item['name']}    Qty {item['quantity']}",
                    font_size,
                    False,
                    black,
                    True,
                )
            )
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
