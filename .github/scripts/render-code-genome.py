"""Turn public repository language bytes into a chromosome and its legend."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import urllib.request


QUERY = """query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, privacy: PUBLIC,
      ownerAffiliations: [OWNER], isFork: false,
      orderBy: {field: NAME, direction: ASC}) {
      nodes {
        nameWithOwner
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          totalSize
          pageInfo { hasNextPage }
          edges { size node { name color } }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

COLORS = ["#d7ff73", "#a4c9bb", "#e7c87a", "#b4a2d8", "#df947b", "#80bcd2", "#789184"]
CHROMOSOME = (
    "M190 175 C180 150 192 128 216 126 C234 124 246 136 252 153 "
    "L284 254 L316 153 C322 136 334 124 352 126 C376 128 388 150 378 175 "
    "L329 323 L378 471 C388 496 376 518 352 520 C334 522 322 510 316 493 "
    "L284 392 L252 493 C246 510 234 522 216 520 C192 518 180 496 190 471 "
    "L239 323Z"
)


def collect_repositories(username):
    repositories = []
    after = None
    while True:
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": QUERY, "variables": {"login": username, "after": after}}).encode(),
            headers={
                "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                "Content-Type": "application/json",
                "User-Agent": "FaisalTabrez-code-genome",
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
        if payload.get("errors") or not payload.get("data", {}).get("user"):
            raise RuntimeError("GitHub language query failed; no genome was written")
        connection = payload["data"]["user"]["repositories"]
        repositories.extend(connection["nodes"])
        if not connection["pageInfo"]["hasNextPage"]:
            return repositories
        after = connection["pageInfo"]["endCursor"]


def summarize(repositories, username):
    totals = Counter()
    for repository in repositories:
        languages = repository["languages"]
        if languages["pageInfo"]["hasNextPage"]:
            raise ValueError("A repository has more than 100 languages; refusing an incomplete genome")
        if sum(edge["size"] for edge in languages["edges"]) != languages["totalSize"]:
            raise ValueError("Incomplete GitHub language byte totals")
        for edge in languages["edges"]:
            totals[edge["node"]["name"]] += edge["size"]
    totals = {name: count for name, count in sorted(totals.items(), key=lambda item: (-item[1], item[0])) if count > 0}
    total_bytes = sum(totals.values())
    if not total_bytes:
        raise ValueError("No language bytes found; no genome was written")
    return {
        "schema_version": 1,
        "username": username,
        "updated_utc": datetime.now(timezone.utc).date().isoformat(),
        "scope": "Public repositories owned by the user, excluding forks; archived repositories included",
        "measure": "GitHub language bytes, summed across repository default branches",
        "repository_count": len(repositories),
        "repositories_with_language_bytes": sum(repo["languages"]["totalSize"] > 0 for repo in repositories),
        "language_count": len(totals),
        "total_bytes": total_bytes,
        "languages": totals,
        "repositories": sorted(repo["nameWithOwner"] for repo in repositories),
    }


def bands_for(data):
    languages = list(data["languages"].items())
    bands = [{"name": name, "bytes": size, "color": COLORS[i]} for i, (name, size) in enumerate(languages[:6])]
    if len(languages) > 6:
        bands.append({"name": f"Other · {len(languages) - 6} languages", "bytes": sum(size for _, size in languages[6:]), "color": COLORS[6]})
    for band in bands:
        band["share"] = band["bytes"] / data["total_bytes"]
    return bands


def label(x, y, text, size=13, anchor="start", color="#b2c6b8"):
    return f'<text x="{x}" y="{y}" font-family="monospace" font-size="{size}" text-anchor="{anchor}" fill="{color}">{html.escape(str(text))}</text>'


def chromosome(bands, transform):
    parts = [f'<g transform="{transform}">', f'<defs><clipPath id="chromosome"><path d="{CHROMOSOME}"/></clipPath></defs>', '<g clip-path="url(#chromosome)">']
    offset = 124.0
    for band in bands:
        height = band["share"] * 398
        parts.append(f'<rect x="170" y="{offset:.5f}" width="220" height="{height:.5f}" fill="{band["color"]}"><title>{html.escape(band["name"])}: {band["share"] * 100:.2f}%</title></rect>')
        offset += height
    # Fine specimen markings are decorative; the color band lengths carry the data.
    for y in range(132, 520, 9):
        parts.append(f'<path d="M176 {y}H391" stroke="#172d25" stroke-opacity=".14" stroke-width="1"/>')
    parts += ['</g>', f'<path d="{CHROMOSOME}" fill="none" stroke="#f3f0e7" stroke-opacity=".35" stroke-width="1.5"/>', '</g>']
    return parts


def render(data, mobile=False):
    width, height = (640, 1120) if mobile else (1200, 660)
    bands = bands_for(data)
    description = "; ".join(f"{band['name']}: {band['share'] * 100:.2f}%" for band in bands)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">The code genome of Faisal Tabrez</title>',
        f'<desc id="desc">Chromosome band lengths encode GitHub language byte shares. {html.escape(description)}. Public, owned, non-fork repository composition.</desc>',
        f'<rect width="{width}" height="{height}" rx="8" fill="#172d25"/>',
        '<g font-family="Arial,sans-serif" fill="#f3f0e7">',
    ]
    if mobile:
        parts += [
            label(32, 35, "THE CODE GENOME / FT—01", 15),
            '<text x="32" y="85" font-size="34" font-weight="700">A fingerprint, written in code.</text>',
            label(32, 119, f"{data['repository_count']} REPOSITORIES / {data['language_count']} LANGUAGES", 15),
            '<path d="M32 143H608" stroke="#b2c6b8" stroke-opacity=".25"/>',
        ]
        parts += chromosome(bands, 'translate(65 71) scale(.9)')
        parts += [label(72, 557, "01 / LANGUAGE BANDS", 14), label(568, 557, "100%", 14, "end")]
        legend_x, legend_y, row_height, right = 33, 586, 57, 607
    else:
        parts += [
            label(42, 38, "THE CODE GENOME / FT—01"),
            label(1158, 38, f"{data['repository_count']} REPOSITORIES / {data['language_count']} LANGUAGES", anchor="end"),
            '<text x="42" y="101" font-size="44" font-weight="700">A fingerprint, written in code.</text>',
            '<path d="M42 132H1158M459 160V550" stroke="#b2c6b8" stroke-opacity=".25"/>',
            label(42, 158, "01 / LANGUAGE BANDS", 12),
        ]
        parts += chromosome(bands, 'translate(-8 55) scale(.9)')
        parts += [label(42, 548, "PUBLIC CODE / ONE SPECIMEN", 12)]
        legend_x, legend_y, row_height, right = 514, 199, 51, 1158
    for index, band in enumerate(bands):
        y = legend_y + index * row_height
        parts += [
            f'<rect x="{legend_x}" y="{y - 16}" width="16" height="16" rx="3" fill="{band["color"]}"/>',
            f'<text x="{legend_x + 31}" y="{y}" font-size="{23 if mobile else 24}">{html.escape(band["name"])}</text>',
            label(right, y, f"{band['share'] * 100:.2f}%", 20, "end", band["color"]),
            f'<path d="M{legend_x} {y + 18}H{right}" stroke="#b2c6b8" stroke-opacity=".15"/>',
        ]
    # An unbroken linear track makes even small byte shares visible at full size.
    track_y, track_x, track_width = (1014, 32, 576) if mobile else (582, 42, 1116)
    parts.append(f'<defs><clipPath id="track"><rect x="{track_x}" y="{track_y}" width="{track_width}" height="12" rx="6"/></clipPath></defs><g clip-path="url(#track)">')
    cursor = float(track_x)
    for band in bands:
        band_width = track_width * band["share"]
        parts.append(f'<rect x="{cursor:.5f}" y="{track_y}" width="{band_width:.5f}" height="12" fill="{band["color"]}"/>')
        cursor += band_width
    parts.append('</g>')
    if mobile:
        parts += [label(32, 1064, "BAND LENGTH = SHARE OF LANGUAGE BYTES", 14),
                  label(32, 1095, f"PUBLIC / OWNED / NON-FORK · {data['updated_utc']}", 13)]
    else:
        parts += [label(42, 626, "BAND LENGTH = SHARE OF LANGUAGE BYTES · PUBLIC / OWNED / NON-FORK", 12),
                  label(1158, 626, data["updated_utc"], 12, "end")]
    return "\n".join(parts + ['</g>', '</svg>\n'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="FaisalTabrez")
    parser.add_argument("--input", help="A saved, complete repository GraphQL page for local rendering")
    parser.add_argument("--output", default="assets/generated")
    args = parser.parse_args()
    if args.input:
        connection = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))["data"]["user"]["repositories"]
        if connection["pageInfo"]["hasNextPage"]:
            raise ValueError("The saved repository page is incomplete")
        repositories = connection["nodes"]
    else:
        repositories = collect_repositories(args.username)
    data = summarize(repositories, args.username)
    documents = {
        "code-genome.svg": render(data),
        "code-genome-mobile.svg": render(data, mobile=True),
        "code-genome.json": json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    }
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in documents.items():
        (output / filename).write_text(content, encoding="utf-8")
        print(f"Generated {output / filename}")


if __name__ == "__main__":
    main()
