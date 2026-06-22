#!/usr/bin/env python3
"""
2026 FIFA World Cup Fantasy League scorer.
Fetches results from ESPN's API and outputs an HTML standings table.
"""

import sys
import requests
from datetime import datetime
from collections import defaultdict

# ── Player → Teams mapping ────────────────────────────────────────────────────
PLAYERS = {
    "Louis":        ["Brazil", "Scotland", "Norway", "Curacao"],
    "Chip":         ["Argentina", "Japan", "Cabo Verde", "Jordan"],
    "Beefs":        ["France", "Haiti", "Qatar", "New Zealand"],
    "JD":           ["Spain", "Canada", "Ghana", "South Africa"],
    "Johnny Jacobs":["Germany", "Australia", "Senegal", "Paraguay"],
    "Lux":          ["Austria", "Sweden", "Saudi Arabia", "Tunisia"],
    "MW":           ["Portugal", "Morocco", "Bosnia & Herzegovina", "Iran"],
    "Wally":        ["Netherlands", "Colombia", "Turkey", "Algeria"],
    "Schnipper":    ["Belgium", "Switzerland", "Egypt", "Ivory Coast"],
    "Spiff":        ["Uruguay", "England", "Czechia", "Republic of Korea"],
    "Wardy":        ["Croatia", "USA", "Mexico", "Ecuador"],
    "Boy":          ["Uruguay", "Iraq", "Congo", "Uzbekistan"],
}

# ESPN team display names → our canonical names
TEAM_ALIASES = {
    "United States":                    "USA",
    "United States of America":         "USA",
    "US":                               "USA",
    "South Korea":                      "Republic of Korea",
    "Korea Republic":                   "Republic of Korea",
    "Korea DPR":                        "Republic of Korea",
    "Cape Verde":                       "Cabo Verde",
    "Cape Verde Islands":               "Cabo Verde",
    "Ivory Coast":                      "Ivory Coast",
    "Côte d'Ivoire":                    "Ivory Coast",
    "Cote d'Ivoire":                    "Ivory Coast",
    "Côte D'Ivoire":                    "Ivory Coast",
    "Bosnia and Herzegovina":           "Bosnia & Herzegovina",
    "Bosnia-Herzegovina":               "Bosnia & Herzegovina",
    "Bosnia & Herzegowina":             "Bosnia & Herzegovina",
    "Czech Republic":                   "Czechia",
    "DR Congo":                         "Congo",
    "Congo DR":                         "Congo",
    "Congo, DR":                        "Congo",
    "Democratic Republic of Congo":     "Congo",
    "Democratic Republic of the Congo": "Congo",
    "Republic of Congo":                "Congo",
    "Curaçao":                          "Curacao",
    "Türkiye":                          "Turkey",
    "New Zealand":                      "New Zealand",
    "Norway":                           "Norway",
}


def normalize_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)


# ── Fetch from ESPN ────────────────────────────────────────────────────────────
WC_START = "20260611"
WC_END   = "20260719"

ESPN_ENDPOINTS = [
    # ESPN sometimes changes the slug; try a few variants
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world.2026/scoreboard",
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifaworldcup/scoreboard",
]


