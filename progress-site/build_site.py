"""Build the progress site: embed the current docs into progress-site/template.html.

The page parses the raw Markdown of the work plan, the progress tracker and the architecture doc in
the browser, so the only thing this script does is inline those three files. Stdlib only, so the
Pages workflow needs no install step.

    python progress-site/build_site.py                 # full document at _site/index.html (Pages)
    python progress-site/build_site.py --fragment OUT  # body-only page, for a claude.ai artifact
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = {
    "plan": "tfm-work-plan.md",
    "arch": "tfm-architecture-and-dod.md",
    "track": "progress-tracker.md",
}

# The artifact viewer wraps the page in this skeleton itself; GitHub Pages needs it written out.
HEAD = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>body { margin: 0; } img { max-width: 100%; } [hidden] { display: none !important; }</style>
</head>
<body>
"""
TAIL = "\n</body>\n</html>\n"


def build(fragment: bool) -> str:
    docs = {key: (ROOT / "docs" / name).read_text(encoding="utf-8") for key, name in DOCS.items()}
    # "</" inside the embedded JSON would close the <script> element early.
    data = json.dumps(docs, ensure_ascii=False).replace("</", "<\\/")
    page = (ROOT / "progress-site" / "template.html").read_text(encoding="utf-8")
    page = page.replace("__DOCS_JSON__", data)
    return page if fragment else HEAD + page + TAIL


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", nargs="?", type=Path, default=ROOT / "_site" / "index.html")
    parser.add_argument("--fragment", action="store_true", help="omit <html>/<head>/<body>")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build(args.fragment), encoding="utf-8")
    print(f"{args.output}: {args.output.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
