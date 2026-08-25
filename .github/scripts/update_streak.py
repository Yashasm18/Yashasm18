#!/usr/bin/env python3
"""
Robust GitHub Streak Stats Generator & Fallback Tool
- Fetches contributions directly from GitHub's public contribution calendar.
- Correctly parses the modern GitHub DOM structure (mapping tool-tips to date cells).
- Accurately computes current streak, longest streak, and total contributions with timezone awareness (Asia/Kolkata default).
- Updates or generates the themed profile/streak.svg file.
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Error fetching contributions HTML: {e}", file=sys.stderr)
        return None


def calculate_streak_data(html, offset=40, tz_hours=5.5):
    # Match all td elements with date, id, and data-level
    td_matches = re.findall(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="([^"]+)"',
        html,
    )
    # Match tooltips with for attribute
    tooltips = re.findall(
        r'<tool-tip[^>]*for="([^"]+)"[^>]*>([\s\S]*?)</tool-tip>',
        html,
    )

    tip_map = {}
    for for_id, tip_text in tooltips:
        m = re.search(r"(\d+)\s+contribution", tip_text)
        tip_map[for_id] = int(m.group(1)) if m else 0

    contributions = {}
    total = 0
    for date, cell_id in td_matches:
        c = tip_map.get(cell_id, 0)
        contributions[date] = c
        total += c

    # Fallback to header total if available
    m_header = re.search(r"(\d[\d,]*)\s+contributions?\s+in\s+the\s+last\s+year", html)
    if m_header:
        total = int(m_header.group(1).replace(",", ""))

    if not contributions:
        print("Could not parse contribution days from HTML", file=sys.stderr)
        return None

    sorted_dates = sorted(contributions.keys())

    # User timezone (default: Asia/Kolkata +5:30)
    tz = datetime.timezone(datetime.timedelta(hours=tz_hours))
    now_tz = datetime.datetime.now(tz)
    today_str = now_tz.strftime("%Y-%m-%d")
    yesterday_str = (now_tz - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # Current streak calculation:
    # 1. If today has contributions > 0, streak is active and ends today.
    # 2. If today has 0 contributions, but yesterday has > 0 contributions,
    #    streak is STILL ACTIVE and ends yesterday (today is still ongoing).
    # 3. If both today and yesterday have 0 contributions, streak is broken (0).
    current_streak = 0
    streak_start = None
    streak_end = None

    if contributions.get(today_str, 0) > 0:
        streak_end = today_str
        scan_dt = now_tz
        while True:
            d_str = scan_dt.strftime("%Y-%m-%d")
            if contributions.get(d_str, 0) > 0:
                streak_start = d_str
                current_streak += 1
                scan_dt -= datetime.timedelta(days=1)
            else:
                break
    elif contributions.get(yesterday_str, 0) > 0:
        streak_end = yesterday_str
        scan_dt = now_tz - datetime.timedelta(days=1)
        while True:
            d_str = scan_dt.strftime("%Y-%m-%d")
            if contributions.get(d_str, 0) > 0:
                streak_start = d_str
                current_streak += 1
                scan_dt -= datetime.timedelta(days=1)
            else:
                break
    else:
        current_streak = 0
        streak_start = None
        streak_end = today_str

    # Longest streak calculation across the entire retrieved history
    longest_streak = 0
    l_start = None
    l_end = None
    cur_len = 0
    cur_start = None

    for d in sorted_dates:
        if contributions[d] > 0:
            if cur_len == 0:
                cur_start = d
            cur_len += 1
            if cur_len > longest_streak:
                longest_streak = cur_len
                l_start = cur_start
                l_end = d
        else:
            cur_len = 0

    # Ensure longest streak is at least current streak
    if current_streak > longest_streak:
        longest_streak = current_streak
        l_start = streak_start
        l_end = streak_end

    def fmt_date(d_str):
        if not d_str:
            return ""
        dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
        return dt.strftime("%b %-d")

    curr_range = f"{fmt_date(streak_start)} - {fmt_date(streak_end)}" if current_streak > 0 else fmt_date(today_str)
    longest_range = f"{fmt_date(l_start)} - {fmt_date(l_end)}" if longest_streak > 0 else ""

    return {
        "total": total + offset,
        "current_streak": current_streak,
        "current_range": curr_range,
        "longest_streak": longest_streak,
        "longest_range": longest_range,
    }


def generate_svg(data):
    total_str = f"{data['total']:,}"
    curr_streak_str = str(data["current_streak"])
    longest_streak_str = str(data["longest_streak"])
    curr_range_str = data["current_range"]
    longest_range_str = data["longest_range"]

    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 28px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='4.5'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='#000000' stroke-opacity='0' fill='#010102' rx='4.5' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#010102' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='#010102' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            <g style='isolation: isolate'>
                <!-- Total Contributions big number -->
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#e9e9f5' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                        {total_str}
                    </text>
                </g>

                <!-- Total Contributions label -->
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#b9bcd9' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>
                        Total Contributions
                    </text>
                </g>

                <!-- Total Contributions range -->
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#8890c0' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>
                        Sep 25, 2025 - Present
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <!-- Current Streak label -->
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#b9bcd9' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        Current Streak
                    </text>
                </g>

                <!-- Current Streak range -->
                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' stroke-width='0' text-anchor='middle' fill='#8890c0' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        {curr_range_str}
                    </text>
                </g>

                <!-- Ring around number -->
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='#a78bfa' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <!-- Fire icon -->
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z' fill='none'/>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='#7dd3fc' stroke-opacity='0'/>
                </g>

                <!-- Current Streak big number -->
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#e9e9f5' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='animation: currstreak 0.6s linear forwards'>
                        {curr_streak_str}
                    </text>
                </g>

            </g>
            <g style='isolation: isolate'>
                <!-- Longest Streak big number -->
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#e9e9f5' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>
                        {longest_streak_str}
                    </text>
                </g>

                <!-- Longest Streak label -->
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#b9bcd9' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>
                        Longest Streak
                    </text>
                </g>

                <!-- Longest Streak range -->
                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='#8890c0' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>
                        {longest_range_str}
                    </text>
                </g>
            </g>
        </g>
    </svg>
"""


