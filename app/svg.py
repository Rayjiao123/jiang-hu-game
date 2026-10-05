"""Whitelist sanitiser for model-written SVG: plain shapes only, no scripts,
links, external references or entity tricks."""
import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

ALLOWED_ELEMENTS = {"svg", "g", "rect", "circle", "ellipse", "path", "polygon", "polyline", "line"}
ALLOWED_ATTRS = {
    "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "fill-opacity",
    "stroke-opacity", "transform", "fill-rule",
}
BAD_VALUE = re.compile(r"url\s*\(|javascript:|expression\s*\(", re.I)
MAX_LEN = 40_000


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def extract(text: str) -> str | None:
    m = re.search(r"<svg[\s\S]*</svg>", text, re.I)
    return m.group(0) if m else None


def clean(src: str) -> str | None:
    if not src or len(src) > MAX_LEN or "<!" in src or "<?" in src:
        return None
    try:
        root = ET.fromstring(src)
    except ET.ParseError:
        return None
    if _local(root.tag) != "svg":
        return None

    def walk(el):
        for child in list(el):
            if _local(child.tag) not in ALLOWED_ELEMENTS:
                el.remove(child)
                continue
            child.tag = f"{{{SVG_NS}}}{_local(child.tag)}"
            _scrub(child)
            child.text = child.tail = None
            walk(child)

    root.tag = f"{{{SVG_NS}}}svg"
    _scrub(root)
    root.text = None
    walk(root)
    return ET.tostring(root, encoding="unicode")


def _scrub(el) -> None:
    for name in list(el.attrib):
        if _local(name) not in ALLOWED_ATTRS or "}" in name or BAD_VALUE.search(el.attrib[name]):
            del el.attrib[name]