def fetch_wc_results() -> list[dict]:
    """Try each ESPN endpoint until one returns data."""
    for url in ESPN_ENDPOINTS:
        try:
            params = {"dates": f"{WC_START}-{WC_END}", "limit": 300}
            r = requests.get(url, params=params, timeout=12)
            if r.status_code != 200:
                continue

            data = r.json()
            events = data.get("events", [])
            if not events:
                continue

            matches = []
            for event in events:
                status_type = event.get("status", {}).get("type", {})
                if not status_type.get("completed", False):
                    continue

                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                comp = competitions[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue

                team1_raw = competitors[0].get("team", {}).get("displayName", "")
                team2_raw = competitors[1].get("team", {}).get("displayName", "")
                score1 = int(competitors[0].get("score", 0) or 0)
                score2 = int(competitors[1].get("score", 0) or 0)

                matches.append({
                    "team1":  normalize_team(team1_raw),
                    "team2":  normalize_team(team2_raw),
                    "score1": score1,
                    "score2": score2,
                    "date":   event.get("date", ""),
                    "raw1":   team1_raw,
                    "raw2":   team2_raw,
                })

            print(f"  ✓ Fetched {len(matches)} completed matches from {url}")
            return matches

        except requests.RequestException as exc:
            print(f"  ✗ {url}: {exc}")

    print(
        "\nCould not fetch data from ESPN.\n"
        "Alternatives:\n"
        "  1. football-data.org  (free API key at football-data.org/client/register)\n"
        "     Set env var FD_API_KEY and use endpoint:\n"
        "     https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED\n"
        "  2. Try again later — the endpoint slug may change as the tournament progresses.\n"
    )
    return []


# ── Score calculation ──────────────────────────────────────────────────────────

def calculate_scores(matches: list[dict]):
    team_to_players: dict[str, list[str]] = defaultdict(list)
    for player, teams in PLAYERS.items():
        for team in teams:
            team_to_players[team].append(player)

    scores: dict[str, int] = defaultdict(int)
    detail: dict[str, list] = defaultdict(list)

    unmatched_teams: set[str] = set()

    for m in matches:
        for team, opp, gs, ga in [
            (m["team1"], m["team2"], m["score1"], m["score2"]),
            (m["team2"], m["team1"], m["score2"], m["score1"]),
        ]:
            if team not in team_to_players:
                unmatched_teams.add(team)
                continue

            if gs > ga:
                result, pts = "W", 3
            elif gs < ga:
                result, pts = "L", 0
            else:
                result, pts = "D", 1

            for player in team_to_players[team]:
                scores[player] += pts
                detail[player].append({
                    "team": team, "opponent": opp,
                    "gf": gs, "ga": ga,
                    "result": result, "points": pts,
                    "date": m["date"][:10] if m["date"] else "",
                })

    # Ensure every player appears even with 0 points
    for player in PLAYERS:
        if player not in scores:
            scores[player] = 0

    if unmatched_teams:
        print(f"  ⚠ Teams in results not matched to any player: {sorted(unmatched_teams)}")

    return dict(scores), dict(detail)


# ── HTML generation ────────────────────────────────────────────────────────────

def _medal(rank: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))


