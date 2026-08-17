#!/usr/bin/env python3
"""
Robust GitHub Streak Stats Fallback & Offset Tool
- If profile/streak.svg exists from DenverCoder1/github-readme-streak-stats, it offsets Total Contributions (+40).
- If DenverCoder1 action failed (e.g. GitHub GraphQL 503 outage), it fetches contributions directly from
  the public HTML contributions calendar, computes exact current/longest streak and total, and writes profile/streak.svg.
"""

import argparse
import datetime
import os
import re
import sys
import urllib.request


def fetch_contributions_html(username):
    url = f"https://github.com/users/{username}/contributions"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Error fetching contributions HTML: {e}", file=sys.stderr)
        return None


def calculate_streak_data(html, offset=40):
    matches = re.findall(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*>[\s\S]*?<tool-tip[^>]*>([\s\S]*?)</tool-tip>',
        html,
    )
    if not matches:
        print("Could not parse contribution days from HTML", file=sys.stderr)
        return None

    contributions = {}
    total = 0
    for date, tip in matches:
        m = re.search(r"(\d+)\s+contribution", tip)
        c = int(m.group(1)) if m else 0
        contributions[date] = c
        total += c

    sorted_dates = sorted(contributions.keys())
    all_days = [(d, contributions[d]) for d in reversed(sorted_dates)]

    # Current streak: scan backwards from newest date with > 0 contributions
    idx = 0
    while idx < len(all_days) and all_days[idx][1] == 0:
        idx += 1

    current_streak = 0
    streak_end = None
    streak_start = None
    if idx < len(all_days):
        streak_end = all_days[idx][0]
        while idx < len(all_days) and all_days[idx][1] > 0:
            streak_start = all_days[idx][0]
            current_streak += 1
            idx += 1

    # Longest streak: scan forward chronologically
    longest_streak = 0
    cur = 0
    l_start = None
    l_end = None
    temp_start = None
    for d in sorted_dates:
        if contributions[d] > 0:
            if cur == 0:
                temp_start = d
            cur += 1
            if cur > longest_streak:
                longest_streak = cur
                l_start = temp_start
                l_end = d
        else:
            cur = 0

    def fmt_date(d_str):
        if not d_str:
            return ""
        dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
        return dt.strftime("%b %-d")

    return {
        "total": total + offset,
        "current_streak": current_streak,
        "current_range": f"{fmt_date(streak_start)} - {fmt_date(streak_end)}",
        "longest_streak": longest_streak,
        "longest_range": f"{fmt_date(l_start)} - {fmt_date(l_end)}",
    }


def update_svg_file(svg_path, data):
    if not os.path.exists(svg_path):
        print(f"File {svg_path} does not exist", file=sys.stderr)
        return False

    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()

    total_str = f"{data['total']:,}"
    curr_streak_str = str(data["current_streak"])
    longest_streak_str = str(data["longest_streak"])
    curr_range_str = data["current_range"]
    longest_range_str = data["longest_range"]

    svg = re.sub(
        r"(<!-- Total Contributions big number -->.*?<text[^>]*>\s*)([0-9,]+)(\s*</text>)",
        f"\\g<1>{total_str}\\g<3>",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(
        r"(<!-- Current Streak range -->.*?<text[^>]*>\s*)([^\n<]+)(\s*</text>)",
        f"\\g<1>{curr_range_str}\\g<3>",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(
        r"(<!-- Current Streak big number -->.*?<text[^>]*>\s*)([0-9,]+)(\s*</text>)",
        f"\\g<1>{curr_streak_str}\\g<3>",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(
        r"(<!-- Longest Streak big number -->.*?<text[^>]*>\s*)([0-9,]+)(\s*</text>)",
        f"\\g<1>{longest_streak_str}\\g<3>",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(
        r"(<!-- Longest Streak range -->.*?<text[^>]*>\s*)([^\n<]+)(\s*</text>)",
        f"\\g<1>{longest_range_str}\\g<3>",
        svg,
        flags=re.DOTALL,
    )

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    print(
        f"Successfully updated {svg_path}: Total={total_str}, Current={curr_streak_str} ({curr_range_str}), Longest={longest_streak_str} ({longest_range_str})"
    )
    return True


def offset_existing_svg(svg_path, offset=40):
    if not os.path.exists(svg_path):
        return False
    with open(svg_path, "r", encoding="utf-8") as f:
        svg = f.read()

    # Check if the SVG is an error card
    if "Failed to retrieve contributions" in svg or "Error" in svg:
        print("SVG contains an error message, skipping offset.", file=sys.stderr)
        return False

    pattern = r"(<!-- Total Contributions big number -->.*?<text[^>]*>\s*)([0-9,]+)(\s*</text>)"
    m = re.search(pattern, svg, flags=re.DOTALL)
    if not m:
        return False

    num = int(m.group(2).replace(",", "")) + offset
    new_svg = re.sub(
        pattern,
        lambda match: f"{match.group(1)}{num:,}{match.group(3)}",
        svg,
        flags=re.DOTALL,
    )
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(new_svg)
    print(f"Successfully offset Total Contributions (+{offset}) -> {num:,}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Update GitHub Streak SVG")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--path", default="profile/streak.svg", help="Path to streak.svg")
    parser.add_argument("--offset", type=int, default=40, help="Offset for total contributions")
    parser.add_argument("--force-fallback", action="store_true", help="Always scrape and recalculate")
    args = parser.parse_args()

    # If not forcing fallback, check if we just need to offset an existing valid SVG generated by the action
    if not args.force_fallback and os.path.exists(args.path):
        with open(args.path, "r", encoding="utf-8") as f:
            content = f.read()
        if "Failed to retrieve contributions" not in content and "<!-- Total Contributions big number -->" in content:
            # Action succeeded, just offset
            if offset_existing_svg(args.path, args.offset):
                return

    # Fallback to scraping public contributions endpoint
    print("Running fallback scraper for contributions...")
    html = fetch_contributions_html(args.username)
    if not html:
        print("Could not fetch HTML contributions", file=sys.stderr)
        sys.exit(1)

    data = calculate_streak_data(html, args.offset)
    if not data:
        print("Failed to calculate streak data from HTML", file=sys.stderr)
        sys.exit(1)

    if not update_svg_file(args.path, data):
        sys.exit(1)


if __name__ == "__main__":
    main()
