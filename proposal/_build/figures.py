"""Draw the two proposal figures as PNG files.

Usage: python proposal/_build/figures.py   (needs matplotlib)

Coordinates are in inches, and every box is sized from its own text, so no
text can run past a box edge.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "figures"
_available = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next((f for f in ("Calibri", "Carlito", "DejaVu Sans") if f in _available))

INK = "#1F2A33"
GREY = "#55626C"
PALETTE = {
    "data": ("#E8F0F8", "#3A6EA5"),
    "proc": ("#EEF3EA", "#4F7D3A"),
    "gate": ("#FFF4DE", "#B7791F"),
    "act": ("#E3F2E7", "#2E7D4F"),
    "verify": ("#E6EEF9", "#2F5D9B"),
    "review": ("#FBEFD9", "#A0661A"),
    "hold": ("#F8E3E1", "#A3342A"),
    "side": ("#F1EEF6", "#6A5A8C"),
}
TITLE_PT, BODY_PT, LINE = 10.5, 8.6, 1.32


def box_height(body: str) -> float:
    lines = body.count("\n") + 1 if body else 0
    return 0.16 + TITLE_PT / 72 + (0.08 + lines * BODY_PT * LINE / 72 if lines else 0) + 0.12


class Canvas:
    def __init__(self, width: float, height: float, title: str) -> None:
        self.fig = plt.figure(figsize=(width, height), dpi=220)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, width)
        self.ax.set_ylim(0, height)
        self.ax.axis("off")
        self.ax.text(width / 2, height - 0.12, title, ha="center", va="top", fontsize=13,
                     fontweight="bold", color=INK)

    def box(self, x: float, top: float, w: float, title: str, body: str, kind: str, h: float | None = None):
        """Draw a box whose top edge is at `top`; returns (x, bottom, w, h)."""
        fill, edge = PALETTE[kind]
        h = h or box_height(body)
        y = top - h
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                         linewidth=1.2, edgecolor=edge, facecolor=fill))
        self.ax.text(x + w / 2, top - 0.15, title, ha="center", va="top", fontsize=TITLE_PT,
                     fontweight="bold", color=edge)
        if body:
            self.ax.text(x + w / 2, top - 0.15 - TITLE_PT / 72 - 0.08, body, ha="center", va="top",
                         fontsize=BODY_PT, color=INK, linespacing=LINE)
        return x, y, w, h

    def arrow(self, x1, y1, x2, y2, color=GREY, ls="-", label=None, label_dx=0.06):
        self.ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
                                          linewidth=1.2, color=color, linestyle=ls, shrinkA=1, shrinkB=1))
        if label:
            self.ax.text((x1 + x2) / 2 + label_dx, (y1 + y2) / 2, label, fontsize=8, color=color,
                         ha="left", va="center")

    def save(self, name: str) -> None:
        path = OUT / name
        self.fig.savefig(path, facecolor="white")
        plt.close(self.fig)
        _trim(path)


def _trim(path: Path, margin: int = 24) -> None:
    """Crop the white border left around the drawing."""
    from PIL import Image, ImageChops

    image = Image.open(path).convert("RGB")
    diff = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
    left, top, right, bottom = diff.getbbox()
    image.crop((max(0, left - margin), max(0, top - margin), min(image.width, right + margin),
                min(image.height, bottom + margin))).save(path, dpi=(220, 220))


def bottom_center(b):
    x, y, w, _ = b
    return x + w / 2, y


def top_center(b):
    x, y, w, h = b
    return x + w / 2, y + h


def figure_1() -> None:
    W, H = 7.2, 8.3
    c = Canvas(W, H, "Proposed fidelity-gated decision pipeline")
    gap = 0.12
    w3 = (W - 0.2 - 2 * gap) / 3
    top = H - 0.55
    sources = [
        ("Public AIS archives", "NOAA (US), Danish Maritime\nAuthority, Norway, Finland;\nreplayed at real-time speed"),
        ("Live Gulf recording", "aisstream.io feed for the Gulf,\nHormuz and Gulf of Oman,\nrecorded daily from Oct 2026"),
        ("Commitments and notices", "bookings and schedules (DCSA);\ncarrier advisories such as End\nof Voyage and port omissions"),
    ]
    row1 = [c.box(0.1 + i * (w3 + gap), top, w3, t, b, "data") for i, (t, b) in enumerate(sources)]

    top = min(b[1] for b in row1) - 0.38
    ingest = c.box(0.55, top, W - 1.1, "Ingestion and cleaning",
                   "one schema for all sources; duplicate MMSI, stale retransmissions and timestamp errors removed;\nraw messages kept verbatim in a causal, as-of-time evidence store", "proc")
    for b in row1:
        x, y = bottom_center(b)
        c.arrow(x, y, min(max(x, ingest[0] + 0.4), ingest[0] + ingest[2] - 0.4), ingest[1] + ingest[3])

    top = ingest[1] - 0.38
    w2 = (W - 0.2 - 0.5) / 2
    branch_a = c.box(0.1, top, w2, "Branch A: location fidelity",
                     "physics residuals: speed, turn rate, land, gaps\nmulti-vessel coherence and jamming zones\n(H3 cell x 10 min); base-station position drift\nport calls flagged inside zones or gaps", "proc")
    branch_b = c.box(0.1 + w2 + 0.5, top, w2, "Branch B: commitment watch",
                     "corruption-aware CUSUM for every voyage;\neach reading weighted by P(uncorrupted)\nfrom the jamming map of other vessels;\nnotice-aware labels and cost exposure", "proc")
    xi, yi = ingest[0], ingest[1]
    c.arrow(xi + ingest[2] * 0.3, yi, branch_a[0] + w2 / 2, branch_a[1] + branch_a[3])
    c.arrow(xi + ingest[2] * 0.7, yi, branch_b[0] + w2 / 2, branch_b[1] + branch_b[3])
    mid_y = branch_a[1] + branch_a[3] / 2
    c.arrow(branch_a[0] + w2, mid_y, branch_b[0], mid_y, color=PALETTE["proc"][1])
    c.ax.text(W / 2, mid_y + 0.08, "zones", ha="center", va="bottom", fontsize=8, color=PALETTE["proc"][1])

    top = branch_a[1] - 0.38
    side_w = 1.25
    gate = c.box(side_w + 0.35, top, W - 2 * side_w - 0.7, "Fidelity gate",
                 "decision-weighted fidelity F(E, a) against\nthe threshold for action a; m-of-n independent\nsupport (jammed sources count zero); hard\nconstraints; conformal calibration", "gate")
    gy = gate[1] + gate[3] / 2
    bench = c.box(0.1, gy + 0.42, side_w, "Benchmark", "synthetic attacks\nand red team", "side")
    agent = c.box(W - 0.1 - side_w, gy + 0.42, side_w, "Agent", "proposes\naction a", "side")
    c.arrow(bench[0] + side_w, bench[1] + bench[3] / 2, gate[0], bench[1] + bench[3] / 2, color=PALETTE["side"][1], ls="--")
    c.arrow(agent[0], agent[1] + agent[3] / 2, gate[0] + gate[2], agent[1] + agent[3] / 2, color=PALETTE["side"][1])
    c.arrow(*bottom_center(branch_a), gate[0] + gate[2] * 0.3, gate[1] + gate[3])
    c.arrow(*bottom_center(branch_b), gate[0] + gate[2] * 0.7, gate[1] + gate[3])

    top = gate[1] - 0.45
    gap4 = 0.12
    w4 = (W - 0.2 - 3 * gap4) / 4
    verdicts = [
        ("ACT", "execute with a signed,\nshort-lived token", "act"),
        ("VERIFY", "run the cheapest check\nthat can change the verdict", "verify"),
        ("REVIEW", "human reviewer with\nevidence and case file", "review"),
        ("HOLD", "wait; timeouts and\nmissing data end here", "hold"),
    ]
    gx, gyb = bottom_center(gate)
    for i, (t, b, k) in enumerate(verdicts):
        v = c.box(0.1 + i * (w4 + gap4), top, w4, t, b, k)
        c.arrow(gx + (i - 1.5) * 0.35, gyb, *top_center(v))
    c.save("figure1_pipeline.png")


def figure_2() -> None:
    W, H = 7.2, 6.6
    c = Canvas(W, H, "Gate decision for one proposed action")
    action = c.box(1.7, H - 0.55, W - 3.4, "Proposed action a",
                   "for example: cancel Jebel Ali trucking and book Sohar;\nevidence snapshot E as of the decision time", "side")
    checks = c.box(0.5, action[1] - 0.4, W - 1.0, "Three checks",
                   "1. Fidelity: F(E, a) is at or above the threshold for this action class\n"
                   "2. Independence: m supports with disjoint provenance roots, none inside a jamming zone\n"
                   "3. Constraints: physics, capacity and legal rules pass", "gate")
    c.arrow(*bottom_center(action), *top_center(checks))

    top = checks[1] - 0.45
    w = (W - 0.2 - 0.4) / 2
    act = c.box(0.1, top, w, "All three pass: ACT",
                "execute with a token bound to the exact\nparameters, the evidence snapshot and\na short expiry", "act")
    least = c.box(0.1 + w + 0.4, top, w, "Any check fails: least expected cost",
                  "compare harm if wrong with the costs of a\ncheck, a human review and the delay", "proc",
                  h=act[3])
    cx, cy = bottom_center(checks)
    c.arrow(cx - 1.4, cy, *top_center(act), color=PALETTE["act"][1], label="yes")
    c.arrow(cx + 1.4, cy, *top_center(least), label="no")

    top = least[1] - 0.45
    w3 = 1.7
    x0 = least[0] + least[2] / 2 - (3 * w3 + 2 * 0.12) / 2
    x0 = min(x0, W - 0.1 - (3 * w3 + 2 * 0.12))
    outs = [
        ("VERIFY", "best check is worth its\ncost; then the three\nchecks run again", "verify"),
        ("REVIEW", "high stakes or\nunresolved; a human\ndecides", "review"),
        ("HOLD", "waiting costs less\nthan the expected harm;\ntimeouts end here", "hold"),
    ]
    boxes = []
    lx, ly = bottom_center(least)
    for i, (t, b, k) in enumerate(outs):
        bx = c.box(x0 + i * (w3 + 0.12), top, w3, t, b, k)
        boxes.append(bx)
        c.arrow(lx + (i - 1) * 0.5, ly, *top_center(bx))
    c.save("figure2_gate.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    figure_1()
    figure_2()
    print("wrote", *sorted(p.name for p in OUT.glob("*.png")))
