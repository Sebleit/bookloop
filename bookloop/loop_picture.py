"""The picture of a swap, for moderators: who gives which book to whom.

People are circles, placed left to right, and each book is an arrow from
the giver to the receiver, labelled with its title and coloured by what has
happened: green once it was handed over, grey while it's still waiting, red if
the swap was cancelled. (Left to right keeps every label clear of the others,
even when two people swap with each other.) Streamlit draws it
with st.graphviz_chart; this module only writes the Graphviz text, so it can
be tested without a browser.
"""

from collections.abc import Sequence
from typing import Protocol


class _Trade(Protocol):
    title: str
    giver_name: str
    receiver_name: str
    status: str


# status: (colour, line style, word shown under the book's title)
STYLES = {
    "completed": ("#2e7d32", "solid", "handed over"),
    "pending": ("#757575", "dashed", "waiting"),
    "cancelled": ("#c62828", "dotted", "cancelled"),
}


def _quoted(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def loop_dot(trades: Sequence[_Trade]) -> str:
    """Graphviz text for one loop: a circle of people with an arrow per book."""
    lines = [
        "digraph swap {",
        "  rankdir=LR; nodesep=0.9; ranksep=2.2;",
        '  node [shape=circle, fixedsize=true, width=0.75, style=filled, fillcolor="#eef1f6", '
        'color="#8a94a6", fontname="Helvetica", fontsize=12];',
        '  edge [fontname="Helvetica", fontsize=10, penwidth=2];',
    ]
    for trade in trades:
        colour, style, word = STYLES.get(trade.status, STYLES["pending"])
        label = _quoted(f"{trade.title}\n{word}").replace("\n", "\\n")
        lines.append(
            f"  {_quoted(trade.giver_name)} -> {_quoted(trade.receiver_name)} "
            f'[label={label}, color="{colour}", fontcolor="{colour}", style={style}];'
        )
    lines.append("}")
    return "\n".join(lines)
