"""
pdf_text_engine.py
==================

A small, dependency-light engine for getting *clean, reliable* text out of PDFs.

It was extracted from a larger document-parsing project and stripped of all
domain-specific logic, so it works as a neutral starting point for any PDF task
(contracts, invoices, reports, forms, etc.).

What it gives you
-----------------
1. Position-aware text extraction that fixes the classic "L a d y  L a l a"
   problem where PDFs return text with characters spread out or words mashed
   together. This is the hard part, and it's done here.
2. A dual extraction strategy: pdfplumber's layout-aware extractor first, with
   automatic fallback to character-position reconstruction when the layout
   extractor produces garbage.
3. Table extraction (pdfplumber tables -> list of rows).
4. Generic, regex-based section splitting so you can chop a document into
   logical blocks (clauses, sections, line items) by a heading pattern you
   define.
5. Light text-cleanup helpers.
6. Stubbed field-extraction hooks with contract-flavored examples (dates,
   money, parties, defined terms) showing exactly where to plug in your own
   rules.

Only dependency: pdfplumber  ->  pip install pdfplumber

Quick start
-----------
    from pdf_text_engine import PDFTextEngine

    engine = PDFTextEngine("agreement.pdf")
    print(engine.full_text())                 # clean text, all pages
    for n, sec in engine.split_sections(r"^\s*\d+\.\s+[A-Z]"):
        print(n, sec[:80])                    # numbered clauses
    print(engine.find_dates())
    print(engine.find_money())
    for table in engine.extract_tables():
        ...

Author's note: the position-reconstruction logic (extract_text_with_positions)
is the genuinely valuable, hard-won piece. Everything else is convenience.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pdf_text_engine requires pdfplumber. Install it with:\n"
        "    pip install pdfplumber"
    ) from exc


# ---------------------------------------------------------------------------
# Core: position-aware character reconstruction
# ---------------------------------------------------------------------------
def extract_text_with_positions(
    page, x_tolerance: float = 3.0, y_tolerance: float = 3.0
) -> str:
    """Rebuild a page's text from individual character coordinates.

    Naive PDF extraction often returns text like "L a d y  L a l a" (every
    character spaced) or, conversely, words with no spaces at all. That happens
    because the PDF stores glyph positions, not words, and the default
    extractor guesses wrong. This function looks at each character's actual
    (x, y) box and rejoins them based on real spacing:

      * Characters whose vertical position differs by more than ``y_tolerance``
        start a new line.
      * On a line, if the gap between one character's right edge and the next
        character's left edge is smaller than ``x_tolerance``, they belong to
        the same word; otherwise a single space is inserted.

    Tuning tips:
      * If words are running together, *lower* x_tolerance.
      * If single words are being split apart, *raise* x_tolerance.
      * If lines merge or split incorrectly, adjust y_tolerance.

    Args:
        page: a pdfplumber page object (``page.chars`` is used).
        x_tolerance: horizontal gap (in PDF points) below which characters join.
        y_tolerance: vertical gap (in PDF points) that starts a new line.

    Returns:
        Reconstructed text for the page, lines separated by ``\\n``.
    """
    chars = page.chars
    if not chars:
        return ""

    # Sort top-to-bottom, then left-to-right. Rounding 'top' groups characters
    # that share a baseline despite sub-pixel differences.
    chars = sorted(chars, key=lambda c: (round(c["top"]), c["x0"]))

    lines: List[str] = []
    current_line: List[str] = []
    current_y: Optional[float] = None
    prev_char: Optional[dict] = None

    for char in chars:
        char_y = round(char["top"])

        # New line?
        if current_y is None or abs(char_y - current_y) > y_tolerance:
            if current_line:
                lines.append("".join(current_line))
            current_line = [char["text"]]
            current_y = char_y
            prev_char = char
            continue

        # Same line: decide whether to insert a space.
        if prev_char:
            distance = char["x0"] - prev_char["x1"]
            if distance < x_tolerance:
                current_line.append(char["text"])
            else:
                current_line.append(" ")
                current_line.append(char["text"])
        else:
            current_line.append(char["text"])

        prev_char = char

    if current_line:
        lines.append("".join(current_line))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Text cleanup helpers
# ---------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Normalize whitespace without destroying line structure.

    Collapses runs of spaces/tabs, trims trailing space on each line, and
    collapses 3+ blank lines down to a single blank line.
    """
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_garbage(text: str) -> bool:
    """Heuristic: did the layout extractor produce spaced-out junk?

    If a large fraction of "words" are single characters, the layout extractor
    probably failed and position reconstruction will do better. Used internally
    to decide whether to fall back.
    """
    tokens = text.split()
    if len(tokens) < 20:
        return False
    singles = sum(1 for t in tokens if len(t) == 1)
    return (singles / len(tokens)) > 0.4


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
@dataclass
class PageText:
    """Text for a single page plus which strategy produced it."""

    number: int
    text: str
    strategy: str  # "layout" or "positions"


