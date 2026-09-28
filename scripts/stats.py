#!/usr/bin/env python3
"""Render the profile README images from the GitHub GraphQL API.

Outputs (dark + light variant of each):
  header-{dark,light}.svg  animated name + typing roles
  stats-{dark,light}.svg   this-year numbers: contributions, commits, streaks, languages
  graph-{dark,light}.svg   daily contributions this year with a 7-day average line

Standard library only. Run:  python3 scripts/stats.py --user sairam782 --out dist
Needs GITHUB_TOKEN (the Actions token is enough for public data).
Use --demo to render with fake data for a local preview.
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import urllib.request
from html import escape

# ---------------------------------------------------------------- config

NAME = "Abhishek Sairam Gaduputi"
ROLES = [
    "ML Engineer · Computer Vision · GenAI",
    "Building multi-agent systems that ship",
    "Diffusion models, synthetic MRI, deepfake defense",
    "MS in AI @ NJIT · class of 2027",
    "Open to 2027 ML / Applied Scientist roles",
]
SKIP_LANGS = {"Jupyter Notebook", "HTML", "CSS", "SCSS"}  # notebook outputs and markup inflate byte counts

THEMES = {
    "dark": dict(
        bg="#161b22", tile="#0d1117", border="#30363d", text="#e6edf3", muted="#8b949e",
        grid="#21262d",
        accents=["#7aa2f7", "#bb9af7", "#7dcfff", "#9ece6a", "#ff9e64", "#f7768e"],
        grad=["#7aa2f7", "#bb9af7", "#7dcfff"],
    ),
    "light": dict(
        bg="#f6f8fa", tile="#ffffff", border="#d0d7de", text="#1f2328", muted="#59636e",
        grid="#e5e8eb",
        accents=["#2e59c9", "#7a4ec2", "#0b7fa8", "#3f7d1c", "#c75b14", "#c42b4a"],
        grad=["#2e59c9", "#7a4ec2", "#0b7fa8"],
    ),
}

SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
W = 860

# ---------------------------------------------------------------- data

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch(user, token, now):
    start = dt.datetime(now.year, 1, 1, tzinfo=dt.timezone.utc)
    body = json.dumps({"query": QUERY, "variables": {
        "login": user, "from": start.isoformat(), "to": now.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "profile-stats"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors"):
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def demo_data(now):
    rnd = random.Random(7)
    d, days = dt.date(now.year, 1, 1), []
    while d <= now.date():
        heat = 0.25 + 0.75 * (d.timetuple().tm_yday / 366) ** 2
        c = rnd.choice([0, 0, 0, 1, 2, 3, 5, 8]) if rnd.random() < heat else 0
        days.append({"date": d.isoformat(), "contributionCount": c})
        d += dt.timedelta(days=1)
    return {
        "contributionsCollection": {
            "totalCommitContributions": 412, "totalPullRequestContributions": 38,
            "totalIssueContributions": 6, "totalPullRequestReviewContributions": 3,
            "totalRepositoriesWithContributedCommits": 17, "restrictedContributionsCount": 0,
            "contributionCalendar": {"totalContributions": sum(x["contributionCount"] for x in days),
                                     "weeks": [{"contributionDays": days}]},
        },
        "repositories": {"nodes": [{"languages": {"edges": [
            {"size": 900_000, "node": {"name": "Python", "color": "#3572A5"}},
            {"size": 520_000, "node": {"name": "JavaScript", "color": "#f1e05a"}},
            {"size": 210_000, "node": {"name": "TypeScript", "color": "#3178c6"}},
            {"size": 60_000, "node": {"name": "HTML", "color": "#e34c26"}},
            {"size": 40_000, "node": {"name": "CSS", "color": "#663399"}},
            {"size": 9_000, "node": {"name": "Shell", "color": "#89e051"}},
            {"size": 5_000, "node": {"name": "C++", "color": "#f34b7d"}},
        ]}}]},
    }


def summarize(user, now):
    cc = user["contributionsCollection"]
    today = now.date()
    days = []
    for w in cc["contributionCalendar"]["weeks"]:
        for x in w["contributionDays"]:
            d = dt.date.fromisoformat(x["date"])
            if d.year == today.year and d <= today:
                days.append((d, x["contributionCount"]))
    days.sort()
    counts = [c for _, c in days]

    # current streak: a zero today does not break it yet
    i = len(days) - 1
    if i >= 0 and counts[i] == 0:
        i -= 1
    cur, cur_start = 0, None
    while i >= 0 and counts[i] > 0:
        cur, cur_start, i = cur + 1, days[i][0], i - 1

    best, best_range, run, run_start = 0, None, 0, None
    for d, c in days:
        if c > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > best:
                best, best_range = run, (run_start, d)
        else:
            run = 0

    peak_day, peak = max(days, key=lambda t: (t[1], t[0])) if days else (today, 0)
    months = {}
    for d, c in days:
        months[d.month] = months.get(d.month, 0) + c
    best_month = max(months, key=months.get) if months else today.month

    langs = {}
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in SKIP_LANGS:
                continue
            langs[n] = langs.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#8b949e"
    total_bytes = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda t: -t[1])[:6]
    other = total_bytes - sum(s for _, s in top)
    lang_list = [(n, s / total_bytes, colors[n]) for n, s in top]
    if other / total_bytes > 0.005:
        lang_list.append(("Other", other / total_bytes, "#6e7681"))

    active = sum(1 for c in counts if c > 0)
    total = sum(counts)
    return dict(
        year=today.year, today=today, days=days, total=total,
        private=cc["restrictedContributionsCount"],
        commits=cc["totalCommitContributions"], prs=cc["totalPullRequestContributions"],
        issues=cc["totalIssueContributions"], reviews=cc["totalPullRequestReviewContributions"],
        repos=cc["totalRepositoriesWithContributedCommits"],
        active=active, n_days=len(days), cur=cur, cur_start=cur_start,
        best=best, best_range=best_range, peak=peak, peak_day=peak_day,
        best_month=best_month, best_month_total=months.get(best_month, 0),
        avg_active=(total / active) if active else 0, langs=lang_list,
    )


# ---------------------------------------------------------------- helpers

def fmt_day(d):
    return f"{d:%b} {d.day}"


def fmt_int(n):
    return f"{n:,}"


def svg_open(h, title, extra_css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title><style>{extra_css}</style>")


def card(t, h):
    return (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="12" '
            f'fill="{t["bg"]}" stroke="{t["border"]}"/>')


# ---------------------------------------------------------------- header

def header_svg(t):
    h, cw, fs = 132, 12.0, 20
    slot, type_t, hold, erase = 3.6, 1.2, 1.8, 0.45
    total = slot * len(ROLES)
    out = [svg_open(h, f"{NAME}: " + "; ".join(ROLES), f"""
      .name {{ font: 700 38px {SANS}; letter-spacing: .5px; }}
      .role {{ font: 500 {fs}px {MONO}; fill: {t['text']}; }}
      .cur  {{ animation: blink 1s steps(1) infinite; }}
      @keyframes blink {{ 50% {{ opacity: 0; }} }}
      .fade {{ animation: rise .9s ease-out both; }}
      @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: none; }} }}
    """)]
    g = t["grad"]
    out.append(f"""<defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{g[0]}"><animate attributeName="stop-color" values="{g[0]};{g[1]};{g[2]};{g[0]}" dur="8s" repeatCount="indefinite"/></stop>
      <stop offset="1" stop-color="{g[2]}"><animate attributeName="stop-color" values="{g[2]};{g[0]};{g[1]};{g[2]}" dur="8s" repeatCount="indefinite"/></stop>
    </linearGradient></defs>""")
    out.append(f'<text class="name" x="{W / 2}" y="54" text-anchor="middle" fill="url(#g)">{escape(NAME)}</text>')

    # The timeline is shifted so frame 0 shows the first role fully typed.
    # Renderers that freeze animations (reduced motion, previews) still get a complete header.
    y = 98
    cursor = []
    for i, role in enumerate(ROLES):
        n = len(role)
        x0 = (W - n * cw) / 2
        s = i * slot
        # discrete key frames: type char by char, hold, erase char by char
        frames = [(0.0, 0)]
        for k in range(n + 1):
            frames.append((s + type_t * k / n, k))
        frames.append((s + type_t + hold, n))
        for k in range(n, -1, -1):
            frames.append((s + type_t + hold + erase * (n - k) / n, k))
        frames = shift(frames, type_t, total)
        widths = ";".join(f"{k * cw:.1f}" for _, k in frames)
        times = ";".join(f"{tt / total:.5f}" for tt, _ in frames)
        start_w = n * cw if i == 0 else 0
        out.append(f'<clipPath id="c{i}"><rect x="{x0:.1f}" y="{y - 24}" height="34" width="{start_w:.1f}">'
                   f'<animate attributeName="width" values="{widths}" keyTimes="{times}" '
                   f'dur="{total}s" calcMode="discrete" repeatCount="indefinite"/></rect></clipPath>')
        out.append(f'<text class="role" x="{x0:.1f}" y="{y}" clip-path="url(#c{i})">{escape(role)}</text>')
        cursor += [((tt + type_t) % total, x0 + k * cw + 2) for tt, k in frames
                   if s <= (tt + type_t) % total < s + slot]
    pairs = shift(cursor, type_t, total)
    out.append(f'<rect class="cur" x="{pairs[0][1]:.1f}" y="{y - 19}" width="3" height="24" rx="1" fill="{g[1]}">'
               f'<animate attributeName="x" values="{";".join(f"{v:.1f}" for _, v in pairs)}" '
               f'keyTimes="{";".join(f"{tt / total:.5f}" for tt, _ in pairs)}" dur="{total}s" '
               f'calcMode="discrete" repeatCount="indefinite"/></rect>')
    out.append("</svg>")
    return "".join(out)


def shift(frames, by, total):
    """Move a piecewise-constant timeline earlier by `by` seconds, wrapping around the cycle."""
    frames = dedupe(frames, total)
    at = [v for tt, v in frames if tt <= by + 1e-9][-1]
    moved = [((tt - by) % total, v) for tt, v in frames]
    return dedupe([(0.0, at)] + [f for f in moved if f[0] > 0], total)


def dedupe(frames, total):
    """Keep key times strictly increasing and inside [0, 1)."""
    out, last = [], -1.0
    for tt, v in sorted(frames, key=lambda f: f[0]):
        tt = round(tt, 4)
        if tt >= total:
            continue
        if tt <= last:
            out[-1] = (out[-1][0], v)
            continue
        out.append((tt, v))
        last = tt
    return out


# ---------------------------------------------------------------- stats card

def stats_svg(s, t):
    h = 262
    a = t["accents"]
    tiles = [
        (fmt_int(s["total"]), "Contributions",
         f"incl. {fmt_int(s['private'])} private" if s["private"] else f"{s['avg_active']:.1f} per active day"),
        (fmt_int(s["commits"]), "Commits", f"across {s['repos']} repos"),
        (fmt_int(s["prs"]), "Pull requests", f"{s['issues']} issues · {s['reviews']} reviews"),
        (fmt_int(s["active"]), "Active days",
         f"of {s['n_days']} ({100 * s['active'] / max(1, s['n_days']):.0f}%)"),
        (f"{s['cur']}", "Current streak",
         f"since {fmt_day(s['cur_start'])}" if s["cur"] else "starts with a commit"),
        (f"{s['best']}", "Longest streak",
         f"{fmt_day(s['best_range'][0])} to {fmt_day(s['best_range'][1])}" if s["best_range"] else "no streak yet"),
    ]
    css = f"""
      .h {{ font: 700 17px {SANS}; fill: {t['text']}; }}
      .sub {{ font: 400 12.5px {SANS}; fill: {t['muted']}; }}
      .num {{ font: 700 30px {SANS}; }}
      .lab {{ font: 600 12.5px {SANS}; fill: {t['text']}; }}
      .sm {{ font: 400 11px {SANS}; fill: {t['muted']}; }}
      .hl {{ font: 400 12.5px {SANS}; fill: {t['muted']}; }}
      .hl tspan.b {{ fill: {t['text']}; font-weight: 600; }}
      .lg {{ font: 400 11.5px {SANS}; fill: {t['muted']}; }}
      .shine {{ animation: sweep 5s ease-in-out infinite; }}
      @keyframes sweep {{ from {{ transform: translateX(-160px); }} to {{ transform: translateX({W}px); }} }}
      .dot {{ animation: pulse 2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
      @keyframes pulse {{ 50% {{ opacity: .35; }} }}
    """
    out = [svg_open(h, f"{s['year']} on GitHub: {s['total']} contributions, {s['commits']} commits", css),
           card(t, h)]
    out.append('<defs><linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
               '<stop offset=".5" stop-color="#fff" stop-opacity=".45"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
               '</linearGradient></defs>')
    out.append(f'<text class="h" x="24" y="36">{s["year"]} on GitHub</text>')
    out.append(f'<text class="sub" x="{W - 24}" y="36" text-anchor="end">'
               f'Jan 1 to {fmt_day(s["today"])} · refreshed daily</text>')

    pad, gap, top, th = 24, 12, 54, 96
    tw = (W - 2 * pad - 5 * gap) / 6
    for i, (num, lab, sub) in enumerate(tiles):
        x = pad + i * (tw + gap)
        out.append(f'<g>'
                   f'<rect x="{x:.1f}" y="{top}" width="{tw:.1f}" height="{th}" rx="9" fill="{t["tile"]}" stroke="{t["border"]}"/>'
                   f'<rect x="{x + 14:.1f}" y="{top + 14}" width="18" height="3" rx="1.5" fill="{a[i]}"/>'
                   f'<text class="num" x="{x + 14:.1f}" y="{top + 50}" fill="{a[i]}">{escape(num)}</text>'
                   f'<text class="lab" x="{x + 14:.1f}" y="{top + 69}">{escape(lab)}</text>'
                   f'<text class="sm" x="{x + 14:.1f}" y="{top + 85}">{escape(sub)}</text></g>')

    y = top + th + 30
    month = dt.date(2000, s["best_month"], 1).strftime("%B")
    out.append(f'<text class="hl" x="24" y="{y}">Busiest day <tspan class="b">{fmt_day(s["peak_day"])}</tspan> '
               f'({s["peak"]}) <tspan dx="10">·</tspan><tspan dx="10">Best month</tspan> '
               f'<tspan class="b">{month}</tspan> ({fmt_int(s["best_month_total"])}) '
               f'<tspan dx="10">·</tspan><tspan dx="10">Avg</tspan> <tspan class="b">{s["avg_active"]:.1f}</tspan> '
               f'per active day</text>')

    # languages
    y += 22
    out.append(f'<text class="hl" x="24" y="{y}">Top languages in public repos</text>')
    y += 12
    bw = W - 48
    out.append(f'<clipPath id="lb"><rect x="24" y="{y}" width="{bw}" height="10" rx="5"/></clipPath>'
               f'<g clip-path="url(#lb)"><g>')
    x = 24.0
    for name, frac, col in s["langs"]:
        w = frac * bw
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{w + 0.6:.1f}" height="10" fill="{col}"/>')
        x += w
    out.append(f'<rect class="shine" x="0" y="{y}" width="120" height="10" fill="url(#sh)"/></g></g>')
    y += 30
    x = 24.0
    for name, frac, col in s["langs"]:
        label = f"{name} {frac * 100:.0f}%" if frac >= 0.01 else f"{name} <1%"
        out.append(f'<circle cx="{x + 5:.1f}" cy="{y - 4}" r="5" fill="{col}"/>'
                   f'<text class="lg" x="{x + 15:.1f}" y="{y}">{escape(label)}</text>')
        x += 15 + 6.4 * len(label) + 22
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- graph

def nice_max(v):
    if v <= 4:
        return 4
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= v:
            return m * mag
    return 10 * mag


def graph_svg(s, t):
    h = 300
    a = t["accents"]
    days = s["days"]
    counts = [c for _, c in days]
    n = len(days)
    avg = []
    for i in range(n):
        win = counts[max(0, i - 6): i + 1]
        avg.append(sum(win) / len(win))
    L, R, T, B = 48, 24, 64, h - 42
    pw, ph = W - L - R, B - T
    ymax = nice_max(max(counts + [1]))
    step = pw / max(1, n)
    X = lambda i: L + step * (i + 0.5)
    Y = lambda v: B - ph * min(v, ymax) / ymax

    css = f"""
      .h {{ font: 700 17px {SANS}; fill: {t['text']}; }}
      .ax {{ font: 400 11px {SANS}; fill: {t['muted']}; }}
      .lg {{ font: 400 12px {SANS}; fill: {t['muted']}; }}
      .pk {{ font: 600 11.5px {SANS}; fill: {t['text']}; }}
      .ring {{ animation: ring 2.2s ease-out infinite; transform-box: fill-box; transform-origin: center; }}
      @keyframes ring {{ from {{ transform: scale(1); opacity: .9; }} to {{ transform: scale(3.2); opacity: 0; }} }}
    """
    out = [svg_open(h, f"Daily contributions in {s['year']}", css), card(t, h)]
    out.append(f'<defs><linearGradient id="ar" x1="0" x2="0" y1="0" y2="1">'
               f'<stop offset="0" stop-color="{a[1]}" stop-opacity=".35"/>'
               f'<stop offset="1" stop-color="{a[1]}" stop-opacity="0"/></linearGradient></defs>')
    out.append(f'<text class="h" x="24" y="36">Daily contributions in {s["year"]}</text>')
    lx = W - 24
    out.append(f'<g transform="translate({lx - 205},0)">'
               f'<rect x="0" y="27" width="10" height="10" rx="2" fill="{a[0]}" opacity=".6"/>'
               f'<text class="lg" x="16" y="36">each day</text>'
               f'<rect x="92" y="31" width="18" height="3" rx="1.5" fill="{a[1]}"/>'
               f'<text class="lg" x="116" y="36">7-day average</text></g>')

    for k in range(5):
        v = ymax * k / 4
        yy = Y(v)
        dash = "" if k == 0 else ' stroke-dasharray="3 4"'
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{t["grid"]}"{dash}/>')
        lab = f"{v:g}" if v == int(v) else f"{v:.1f}"
        out.append(f'<text class="ax" x="{L - 10}" y="{yy + 4:.1f}" text-anchor="end">{lab}</text>')

    for i, (d, _) in enumerate(days):
        if d.day == 1:
            out.append(f'<line x1="{X(i) - step / 2:.1f}" x2="{X(i) - step / 2:.1f}" y1="{B}" y2="{B + 5}" stroke="{t["border"]}"/>')
            out.append(f'<text class="ax" x="{X(i) - step / 2 + 4:.1f}" y="{B + 20}">{d:%b}</text>')

    bw = max(1.2, step * 0.72)
    out.append('<g class="bars">')
    for i, c in enumerate(counts):
        if c:
            out.append(f'<rect x="{X(i) - bw / 2:.2f}" y="{Y(c):.1f}" width="{bw:.2f}" '
                       f'height="{B - Y(c):.1f}" rx="{min(1.5, bw / 2):.2f}" fill="{a[0]}" opacity=".55"/>')
    out.append("</g>")

    if n:
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(avg))
        out.append(f'<polygon class="area" points="{X(0):.1f},{B} {pts} {X(n - 1):.1f},{B}" fill="url(#ar)"/>')
        out.append(f'<polyline class="line" points="{pts}" fill="none" stroke="{a[1]}" '
                   f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
        pi = next(i for i, (d, _) in enumerate(days) if d == s["peak_day"])
        px, py = X(pi), Y(s["peak"])
        label = f"Peak: {s['peak']} on {fmt_day(s['peak_day'])}"
        tx = min(max(px, L + 70), W - R - 70)
        out.append(f'<g><circle class="ring" cx="{px:.1f}" cy="{py:.1f}" r="4" fill="none" stroke="{a[4]}" stroke-width="1.5"/>'
                   f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{a[4]}" stroke="{t["bg"]}" stroke-width="2"/>'
                   f'<text class="pk" x="{tx:.1f}" y="{max(py - 10, T - 8):.1f}" text-anchor="middle">{escape(label)}</text></g>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "sairam782"))
    ap.add_argument("--out", default="dist")
    ap.add_argument("--demo", action="store_true", help="fake data, no network")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    if args.demo:
        user = demo_data(now)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        user = fetch(args.user, token, now)
    s = summarize(user, now)

    os.makedirs(args.out, exist_ok=True)
    for mode, t in THEMES.items():
        for name, svg in (("header", header_svg(t)), ("stats", stats_svg(s, t)), ("graph", graph_svg(s, t))):
            with open(os.path.join(args.out, f"{name}-{mode}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
    print(f"{s['year']}: {s['total']} contributions, {s['commits']} commits, "
          f"{s['active']} active days, streak {s['cur']} (best {s['best']})")


if __name__ == "__main__":
    main()
