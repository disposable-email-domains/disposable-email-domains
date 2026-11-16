#!/usr/bin/env python3
"""Generate statistics markdown table from fetch_stats.json for GitHub Actions"""

import json
import os


def cell(text: str) -> str:
    """Make text safe for a markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def status(data: dict) -> str:
    if data.get("error"):
        return f"❌ {cell(data['error'])}"
    if data.get("warning"):
        return f"⚠️ {cell(data['warning'])}"
    return "✅"


def main():
    stats_file = "fetch_stats.json"
    output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")

    if not os.path.exists(stats_file):
        with open(output_file, "a") as f:
            f.write("stats=No statistics available\n")
        return

    with open(stats_file) as f:
        stats = json.load(f)

    failed = sum(1 for data in stats.values() if data.get("error"))
    lines = [
        "## Statistics",
        "",
        f"{len(stats) - failed} of {len(stats)} sources succeeded.",
        "",
        "| Source | Domains Found | New Added | Status |",
        "|--------|---------------|-----------|--------|",
    ]

    # Failed sources first, so they are seen
    for source, data in sorted(stats.items(), key=lambda item: (not item[1].get("error"), item[0].lower())):
        found = data.get("found", 0)
        added = data.get("added", 0)
        lines.append(f"| {cell(source)} | {found} | {added} | {status(data)} |")

    # Write to GITHUB_OUTPUT using multiline syntax
    with open(output_file, "a") as f:
        f.write("stats<<EOF\n")
        f.write("\n".join(lines))
        f.write("\nEOF\n")


if __name__ == "__main__":
    main()