def generate_html(scores: dict, detail: dict, matches: list[dict]) -> str:
    sorted_players = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Standings rows ────────────────────────────────────────────────
    rows = []
    prev_score = None
    prev_rank = 0
    for i, (player, score) in enumerate(sorted_players, 1):
        rank = prev_rank if score == prev_score else i
        prev_score, prev_rank = score, rank

        teams = PLAYERS[player]
        events = detail.get(player, [])
        wins   = sum(1 for e in events if e["result"] == "W")
        draws  = sum(1 for e in events if e["result"] == "D")
        losses = sum(1 for e in events if e["result"] == "L")
        played = wins + draws + losses

        rank_css = {1: " gold", 2: " silver", 3: " bronze"}.get(rank, "")
        rows.append(f"""
        <tr>
          <td class="rank{rank_css}">{_medal(rank)}</td>
          <td class="player">{player}</td>
          <td class="teams">{", ".join(teams)}</td>
          <td class="num">{played}</td>
          <td class="num">{wins}</td>
          <td class="num">{draws}</td>
          <td class="num">{losses}</td>
          <td class="pts">{score}</td>
        </tr>""")

    # ── Match results rows ────────────────────────────────────────────
    fantasy_teams = {t for ts in PLAYERS.values() for t in ts}

    def highlight(team: str) -> str:
        return f'<span class="hl">{team}</span>' if team in fantasy_teams else team

    mrows = []
    for m in sorted(matches, key=lambda x: x["date"]):
        t1, t2 = m["team1"], m["team2"]
        s1, s2 = m["score1"], m["score2"]
        date = m["date"][:10] if m["date"] else "—"
        mrows.append(f"""
        <tr>
          <td class="mdate">{date}</td>
          <td class="mteam right">{highlight(t1)}</td>
          <td class="mscore">{s1} – {s2}</td>
          <td class="mteam">{highlight(t2)}</td>
        </tr>""")

    match_section = "".join(mrows) if mrows else \
        '<tr><td colspan="4" class="empty">No completed matches yet.</td></tr>'

    rows_html = "".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WC 2026 Fantasy League</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: linear-gradient(160deg, #0d1b2a 0%, #1b2838 60%, #0d1b2a 100%);
      min-height: 100vh;
      padding: 24px 16px 48px;
      color: #dce6f0;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; }}

    h1 {{
      text-align: center;
      font-size: clamp(1.6rem, 4vw, 2.4rem);
      font-weight: 800;
      letter-spacing: .5px;
      background: linear-gradient(90deg, #f7c948, #f9a825);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 6px;
    }}
    .tagline {{
      text-align: center;
      color: #7a93aa;
      font-size: .85rem;
      margin-bottom: 28px;
      letter-spacing: .4px;
    }}

    .card {{
      background: rgba(255,255,255,.04);
      border: 1px solid rgba(255,255,255,.09);
      border-radius: 14px;
      overflow: hidden;
      margin-bottom: 28px;
    }}
    .card-title {{
      padding: 13px 20px;
      font-weight: 700;
      font-size: .95rem;
      color: #f9a825;
      background: rgba(255,255,255,.04);
      border-bottom: 1px solid rgba(255,255,255,.08);
      letter-spacing: .3px;
    }}

    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      padding: 10px 14px;
      text-align: left;
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #5f7d94;
      font-weight: 700;
      background: rgba(0,0,0,.15);
    }}
    tbody tr {{ transition: background .15s; }}
    tbody tr:hover {{ background: rgba(255,255,255,.04); }}
    td {{ padding: 11px 14px; border-bottom: 1px solid rgba(255,255,255,.04); font-size: .93rem; }}
    tbody tr:last-child td {{ border-bottom: none; }}

    .rank       {{ font-size: 1.1rem; width: 44px; }}
    .rank.gold   {{ color: #ffd700; }}
    .rank.silver {{ color: #c0c0c0; }}
    .rank.bronze {{ color: #cd7f32; }}
    .player  {{ font-weight: 700; color: #fff; white-space: nowrap; }}
    .teams   {{ font-size: .8rem; color: #6b8599; }}
    .num     {{ text-align: center; width: 46px; color: #9ab; }}
    .pts     {{ text-align: right; font-weight: 800; font-size: 1.15rem; color: #f9a825; padding-right: 18px; }}

    .mdate  {{ color: #5f7d94; font-size: .82rem; white-space: nowrap; width: 100px; }}
    .mteam  {{ color: #c5d8e8; font-size: .88rem; }}
    .mteam.right {{ text-align: right; }}
    .mscore {{ text-align: center; font-weight: 700; font-family: monospace; font-size: 1rem;
               color: #fff; width: 80px; }}
    .hl     {{ color: #f9a825; font-weight: 600; }}
    .empty  {{ text-align: center; padding: 20px; color: #3d5568; }}

    .footer {{ text-align: center; color: #2e4459; font-size: .78rem; margin-top: 8px; }}

    @media (max-width: 600px) {{
      .teams {{ display: none; }}
      thead th.hide-sm, td.hide-sm {{ display: none; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <h1>⚽ World Cup 2026 Fantasy League</h1>
  <p class="tagline">Win = 3 pts &nbsp;·&nbsp; Draw = 1 pt &nbsp;·&nbsp; Loss = 0 pts</p>

  <div class="card">
    <div class="card-title">Standings</div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Player</th>
          <th>Teams</th>
          <th style="text-align:center">P</th>
          <th style="text-align:center">W</th>
          <th style="text-align:center">D</th>
          <th style="text-align:center">L</th>
          <th style="text-align:right;padding-right:18px">Pts</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Results ({len(matches)} completed)</div>
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th style="text-align:right">Home</th>
          <th style="text-align:center">Score</th>
          <th>Away</th>
        </tr>
      </thead>
      <tbody>
        {match_section}
      </tbody>
    </table>
  </div>

  <p class="footer">Last updated: {now}</p>
</div>
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    print("Fetching 2026 World Cup results from ESPN…")
    matches = fetch_wc_results()

    if not matches:
        print("Generating HTML with zero scores (no match data).")

    print("Calculating fantasy scores…")
    scores, detail = calculate_scores(matches)

    html = generate_html(scores, detail, matches)

    out = "wc2026_fantasy.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nWritten → {out}")
    print("\nStandings:")
    for player, pts in sorted(scores.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {player:<18} {pts:>3} pts")


if __name__ == "__main__":
    main()
