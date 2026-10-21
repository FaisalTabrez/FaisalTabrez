"""Render profile artwork from GitHub's contribution calendar, using only stdlib."""

import argparse
import html
import json
import math
import os
from pathlib import Path
import urllib.request


def load_calendar(username, input_path):
    if input_path:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8-sig"))
    else:
        query = """query($login: String!) {
          user(login: $login) { contributionsCollection {
            contributionCalendar { totalContributions weeks {
              contributionDays { date contributionCount contributionLevel }
            } }
          } }
        }"""
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"login": username}}).encode(),
            headers={
                "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                "Content-Type": "application/json",
                "User-Agent": "FaisalTabrez-profile-artwork",
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub contribution query failed")
    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    if not calendar["weeks"]:
        raise ValueError("GitHub returned an empty calendar")
    return calendar


def canvas(height, title, description):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" '
        f'viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        f'<rect width="1200" height="{height}" rx="8" fill="#172d25"/>',
        '<style>text{font-family:Arial,sans-serif;fill:#f3f0e7}.label{'
        'font-family:monospace;font-size:13px;letter-spacing:1.5px;fill:#b2c6b8}</style>',
    ]


def activity(calendar):
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]][-31:]
    total = sum(day["contributionCount"] for day in days)
    peak = max(day["contributionCount"] for day in days)
    ceiling = max(4, math.ceil(peak / 4) * 4)
    svg = canvas(350, "The activity signal", f"{total} GitHub contributions over the last {len(days)} days.")
    svg += [
        '<text x="42" y="38" class="label">THE ACTIVITY SIGNAL / DAILY CONTRIBUTIONS</text>',
        f'<text x="1158" y="38" text-anchor="end" class="label">{total:,} IN {len(days)} DAYS</text>',
    ]
    for tick in range(5):
        y = 85 + tick * 48
        svg += [
            f'<path d="M82 {y}H1158" stroke="#b2c6b8" stroke-opacity=".15"/>',
            f'<text x="63" y="{y + 5}" text-anchor="end" class="label">{ceiling * (4 - tick) // 4}</text>',
        ]
    points = [(82 + i * 1076 / max(1, len(days) - 1), 277 - day["contributionCount"] * 192 / ceiling)
              for i, day in enumerate(days)]
    coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    svg += [
        f'<polygon points="82,277 {coordinates} 1158,277" fill="#d7ff73" opacity=".12"/>',
        f'<polyline points="{coordinates}" fill="none" stroke="#d7ff73" stroke-width="3" stroke-linejoin="round"/>',
    ]
    for (x, y), day in zip(points, days):
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#d54b32">'
                   f'<title>{day["date"]}: {day["contributionCount"]} contributions</title></circle>')
    for index in sorted({0, len(days) // 2, len(days) - 1}):
        x = points[index][0]
        anchor = "start" if index == 0 else "end" if index == len(days) - 1 else "middle"
        svg.append(f'<text x="{x:.1f}" y="310" text-anchor="{anchor}" class="label">{days[index]["date"]}</text>')
    return "\n".join(svg + ["</svg>\n"])


def landscape(calendar):
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    peak = max(day["contributionCount"] for day in days)
    svg = canvas(540, "A year in three dimensions", "One column per day. Column height is proportional to the GitHub contribution count.")
    svg += [
        '<text x="42" y="38" class="label">CONTRIBUTION TOPOGRAPHY / ONE COLUMN PER DAY</text>',
        f'<text x="42" y="81" font-size="28" font-weight="700">{calendar["totalContributions"]:,} contributions. A year of building.</text>',
        '<path d="M42 107H1158" stroke="#b2c6b8" stroke-opacity=".2"/>',
    ]
    colors = {"NONE": "#294238", "FIRST_QUARTILE": "#537c4d", "SECOND_QUARTILE": "#84af59",
              "THIRD_QUARTILE": "#b2d76b", "FOURTH_QUARTILE": "#d7ff73"}
    columns = []
    step = 960 / max(1, len(calendar["weeks"]) - 1)
    for week_index, week in enumerate(calendar["weeks"]):
        for day_index, day in enumerate(week["contributionDays"]):
            x = 65 + week_index * step + day_index * 14
            y = 300 + week_index * 2.6 - day_index * 11
            height = 1 + day["contributionCount"] * 100 / max(1, peak)
            columns.append((y, x, height, day))
    for y, x, height, day in sorted(columns, key=lambda column: column[0]):
        top = y - height
        color = colors[day["contributionLevel"]]
        svg += [
            f'<g><title>{day["date"]}: {day["contributionCount"]} contributions</title>',
            f'<path d="M{x:.1f},{top:.1f}l8,4v{height:.1f}l-8,-4Z" fill="{color}" opacity=".45"/>',
            f'<path d="M{x + 8:.1f},{top + 4:.1f}l8,-4v{height:.1f}l-8,4Z" fill="{color}" opacity=".7"/>',
            f'<path d="M{x:.1f},{top:.1f}l8,-4l8,4l-8,4Z" fill="{color}" stroke="#172d25" stroke-width=".5"/></g>',
        ]
    svg += [
        '<path d="M42 477H1158" stroke="#b2c6b8" stroke-opacity=".2"/>',
        f'<text x="42" y="512" class="label">{days[0]["date"]} → {days[-1]["date"]}</text>',
        f'<text x="1158" y="512" text-anchor="end" class="label">PEAK {peak} / DAY · LINEAR HEIGHT</text>',
    ]
    return "\n".join(svg + ["</svg>\n"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="FaisalTabrez")
    parser.add_argument("--input", help="Use a saved GitHub GraphQL response for a local render")
    parser.add_argument("--output", default="assets/generated")
    args = parser.parse_args()
    calendar = load_calendar(args.username, args.input)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for filename, render in [("activity.svg", activity), ("contributions-3d.svg", landscape)]:
        (output / filename).write_text(render(calendar), encoding="utf-8")
        print(f"Generated {output / filename}")


if __name__ == "__main__":
    main()
