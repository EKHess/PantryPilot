"""Small, dependency-free PDF generator for printable grocery checklists."""

from datetime import date

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
BLACK = "0 0 0"


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
    """Wrap text using a conservative Helvetica character-width estimate."""
    max_chars = max(8, int(width / (size * 0.52)))
    words = value.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
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
    _text(commands, str(page_number), 563, 23, 8)


def _item_height(item, width, size):
    return max(24, len(_wrapped(f"{item['name']} (Qty: {item['quantity']})", width - 28, size)) * (size + 3) + 7)


def _draw_item(commands, item, x, y, width, size):
    lines = _wrapped(f"{item['name']} (Qty: {item['quantity']})", width - 28, size)
    _rect(commands, x, y - 10, 10, 10, 0.55)
    for index, line in enumerate(lines):
        _text(commands, line, x + 19, y - index * (size + 3), size)
    return y - max(24, len(lines) * (size + 3) + 7)


def _column_tokens(primary):
    tokens = []
    for group in primary.get("groups", []):
        tokens.append(("group", group["name"], len(group["items"])))
        tokens.extend(("item", item, group["name"]) for item in group["items"])
    return tokens


def _render_store_first(pages, lists, font_size, title):
    column_width, gap = 168, 20
    for batch_start in range(0, len(lists), 3):
        batch = lists[batch_start : batch_start + 3]
        positions = [0] * len(batch)
        tokens = [_column_tokens(primary) for primary in batch]
        first_batch_page = True
        while any(positions[index] < len(tokens[index]) for index in range(len(batch))):
            commands = []
            page_number = len(pages) + 1
            top = _page_header(commands, lists, "store", page_number, title)
            for column, primary in enumerate(batch):
                x = 32 + column * (column_width + gap)
                if column:
                    _line(commands, x - gap / 2, top + 5, x - gap / 2, 58, 0.35)
                heading = primary["name"] + (" (continued)" if not first_batch_page else "")
                _text(commands, heading.upper(), x, top, 13, True)
                _line(commands, x, top - 9, x + column_width, top - 9, 0.8)
                y = top - 29
                if (
                    positions[column] < len(tokens[column])
                    and tokens[column][positions[column]][0] == "item"
                ):
                    _text(
                        commands,
                        f"{tokens[column][positions[column]][2].upper()} (continued)",
                        x,
                        y,
                        9,
                        True,
                    )
                    y -= 22
                while positions[column] < len(tokens[column]):
                    token = tokens[column][positions[column]]
                    if token[0] == "group":
                        next_height = (
                            _item_height(tokens[column][positions[column] + 1][1], column_width, font_size)
                            if positions[column] + 1 < len(tokens[column])
                            else 0
                        )
                        required = 24 + next_height
                        if y - required < 58:
                            break
                        _text(commands, f"{token[1].upper()}  ({token[2]})", x, y, 10, True)
                        y -= 24
                    else:
                        needed = _item_height(token[1], column_width, font_size)
                        if y - needed < 58:
                            break
                        y = _draw_item(commands, token[1], x + 2, y, column_width - 2, font_size)
                    positions[column] += 1
            _footer(commands, page_number)
            pages.append(commands)
            first_batch_page = False


def _render_category_first(pages, lists, font_size, title):
    column_width, gap = 168, 20
    commands = []
    page_number = 1
    y = _page_header(commands, lists, "category", page_number, title)
    for primary in lists:
        all_groups = primary.get("groups", [])
        category_continues = False
        for batch_start in range(0, len(all_groups), 3):
            groups = all_groups[batch_start : batch_start + 3]
            group_positions = [0] * len(groups)
            while any(
                group_positions[index] < len(group["items"])
                for index, group in enumerate(groups)
            ):
                if y < 145:
                    _footer(commands, page_number)
                    pages.append(commands)
                    commands = []
                    page_number += 1
                    y = _page_header(commands, lists, "category", page_number, title)
                heading = primary["name"].upper() + (" (continued)" if category_continues else "")
                _text(commands, f"{heading}  ({primary['count']} items)", 32, y, 14, True)
                _line(commands, 32, y - 9, 580, y - 9, 0.9)
                section_top = y - 30
                bottoms = []
                for column, group in enumerate(groups):
                    x = 32 + column * (column_width + gap)
                    if column:
                        _line(commands, x - gap / 2, section_top + 7, x - gap / 2, 58, 0.35)
                    _text(commands, group["name"].upper(), x, section_top, 10, True)
                    column_y = section_top - 23
                    while group_positions[column] < len(group["items"]):
                        item = group["items"][group_positions[column]]
                        needed = _item_height(item, column_width, font_size)
                        if column_y - needed < 58:
                            break
                        column_y = _draw_item(commands, item, x + 2, column_y, column_width - 2, font_size)
                        group_positions[column] += 1
                    bottoms.append(column_y)
                y = min(bottoms, default=section_top) - 18
                category_continues = True
                if any(
                    group_positions[index] < len(group["items"])
                    for index, group in enumerate(groups)
                ):
                    _footer(commands, page_number)
                    pages.append(commands)
                    commands = []
                    page_number += 1
                    y = _page_header(commands, lists, "category", page_number, title)
            y -= 5
    _footer(commands, page_number)
    pages.append(commands)


def grocery_list_pdf(lists: list[dict], title: str = "Compiled Grocery List", font_size: int = 10) -> bytes:
    """Build a monochrome, multi-page grocery list grouped in the selected order."""
    sort_first = lists[0].get("sort_first", "store") if lists else "store"
    pages: list[list[str]] = []
    if sort_first == "category":
        _render_category_first(pages, lists, font_size, title)
    else:
        _render_store_first(pages, lists, font_size, title)
    if not pages:
        commands = []
        _page_header(commands, lists, sort_first, 1, title)
        _text(commands, "Your pantry is stocked. No items are currently needed.", 32, 590, 11)
        _footer(commands, 1)
        pages.append(commands)

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
