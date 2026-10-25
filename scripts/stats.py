import json
import os
import urllib.request
from datetime import date, datetime, timedelta
from html import escape

USER = os.environ.get("GH_USER", "ahmedmosthalim")
TOKEN = os.environ["GH_TOKEN"]
OUT = os.environ.get("OUT_DIR", "assets")

BG, TITLE, TEXT, MUTED, ICON, RING = "#1a1b27", "#70a5fd", "#c0caf5", "#9aa5ce", "#bf91f3", "#7aa2f7"
FONT = "font-family:'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif"


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if body.get("errors"):
        raise SystemExit(body["errors"])
    return body["data"]


def fetch():
    profile = gql(
        """query($login:String!){user(login:$login){name createdAt
        followers{totalCount}
        pullRequests{totalCount}
        issues{totalCount}
        repositories(ownerAffiliations:OWNER,isFork:false,first:100){totalCount nodes{stargazerCount
          languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}""",
        {"login": USER},
    )["user"]
    commits, total, days = 0, 0, {}
    start = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00")).year
    for year in range(start, date.today().year + 1):
        c = gql(
            """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
            contributionsCollection(from:$from,to:$to){totalCommitContributions restrictedContributionsCount
            contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}""",
            {"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        total += c["contributionCalendar"]["totalContributions"]
        for week in c["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return profile, commits, total, days


def streaks(days):
    today = date.today()
    longest = run = 0
    longest_range = (None, None)
    run_start = None
    for key in sorted(days):
        d = date.fromisoformat(key)
        if d > today:
            break
        if days[key] > 0:
            run_start = run_start or d
            run += 1
            if run > longest:
                longest, longest_range = run, (run_start, d)
        else:
            run, run_start = 0, None
    current, d = 0, today
    if days.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    end = d
    while days.get(d.isoformat(), 0) > 0:
        current += 1
        d -= timedelta(days=1)
    return current, (d + timedelta(days=1), end), longest, longest_range


def fmt(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def span(r):
    a, b = r
    if not a:
        return "—"
    f = lambda x: x.strftime("%b %-d, %Y") if x.year != date.today().year else x.strftime("%b %-d")
    return f(a) if a == b else f"{f(a)} – {f(b)}"


def card(w, h, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<style>.t{{{FONT};font-weight:600;font-size:18px;fill:{TITLE}}}.s{{{FONT};font-size:14px;fill:{TEXT}}}.m{{{FONT};font-size:12px;fill:{MUTED}}}.b{{{FONT};font-weight:700;fill:{TEXT}}}</style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>
<text x="25" y="35" class="t">{escape(title)}</text>
{body}
</svg>
"""


def stats_svg(profile, commits, total):
    repos = profile["repositories"]
    stars = sum(r["stargazerCount"] for r in repos["nodes"])
    rows = [
        ("★", "Total stars", stars),
        ("⬤", "Total commits", commits),
        ("⇄", "Pull requests", profile["pullRequests"]["totalCount"]),
        ("!", "Issues", profile["issues"]["totalCount"]),
        ("▣", "Repositories", repos["totalCount"]),
        ("♥", "Followers", profile["followers"]["totalCount"]),
    ]
    body = "".join(
        f'<text x="25" y="{70 + i * 25}" class="s"><tspan fill="{ICON}">{icon}</tspan>  {label}:</text>'
        f'<text x="230" y="{70 + i * 25}" class="b" font-size="14">{fmt(value)}</text>'
        for i, (icon, label, value) in enumerate(rows)
    )
    body += (
        f'<circle cx="380" cy="115" r="48" fill="none" stroke="{RING}" stroke-opacity=".25" stroke-width="7"/>'
        f'<circle cx="380" cy="115" r="48" fill="none" stroke="{RING}" stroke-width="7" stroke-linecap="round" '
        f'stroke-dasharray="301.6" stroke-dashoffset="{301.6 * (1 - min(total, 2000) / 2000):.1f}" transform="rotate(-90 380 115)"/>'
        f'<text x="380" y="113" text-anchor="middle" class="b" font-size="22">{fmt(total)}</text>'
        f'<text x="380" y="132" text-anchor="middle" class="m">contributions</text>'
    )
    return card(467, 225, f"{profile['name'] or USER}'s GitHub Stats", body)


def streak_svg(total, first_day, days):
    current, current_range, longest, longest_range = streaks(days)
    cols = [
        (82, fmt(total), "Total contributions", f"{span((first_day, date.today()))}"),
        (247, str(current), "Current streak", span(current_range) if current else "Start one today"),
        (412, str(longest), "Longest streak", span(longest_range)),
    ]
    body = f'<line x1="165" y1="60" x2="165" y2="190" stroke="{MUTED}" stroke-opacity=".3"/><line x1="330" y1="60" x2="330" y2="190" stroke="{MUTED}" stroke-opacity=".3"/>'
    for x, value, label, sub in cols:
        color = TITLE if label == "Current streak" else TEXT
        body += (
            f'<text x="{x}" y="112" text-anchor="middle" class="b" font-size="28" fill="{color}">{value}</text>'
            f'<text x="{x}" y="145" text-anchor="middle" class="s" fill="{color}">{label}</text>'
            f'<text x="{x}" y="168" text-anchor="middle" class="m">{escape(sub)}</text>'
        )
    return card(495, 225, "Contribution streak", body)


def langs_svg(profile):
    sizes, colors = {}, {}
    for repo in profile["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or MUTED
    everything = sum(sizes.values()) or 1
    top = [kv for kv in sorted(sizes.items(), key=lambda kv: -kv[1]) if kv[1] / everything >= 0.005][:8]
    whole = sum(v for _, v in top) or 1
    bar, x = "", 25.0
    for name, size in top:
        width = 300 * size / whole
        bar += f'<rect x="{x:.2f}" y="55" width="{width:.2f}" height="8" fill="{colors[name]}"/>'
        x += width
    bar = f'<mask id="r"><rect x="25" y="55" width="300" height="8" rx="4" fill="#fff"/></mask><g mask="url(#r)">{bar}</g>'
    items = "".join(
        f'<circle cx="{30 + (i % 2) * 150}" cy="{86 + (i // 2) * 25}" r="5" fill="{colors[name]}"/>'
        f'<text x="{42 + (i % 2) * 150}" y="{91 + (i // 2) * 25}" class="s">{escape(name)} <tspan class="m">{100 * size / whole:.1f}%</tspan></text>'
        for i, (name, size) in enumerate(top)
    )
    return card(350, 90 + 25 * ((len(top) + 1) // 2), "Most used languages", bar + items)


def main():
    profile, commits, total, days = fetch()
    first_day = date.fromisoformat(min(days)) if days else date.today()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in [
        ("stats.svg", stats_svg(profile, commits, total)),
        ("streak.svg", streak_svg(total, first_day, days)),
        ("languages.svg", langs_svg(profile)),
    ]:
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg)
    print(f"commits={commits} contributions={total} days={len(days)}")


if __name__ == "__main__":
    main()
