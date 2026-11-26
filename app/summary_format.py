"""Teksti i përmbledhjes: si shkruhet kodi brenda tij dhe si ndahet për shfaqje."""

import re


FENCE = "```"


def looks_like_code(value: str) -> bool:
    """Dallon kodin nga fjalitë shqipe, edhe kur modeli nuk e ka shënuar."""
    if "{" in value and "}" in value and (";" in value or "\n" in value):
        return True
    if "\n" in value and re.search(
        r"(?m)^\s*(def |class |import |from \S+ import |for .*:$|while .*:$|if .*:$|return )|;\s*$",
        value,
    ):
        return True
    return value.count(";") >= 2 and "=" in value and "(" in value


def _fenced(code: str) -> str:
    return f"{FENCE}\n{code}\n{FENCE}"


def format_example(item: str) -> list[str]:
    """Një shembull si rreshta të përmbledhjes: pika teksti dhe blloqe kodi."""
    parts = item.replace("\r\n", "\n").split(FENCE)
    lines = []
    for index, part in enumerate(parts):
        inside_fence = index % 2 == 1
        if inside_fence:
            # Rreshti i parë mund të jetë vetëm emri i gjuhës, p.sh. "java".
            part = re.sub(r"\A[ \t]*[\w+#-]*[ \t]*\n", "", part)
        part = part.strip("\n")
        if not part.strip():
            continue
        if inside_fence or looks_like_code(part):
            lines.append(_fenced(part.rstrip()))
        else:
            lines.append(f"- {one_line(part)}")
    return lines


def one_line(value: str) -> str:
    return " ".join(value.split())


def parse_summary(summary: str) -> list[tuple]:
    """Kthen blloqet: ("title" | "heading" | "paragraph" | "code", tekst) ose ("list", [pika])."""
    lines = summary.replace("\r\n", "\n").split("\n")
    blocks, paragraph, items = [], [], []

    def flush():
        if paragraph:
            blocks.append(("paragraph", "\n".join(paragraph)))
            paragraph.clear()
        plain = []
        for item in items:
            # Përmbledhjet e vjetra e kanë kodin si pikë të zakonshme.
            if looks_like_code(item):
                if plain:
                    blocks.append(("list", list(plain)))
                    plain.clear()
                blocks.append(("code", item))
            else:
                plain.append(item)
        if plain:
            blocks.append(("list", plain))
        items.clear()

    starts_section = True
    index = 0
    while index < len(lines):
        line = lines[index]
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if line.strip().startswith(FENCE):
            flush()
            code = []
            index += 1
            while index < len(lines) and lines[index].strip() != FENCE:
                code.append(lines[index])
                index += 1
            blocks.append(("code", "\n".join(code)))
        elif not line.strip():
            flush()
            starts_section = True
            index += 1
            continue
        elif starts_section and line.endswith(":") and not line.startswith("- ") and following:
            blocks.append(("heading", line[:-1]))
        elif not blocks and not paragraph and not items and not following:
            blocks.append(("title", line))
        elif line.startswith("- "):
            if paragraph:
                flush()
            items.append(line[2:])
        elif items:
            items[-1] += "\n" + line
        else:
            paragraph.append(line)
        starts_section = False
        index += 1

    flush()
    return blocks
