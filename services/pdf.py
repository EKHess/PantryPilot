"""Small, dependency-free PDF generator for printable grocery checklists."""

from datetime import date

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
BLACK = "0 0 0"
CONTENT_BOTTOM = 58

# Widths from Helvetica's built-in AFM data, expressed in thousandths of an em.
# Using the real font metrics here is important: character counts substantially
# underestimate strings containing wide letters and caused text to spill into
# the next column in larger print sizes.
_NARROW = set(" !'.,:;ijlI|[]()")
_WIDE = set("MW@%&#m")


def _pdf_text(value: str) -> str:
    encoded = value.encode("cp1252", "replace").decode("cp1252")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _text(commands, text, x, y, size=10, bold=False):
    font = "F2" if bold else "F1"
    commands.append(f"BT {BLACK} rg /{font} {size} Tf 1 0 0 1 {x} {y} Tm ({_pdf_text(text)}) Tj ET")


def _line(commands, x1, y1, x2, y2, width=0.7):
    commands.append(f"{BLACK} RG {width} w {x1} {y1} m {x2} {y2} l S")


def _rect(commands, x, y, width, height, stroke_width=0.7):
    commands.append(f"{BLACK} RG {stroke_width} w {x} {y} {width} {height} re S")


def _wrapped(value: str, width: float, size: int) -> list[str]:
    """Wrap text to a measured width, including unusually long single words."""
    def text_width(text):
        units = sum(278 if char in _NARROW else 833 if char in _WIDE else 556 for char in text)
        return units * size / 1000

    words = value.split()
    lines, current = [], ""
    for original_word in words:
        word = original_word
        while word and text_width(word) > width:
            split_at = max(index for index in range(1, len(word) + 1) if text_width(word[:index]) <= width)
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:split_at])
            word = word[split_at:]
        if not word:
            continue
        candidate = f"{current} {word}".strip()
        if current and text_width(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _stats(lists: list[dict], sort_first: str) -> tuple[int, int, int]:
    primary = {group["name"] for group in lists}
    secondary = {
        group["name"] for primary_group in lists for group in primary_group.get("groups", [])
    }
    stores = len(primary if sort_first == "store" else secondary)
    categories = len(primary if sort_first == "category" else secondary)
    total = sum(group.get("count", 0) for group in lists)
    return stores, categories, total


def _page_header(commands, lists, sort_first, page_number, title):
    if page_number == 1:
        # Simple black-and-white cart mark.
        commands.append(f"{BLACK} RG 1.4 w 32 715 46 46 re S")
        _line(commands, 42, 746, 47, 729, 1.3)
        _line(commands, 47, 729, 68, 729, 1.3)
        _line(commands, 48, 742, 70, 742, 1.3)
        _text(commands, "PantryPilot", 92, 744, 25, True)
        _text(commands, title, 92, 721, 15)
        _text(commands, f"{date.today():%B %d, %Y}", 92, 701, 10)
        stores, categories, total = _stats(lists, sort_first)
        _rect(commands, 447, 704, 128, 62)
        for index, (label, value) in enumerate(
            (("Stores", stores), ("Categories", categories), ("Total Items", total))
        ):
            y = 749 - index * 18
            _text(commands, label, 458, y, 9)
            _text(commands, str(value), 553, y, 9, True)
        _line(commands, 32, 680, 580, 680, 1)
        _rect(commands, 40, 641, 21, 21, 1)
        _line(commands, 45, 651, 49, 647, 1.2)
        _line(commands, 49, 647, 57, 656, 1.2)
        _text(commands, "Check off items as you shop.", 76, 651, 10)
        order = "store then category" if sort_first == "store" else "category then store"
        _text(commands, f"Organized by {order} to help you shop efficiently.", 76, 636, 9)
        return 610
    _text(commands, "PantryPilot", 32, 746, 16, True)
    _text(commands, f"{title} · Continued", 139, 746, 11)
    _text(commands, f"Page {page_number}", 538, 746, 9)
    _line(commands, 32, 732, 580, 732, 0.8)
    return 710


def _footer(commands, page_number):
    _line(commands, 32, 42, 580, 42, 0.8)
    _text(commands, "Shop smart. Save time. Waste less.", 205, 23, 9)
    _text(commands, f"Page {page_number} of {{total_pages}}", 505, 23, 8)


def _item_height(item, width, size):
    line_height = size + 3
    return max(24, len(_wrapped(f"{item['name']} (Qty: {item['quantity']})", width - 22, size)) * line_height + 7)


def _draw_wrapped_text(commands, value, x, y, width, size, bold=False):
    """Draw a heading without allowing it to intrude into an adjacent column."""
    lines = _wrapped(value, width, size)
    line_height = size + 2
    for index, line in enumerate(lines):
        _text(commands, line, x, y - index * line_height, size, bold)
    return y - len(lines) * line_height


def _draw_item(commands, item, x, y, width, size):
    lines = _wrapped(f"{item['name']} (Qty: {item['quantity']})", width - 22, size)
    # PDF text positions are baselines. Align the box with the glyph body of the
    # first line rather than putting its top on the baseline (which looked low).
    checkbox_y = y + size * 0.35 - 5
    _rect(commands, x, round(checkbox_y, 2), 10, 10, 0.55)
    for index, line in enumerate(lines):
        _text(commands, line, x + 16, y - index * (size + 3), size)
    return y - max(24, len(lines) * (size + 3) + 7)


def _column_tokens(primary):
    tokens = []
    for group in primary.get("groups", []):
        tokens.append(("group", group["name"], len(group["items"])))
        tokens.extend(("item", item, group["name"]) for item in group["items"])
    return tokens


def _primary_heading_label(primary, sort_first):
    label = primary["name"].upper()
    return f"{label}  ({primary['count']} items)" if sort_first == "category" else label


def _primary_heading_height(primary, width, continued, sort_first):
    lines = len(_wrapped(_primary_heading_label(primary, sort_first), width, 13))
    return lines * 15 + (11 if continued else 0) + 12


def _draw_primary_heading(commands, primary, x, y, width, continued, sort_first):
    """Draw a list heading, keeping its continuation marker deliberately small."""
    bottom = _draw_wrapped_text(
        commands, _primary_heading_label(primary, sort_first), x, y, width, 13, True
    )
    if continued:
        _text(commands, "(continued)", x, bottom + 1, 8)
        bottom -= 11
    _line(commands, x, bottom + 4, x + width, bottom + 4, 0.8)
    return bottom - 12


def _draw_group_continuation(commands, name, x, y, width):
    bottom = _draw_wrapped_text(commands, name.upper(), x, y, width, 9, True)
    _text(commands, "(continued)", x, bottom + 1, 7)
    return bottom - 13


def _render_newspaper(pages, lists, font_size, title, sort_first):
    """Flow every list down, then across three columns like a newspaper."""
    column_width, gap = 168, 20
    commands = []
    page_number = 1
    top = _page_header(commands, lists, sort_first, page_number, title)
    for divider in (210, 398):
        _line(commands, divider, top + 5, divider, CONTENT_BOTTOM, 0.35)
    column = 0
    y = top

    def column_x():
        return 32 + column * (column_width + gap)

    def advance_column():
        nonlocal commands, page_number, top, column, y
        column += 1
        if column == 3:
            _footer(commands, page_number)
            pages.append(commands)
            commands = []
            page_number += 1
            top = _page_header(commands, lists, sort_first, page_number, title)
            for divider in (210, 398):
                _line(commands, divider, top + 5, divider, CONTENT_BOTTOM, 0.35)
            column = 0
        y = top

    for primary in lists:
        tokens = _column_tokens(primary)
        if not tokens:
            continue
        position = 0
        continued = False
        while position < len(tokens):
            heading_height = _primary_heading_height(
                primary, column_width, continued, sort_first
            )
            token = tokens[position]
            if token[0] == "group":
                following = tokens[position + 1] if position + 1 < len(tokens) else None
                first_content = 24 + (
                    _item_height(following[1], column_width, font_size)
                    if following and following[0] == "item" else 0
                )
            else:
                first_content = 22 + _item_height(token[1], column_width, font_size)
            if y - heading_height - first_content < CONTENT_BOTTOM:
                advance_column()
                continued = position > 0

            x = column_x()
            y = _draw_primary_heading(
                commands, primary, x, y, column_width, continued, sort_first
            )
            if token[0] == "item":
                y = _draw_group_continuation(commands, token[2], x, y, column_width)

            while position < len(tokens):
                token = tokens[position]
                if token[0] == "group":
                    following = tokens[position + 1] if position + 1 < len(tokens) else None
                    required = 24 + (
                        _item_height(following[1], column_width, font_size)
                        if following and following[0] == "item" else 0
                    )
                    if y - required < CONTENT_BOTTOM:
                        break
                    _text(commands, f"{token[1].upper()}  ({token[2]})", x, y, 10, True)
                    y -= 24
                else:
                    needed = _item_height(token[1], column_width, font_size)
                    if y - needed < CONTENT_BOTTOM:
                        break
                    y = _draw_item(commands, token[1], x + 2, y, column_width - 2, font_size)
                position += 1

            if position < len(tokens):
                advance_column()
                continued = True
            else:
                y -= 10

    _footer(commands, page_number)
    pages.append(commands)


def grocery_list_pdf(lists: list[dict], title: str = "Compiled Grocery List", font_size: int = 10) -> bytes:
    """Build a monochrome, multi-page grocery list grouped in the selected order."""
    sort_first = lists[0].get("sort_first", "store") if lists else "store"
    pages: list[list[str]] = []
    if lists:
        _render_newspaper(pages, lists, font_size, title, sort_first)
    if not pages:
        commands = []
        _page_header(commands, lists, sort_first, 1, title)
        _text(commands, "Your pantry is stocked. No items are currently needed.", 32, 590, 11)
        _footer(commands, 1)
        pages.append(commands)

    # Page count is only known after the content has been flowed. Delaying this
    # substitution keeps pagination independent from document assembly.
    total_pages = len(pages)
    pages = [
        [command.replace("{total_pages}", str(total_pages)) for command in commands]
        for commands in pages
    ]

    objects: list[bytes] = []
    page_ids = []
    for index, commands in enumerate(pages):
        page_id = 5 + index * 2
        content_id = page_id + 1
        page_ids.append(page_id)
        stream = "\n".join(commands).encode("cp1252")
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>").encode(),
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        ])
    base_objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (f"<< /Type /Pages /Kids [{' '.join(f'{page} 0 R' for page in page_ids)}] /Count {len(page_ids)} >>").encode(),
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
    document.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(document)