class PDFTextEngine:
    """High-level, reusable PDF text engine.

    Open a PDF once, then pull clean text, tables, sections, or fields.

    Args:
        pdf_path: path to the PDF file.
        x_tolerance / y_tolerance: passed through to both extraction strategies.
        prefer: "auto" (default) tries layout first and falls back to position
            reconstruction when the layout output looks like garbage;
            "layout" forces the layout extractor; "positions" forces
            character reconstruction.
    """

    def __init__(
        self,
        pdf_path: str,
        x_tolerance: float = 3.0,
        y_tolerance: float = 3.0,
        prefer: str = "auto",
    ):
        self.pdf_path = pdf_path
        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance
        if prefer not in {"auto", "layout", "positions"}:
            raise ValueError("prefer must be 'auto', 'layout', or 'positions'")
        self.prefer = prefer
        self._pages: Optional[List[PageText]] = None

    # -- extraction ---------------------------------------------------------
    def pages(self) -> List[PageText]:
        """Extract (and cache) clean text for every page."""
        if self._pages is not None:
            return self._pages

        result: List[PageText] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text, strategy = self._extract_page(page)
                result.append(PageText(i, clean_text(text), strategy))
        self._pages = result
        return result

    def _extract_page(self, page) -> Tuple[str, str]:
        """Run the chosen strategy for one page, with auto-fallback."""
        if self.prefer == "positions":
            return (
                extract_text_with_positions(
                    page, self.x_tolerance, self.y_tolerance
                ),
                "positions",
            )

        layout = (
            page.extract_text(
                layout=True,
                x_tolerance=self.x_tolerance,
                y_tolerance=self.y_tolerance,
            )
            or ""
        )

        if self.prefer == "layout":
            return layout, "layout"

        # auto: fall back to position reconstruction if layout looks broken
        if not layout.strip() or looks_like_garbage(layout):
            positions = extract_text_with_positions(
                page, self.x_tolerance, self.y_tolerance
            )
            if positions.strip():
                return positions, "positions"
        return layout, "layout"

    def full_text(self, page_separator: str = "\n\n") -> str:
        """Clean text for the whole document."""
        return page_separator.join(p.text for p in self.pages())

    # -- tables -------------------------------------------------------------
    def extract_tables(self) -> List[List[List[Optional[str]]]]:
        """Extract every table in the document via pdfplumber.

        Returns a list of tables; each table is a list of rows; each row is a
        list of cell strings (cells may be None where pdfplumber found none).
        """
        tables: List[List[List[Optional[str]]]] = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    tables.append(table)
        return tables

    # -- section splitting --------------------------------------------------
    def split_sections(
        self, heading_pattern: str, flags: int = re.MULTILINE
    ) -> List[Tuple[int, str]]:
        """Split the document into sections at lines matching a heading regex.

        This is the generic version of "find every section header and slice the
        text between them." Give it a pattern that matches your document's
        section starts and it returns ``(index, section_text)`` pairs.

        Examples of heading patterns:
            r"^\\s*\\d+\\.\\s+[A-Z]"        numbered clauses: "1. TERM", "2. ..."
            r"^\\s*ARTICLE\\s+[IVX]+"       "ARTICLE IV"
            r"^\\s*SECTION\\s+\\d+"         "SECTION 12"
            r"^[A-Z][A-Z \\t]{4,}$"         ALL-CAPS heading lines

        Args:
            heading_pattern: regex marking the start of each section.
            flags: regex flags (defaults to MULTILINE so ^ matches line starts).

        Returns:
            List of (section_index, section_text). If no heading matches, the
            whole document is returned as a single section (index 0).
        """
        text = self.full_text()
        matches = list(re.finditer(heading_pattern, text, flags))
        if not matches:
            return [(0, text)]

        sections: List[Tuple[int, str]] = []
        for idx, m in enumerate(matches):
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            sections.append((idx + 1, text[start:end].strip()))
        return sections

    def split_by_blocks(self, blank_lines: int = 1) -> List[str]:
        """Split text into blocks separated by one or more blank lines.

        Useful when a document has no consistent headings but uses spacing to
        separate logical chunks.
        """
        sep = r"\n{%d,}" % (blank_lines + 1)
        return [b.strip() for b in re.split(sep, self.full_text()) if b.strip()]

    # -- generic field extraction ------------------------------------------
    def find_all(self, pattern: str, flags: int = 0) -> List[str]:
        """Return every match of a regex across the full document text."""
        return re.findall(pattern, self.full_text(), flags)

    def extract_fields(
        self, rules: Dict[str, Callable[[str], Optional[str]]]
    ) -> Dict[str, Optional[str]]:
        """Run a dict of named extractor callables against the full text.

        This is the plug-in point for your own logic. Each rule is a function
        that takes the document text and returns a value (or None).

            rules = {
                "effective_date": lambda t: (m.group(0)
                    if (m := re.search(DATE_RE, t)) else None),
                "governing_law": my_governing_law_extractor,
            }
            engine.extract_fields(rules)

        Returns:
            ``{field_name: value_or_None}``.
        """
        text = self.full_text()
        return {name: fn(text) for name, fn in rules.items()}

    # -- contract-flavored example extractors ------------------------------
    # These show the *shape* of real extractors. Treat them as starting points
    # and tighten the patterns for your documents.
    _DATE_RE = (
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},\s+\d{4}\b"
        r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
        r"|\b\d{4}-\d{2}-\d{2}\b"
    )
    _MONEY_RE = r"(?:US)?\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"
    # "Defined Terms" in quotes, common in contracts: ("the Company")
    _DEFINED_TERM_RE = r'[“"]([A-Z][A-Za-z0-9 ]+?)[”"]'

    def find_dates(self) -> List[str]:
        """Find date-like strings (long-form, slash, and ISO)."""
        return self.find_all(self._DATE_RE)

    def find_money(self) -> List[str]:
        """Find dollar amounts like $1,000 or US$ 2,500.00."""
        return self.find_all(self._MONEY_RE)

    def find_defined_terms(self) -> List[str]:
        """Find quoted defined terms, e.g. "the Company", "Effective Date"."""
        return list(dict.fromkeys(self.find_all(self._DEFINED_TERM_RE)))


# ---------------------------------------------------------------------------
# CLI / demo
# ---------------------------------------------------------------------------
def _demo(path: str) -> None:
    engine = PDFTextEngine(path)
    pages = engine.pages()
    print(f"Parsed {len(pages)} page(s) from {path}")
    strategies = {p.strategy for p in pages}
    print(f"Extraction strategies used: {', '.join(sorted(strategies))}")

    text = engine.full_text()
    print(f"Total characters: {len(text):,}")
    print("\n--- First 500 characters ---")
    print(text[:500])

    dates = engine.find_dates()
    money = engine.find_money()
    print(f"\nDates found ({len(dates)}): {dates[:10]}")
    print(f"Amounts found ({len(money)}): {money[:10]}")

    tables = engine.extract_tables()
    print(f"Tables found: {len(tables)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_text_engine.py <file.pdf>")
        raise SystemExit(1)
    _demo(sys.argv[1])
