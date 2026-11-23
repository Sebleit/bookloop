"""The picture of a swap, for moderators: who gives which book to whom.

People are boxes, top to bottom, in the order the books go round. Each book
is an arrow from the giver to the receiver, coloured by what has happened:
green once it was handed over, grey while it's still waiting, red if the swap
was cancelled. The last arrow goes up the right-hand side, back to the first
person.

Everything has a fixed place, so nothing can overlap, whatever the names and
titles: each label has its own slot next to its arrow, long titles and names
are cut with "…" (the full text shows when you hover over it), and every text
is clipped to its slot as a last safety net. A loop has 2 to 6 people, so the
picture is at most 620 × 560 pixels.

Pages show it with st.markdown(..., unsafe_allow_html=True), because st.html
removes SVG. That's safe here: every name and title is escaped, so text typed
by a user can never become HTML. This module only writes the SVG text, so it
can be tested without a browser.
"""

import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from typing import Protocol

MAX_TITLE = 28  # characters of a book's title shown; enough to tell books apart
MAX_NAME = 14  # characters of a person's name shown

# status: (colour, dashes, word shown under the book's title)
STYLES = {
    "completed": ("#2e7d32", "none", "handed over"),
    "pending": ("#757575", "6 4", "waiting"),
    "cancelled": ("#c62828", "2 4", "cancelled"),
}

# Sizes in pixels.
BOX_X, BOX_WIDTH, BOX_HEIGHT = 20, 150, 40  # each person's box
TOP, ROW = 36, 96  # middle of the first box, and the distance between boxes
SLOT_WIDTH, SLOT_HEIGHT = 236, 48  # the space for each book's label
DOWN_LABEL_X = BOX_X + BOX_WIDTH // 2 + 12  # labels of the arrows going down
RETURN_X = 372  # the arrow going back up to the first person
RETURN_LABEL_X = RETURN_X + 8
WIDTH = RETURN_LABEL_X + SLOT_WIDTH + 4
FONT = "'Source Sans Pro', 'Source Sans 3', Helvetica, Arial, sans-serif"


class _Trade(Protocol):
    title: str
    giver_name: str
    receiver_name: str
    status: str


@dataclass(frozen=True)
class Box:
    """A rectangle on the picture: where something is drawn."""

    x: float
    y: float
    width: float
    height: float

    def overlaps(self, other: "Box") -> bool:
        return (
            self.x < other.x + other.width
            and other.x < self.x + self.width
            and self.y < other.y + other.height
            and other.y < self.y + self.height
        )


@dataclass(frozen=True)
class Layout:
    """Where everything goes for a loop of `count` people."""

    count: int

    @property
    def height(self) -> int:
        return TOP * 2 + ROW * (self.count - 1)

    def middle(self, person: int) -> int:
        return TOP + ROW * person

    def person(self, number: int) -> Box:
        return Box(BOX_X, self.middle(number) - BOX_HEIGHT / 2, BOX_WIDTH, BOX_HEIGHT)

    def label(self, number: int) -> Box:
        """The slot for book `number`: next to its arrow down, or by the arrow back up."""
        if number < self.count - 1:
            between = (self.middle(number) + self.middle(number + 1)) / 2
            return Box(DOWN_LABEL_X - 4, between - SLOT_HEIGHT / 2, SLOT_WIDTH, SLOT_HEIGHT)
        between = (self.middle(0) + self.middle(self.count - 1)) / 2
        return Box(RETURN_LABEL_X, between - SLOT_HEIGHT / 2, SLOT_WIDTH, SLOT_HEIGHT)

    def boxes(self) -> list[Box]:
        return [self.person(i) for i in range(self.count)] + [self.label(i) for i in range(self.count)]


def shorten(text: str, limit: int) -> str:
    """Cut text to `limit` characters, ending with "…" if anything was cut."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def loop_svg(trades: Sequence[_Trade]) -> str:
    """SVG for one loop. `trades` go in order around the loop, as storage returns them."""
    layout = Layout(len(trades))
    key = f"bl{zlib.crc32(repr([(t.giver_name, t.title) for t in trades]).encode()):x}"  # unique ids per picture
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{layout.height}" '
        f'viewBox="0 0 {WIDTH} {layout.height}" style="max-width:100%;height:auto" '
        f'role="img" aria-label="{escape(_summary(trades))}" font-family="{FONT}">',
        "<defs>",
    ]
    for status, (colour, _, _) in STYLES.items():
        parts.append(
            f'<marker id="{key}-{status}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{colour}"/></marker>'
        )
    for number in range(len(trades)):
        parts.append(_clip(f"{key}-label{number}", layout.label(number)))
        box = layout.person(number)  # names stop 8 pixels inside their box
        parts.append(_clip(f"{key}-name{number}", Box(box.x + 8, box.y, box.width - 16, box.height)))
    parts.append("</defs>")

    for number, trade in enumerate(trades):
        status = trade.status if trade.status in STYLES else "pending"
        colour, dashes, word = STYLES[status]
        line = (
            f'fill="none" stroke="{colour}" stroke-width="2" stroke-dasharray="{dashes}" '
            f'marker-end="url(#{key}-{status})"'
        )
        if number < len(trades) - 1:  # down to the next person
            x = BOX_X + BOX_WIDTH // 2
            start, end = layout.person(number), layout.person(number + 1)
            arrow = f'<path d="M{x},{start.y + start.height} V{end.y - 1}" {line}/>'
        else:  # back up the right-hand side to the first person
            right = BOX_X + BOX_WIDTH
            low, high = layout.middle(len(trades) - 1), layout.middle(0)
            arrow = (
                f'<path d="M{right},{low} H{RETURN_X - 12} Q{RETURN_X},{low} {RETURN_X},{low - 12} '
                f'V{high + 12} Q{RETURN_X},{high} {RETURN_X - 12},{high} H{right + 1}" {line}/>'
            )
        slot = layout.label(number)
        text_x = slot.x + (4 if number < len(trades) - 1 else 8)
        middle = slot.y + slot.height / 2
        hover = escape(f"{trade.title} ({word}): {trade.giver_name} → {trade.receiver_name}")
        parts.append(
            f"<g><title>{hover}</title>{arrow}"
            f'<g clip-path="url(#{key}-label{number})" fill="{colour}">'
            f'<text x="{text_x}" y="{middle - 4}" font-size="13">{escape(shorten(trade.title, MAX_TITLE))}</text>'
            f'<text x="{text_x}" y="{middle + 13}" font-size="12">{word}</text></g></g>'
        )

    for number, trade in enumerate(trades):
        box = layout.person(number)
        parts.append(
            f"<g><title>{escape(trade.giver_name)}</title>"
            f'<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}" rx="20" '
            f'fill="#eef1f6" stroke="#8a94a6" stroke-width="1.5"/>'
            f'<text x="{box.x + box.width / 2}" y="{box.y + box.height / 2 + 5}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="#1f2933" clip-path="url(#{key}-name{number})">'
            f"{escape(shorten(trade.giver_name, MAX_NAME))}</text></g>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _clip(clip_id: str, box: Box) -> str:
    return (
        f'<clipPath id="{clip_id}"><rect x="{box.x}" y="{box.y}" '
        f'width="{box.width}" height="{box.height}"/></clipPath>'
    )


def _summary(trades: Sequence[_Trade]) -> str:
    names = [trade.giver_name for trade in trades]
    return "Swap: " + " → ".join(names + names[:1])