def update_or_write_svg(svg_path, data):
    total_str = f"{data['total']:,}"
    curr_streak_str = str(data["current_streak"])
    longest_streak_str = str(data["longest_streak"])
    curr_range_str = data["current_range"]
    longest_range_str = data["longest_range"]

    if os.path.exists(svg_path):
        with open(svg_path, "r", encoding="utf-8") as f:
            svg = f.read()

        if "<!-- Total Contributions big number -->" in svg:
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
                f"Updated existing {svg_path}: Total={total_str}, Current={curr_streak_str} ({curr_range_str}), Longest={longest_streak_str} ({longest_range_str})"
            )
            return True

    # Otherwise write new SVG from template
    os.makedirs(os.path.dirname(os.path.abspath(svg_path)), exist_ok=True)
    svg_content = generate_svg(data)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(
        f"Generated fresh {svg_path}: Total={total_str}, Current={curr_streak_str} ({curr_range_str}), Longest={longest_streak_str} ({longest_range_str})"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Update GitHub Streak SVG")
    parser.add_argument("--username", required=True, help="GitHub username")
    parser.add_argument("--path", default="profile/streak.svg", help="Path to streak.svg")
    parser.add_argument("--offset", type=int, default=40, help="Offset for total contributions")
    parser.add_argument("--timezone-hours", type=float, default=5.5, help="UTC offset hours (default: 5.5 for IST)")
    args = parser.parse_args()

    print(f"Fetching contribution data for {args.username}...")
    html = fetch_contributions_html(args.username)
    if not html:
        print("Could not fetch HTML contributions", file=sys.stderr)
        sys.exit(1)

    data = calculate_streak_data(html, offset=args.offset, tz_hours=args.timezone_hours)
    if not data:
        print("Failed to calculate streak data from HTML", file=sys.stderr)
        sys.exit(1)

    if not update_or_write_svg(args.path, data):
        sys.exit(1)


if __name__ == "__main__":
    main()
