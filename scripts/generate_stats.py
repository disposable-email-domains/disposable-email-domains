#!/usr/bin/env python3
"""Generate statistics markdown table from fetch_stats.json for GitHub Actions"""

import json
import os

def main():
    stats_file = "fetch_stats.json"
    output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")

    if not os.path.exists(stats_file):
        with open(output_file, "a") as f:
            f.write("stats=No statistics available\n")
        return

    with open(stats_file) as f:
        stats = json.load(f)

    lines = [
        "## Statistics",
        "",
        "| Source | Domains Found | New Added |",
        "|--------|---------------|-----------|",
    ]

    for source, data in sorted(stats.items()):
        found = data.get("found", 0)
        added = data.get("added", 0)
        error = data.get("error", "")
        status = f"Error: {error}"[:15] if error else ""
        lines.append(f"| {source} | {found} | {added} |{status}")

    # Write to GITHUB_OUTPUT using multiline syntax
    with open(output_file, "a") as f:
        f.write("stats<<EOF\n")
        f.write("\n".join(lines))
        f.write("\nEOF\n")

if __name__ == "__main__":
    main()
