from fantraxapi.objs.league import DateNotInSeason, League, LivePlayer, PeriodNotInSeason, Position, ScoringPeriod, Status, Team, api, Roster
from fantraxapi.objs.roster import RosterRow
from fantraxapi.objs.base import FantraxBaseObject
from datetime import date, datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import ctypes
import sys
import os
import schedule
import time
import subprocess
import shutil

# ── Monkey-patches (unchanged from your original) ────────────────────────────

def my_custom_reset_info(self) -> None:
    responses = api.get_init_info(self)
    self.name = responses[0]["fantasySettings"]["leagueName"]
    self.year = responses[0]["fantasySettings"]["subtitle"]
    self.start_date = datetime.fromtimestamp(responses[0]["fantasySettings"]["season"]["startDate"] / 1e3)
    self.end_date = datetime.fromtimestamp(responses[0]["fantasySettings"]["season"]["endDate"] / 1e3)
    self.positions = {k: Position(self, v) for k, v in responses[0]["positionMap"].items()}
    self.status = {k: Status(self, v) for k, v in responses[1]["allObjs"].items() if "name" in v}
    period_to_day_list = {}
    for s in responses[4]["displayedLists"]["periodList"]:
        period, s = s.split(" ", maxsplit=1)
        period_to_day_list[s[1:7]] = int(period)
    self.scoring_dates = {}
    period = 1
    days_total = 1
    periodCount = {}
    ignoredDates = [date(2025, 11, 28), date(2025, 12, 17), date(2025, 12, 25)]
    for day in responses[2]["dates"]:
        scoring_date = datetime.strptime(day["object1"], "%Y-%m-%d").date()
        period = (days_total // 7) + 1
        days_total += 1
        if scoring_date in ignoredDates:
            days_total += 1
        if scoring_date == date(2026, 2, 19):
            days_total += 6
        periodCount[period] = periodCount.get(period, 0) + 1
        self.scoring_dates[scoring_date] = period
    self.scoring_periods = {p["value"]: ScoringPeriod(self, p) for p in responses[3]["displayedLists"]["scoringPeriodList"] if p["name"] != "Full Season"}
    self._scoring_periods_lookup = None
    self._update_teams(responses[3]["fantasyTeams"])

def my_custom_live_scores(self, scoring_date: date) -> dict[str, list[LivePlayer]]:
    if scoring_date not in self.scoring_dates:
        raise DateNotInSeason(scoring_date)
    response = api.get_live_scoring_stats(self, scoring_date=scoring_date)
    scorer_map = {}
    for _, data in response["scorerMap"].items():
        for _, data2 in data.items():
            for _, data3 in data2.items():
                for player in data3:
                    if player["scorer"]["scorerId"] not in scorer_map:
                        scorer_map[player["scorer"]["scorerId"]] = player["scorer"]
    active_teams = []
    for matchup in response["matchups"]:
        team1, team2 = matchup.split("_")
        active_teams.append(team1)
        active_teams.append(team2)
    final_scores = {}
    for team_id, data in response["statsPerTeam"]["allTeamsStats"].items():
        if team_id not in active_teams:
            continue
        if team_id not in final_scores:
            final_scores[team_id] = []
        for scorer_id, pts in data["ACTIVE"]["statsMap"].items():
            if not scorer_id.startswith("_"):
                player_data = scorer_map[scorer_id]
                final_scores[team_id].append(LivePlayer(self, player_data, team_id, pts["object1"], scoring_date))
    return final_scores

def my_custom_team_roster(self, team_id: str, period_number: int | None = None) -> Roster:
    if period_number is not None and period_number not in self.scoring_dates.values():
        raise PeriodNotInSeason(period_number)
    return Roster(self, team_id, api.get_team_roster_info(self, team_id, period_number=period_number))

def my_roster_init(self, league: "League", team_id: str, data: dict) -> None:
    FantraxBaseObject.__init__(self, league, data[0])
    self.team = self.league.team(team_id)
    self.period_number = int(self._data["displayedSelections"]["displayedPeriod"])
    self.period_date = self.league.start_date
    lookup: dict[str, dict] = {d["name"]: d for d in self._data["miscData"]["statusTotals"]}
    self.active = int(lookup["Active"]["total"]) if "Active" in lookup else 0
    self.active_max = int(lookup["Active"]["max"]) if "Active" in lookup else 0
    self.reserve = int(lookup["Reserve"]["total"]) if "Reserve" in lookup else 0
    self.reserve_max = int(lookup["Reserve"]["max"]) if "Reserve" in lookup else 0
    self.injured = int(lookup["Inj Res"]["total"]) if "Inj Res" in lookup else 0
    self.injured_max = int(lookup["Inj Res"]["max"]) if "Inj Res" in lookup else 0
    self.rows = []
    for stats_group, schedule_group in zip(self._data["tables"], data[1]["tables"]):
        stats_header = stats_group["header"]["cells"]
        schedule_header = schedule_group["header"]["cells"]
        for stats_row, schedule_row in zip(stats_group["rows"], schedule_group["rows"]):
            if "posId" not in stats_row:
                continue
            stuff = {"posId": stats_row["posId"], "future_games": {}, "total_fantasy_points": None, "fantasy_points_per_game": None}
            if "scorer" in stats_row or stats_row["statusId"] == "1":
                if "scorer" in stats_row:
                    stuff["scorer"] = stats_row["scorer"]
                    for header, cell in zip(schedule_header, schedule_row["cells"]):
                        if cell["content"] and "eventStr" in header and header["eventStr"]:
                            key = header["shortName"]
                            stuff["future_games"][key] = cell
                    for header, cell in zip(stats_header, stats_row["cells"]):
                        if "sortKey" in header:
                            match header["sortKey"]:
                                case "SCORE":
                                    stuff["total_fantasy_points"] = float(cell["content"])
                                case "FPTS_PER_GAME":
                                    stuff["fantasy_points_per_game"] = float(cell["content"])
                        if cell["content"] and "eventStr" in header and header["eventStr"]:
                            stuff["game_today"] = cell
            self.rows.append(RosterRow(self, stuff))

League.reset_info = my_custom_reset_info
League.live_scores = my_custom_live_scores
League.team_roster = my_custom_team_roster
Roster.__init__ = my_roster_init

# ── Config ────────────────────────────────────────────────────────────────────

LEAGUE_ID  = "znwhu9scmbsg41j3"
MY_TEAM_ID = "ep9ipyv2mcc7u7iy"

# Wallpaper will be saved here (overwritten daily)
WALLPAPER_PATH = os.path.join(os.path.expanduser("~"), "fantasy_wallpaper.png")
WALLPAPER_PATH_2 = os.path.join(os.path.expanduser("~"), "fantasy_wallpaper_2.png")
WE_PLAYLIST_NAME = "Fantasy Stats"

# Resolution — change to match your monitor
W, H = 1920, 1080

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK    = (8,  12, 22)       # near-black navy
BG_MID     = (14, 20, 38)
ACCENT     = (255, 185, 40)     # gold
ACCENT2    = (255, 120, 40)     # orange accent
TEXT_WHITE = (240, 240, 255)
TEXT_DIM   = (130, 140, 170)
GUARD_CLR  = (80,  160, 255)    # blue
FWD_CLR    = (80,  220, 140)    # green
CTR_CLR    = (200, 100, 255)    # purple
WIN_CLR    = (80,  220, 140)
LOSE_CLR   = (255,  80,  80)

# ── Font helpers ──────────────────────────────────────────────────────────────

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try common system fonts, fall back to default."""
    candidates_bold   = ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    candidates_normal = ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for name in (candidates_bold if bold else candidates_normal):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()

# ── Drawing primitives ────────────────────────────────────────────────────────

def draw_rounded_rect(draw: ImageDraw.ImageDraw,
                      xy: tuple, radius: int = 18,
                      fill=None, outline=None, width: int = 2) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                           outline=outline, width=width)

def hex_bar(draw: ImageDraw.ImageDraw, x: int, y: int,
            value: float, max_val: float,
            bar_w: int, bar_h: int, color: tuple) -> None:
    """Horizontal bar showing value/max_val ratio."""
    filled = int(bar_w * min(value / max_val, 1.0)) if max_val else 0
    draw.rounded_rectangle([x, y, x + bar_w, y + bar_h],
                           radius=bar_h // 2, fill=(30, 35, 55))
    if filled:
        draw.rounded_rectangle([x, y, x + filled, y + bar_h],
                               radius=bar_h // 2, fill=color)

# ── Background ────────────────────────────────────────────────────────────────

def make_background() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Subtle radial glow top-left
    for r in range(700, 0, -10):
        alpha = int(18 * (1 - r / 700))
        c = tuple(min(255, BG_MID[i] + alpha) for i in range(3))
        draw.ellipse([-r + 200, -r + 180, r + 200, r + 180], fill=c)

    # Bottom-right accent glow
    for r in range(500, 0, -10):
        alpha = int(12 * (1 - r / 500))
        c = (min(255, ACCENT2[0] // 6 + alpha),
             min(255, ACCENT2[1] // 10),
             min(255, ACCENT2[2] // 10))
        draw.ellipse([W - r - 100, H - r - 100, W + r - 100, H + r - 100], fill=c)

    # Thin diagonal grid lines
    for i in range(-H, W + H, 120):
        draw.line([(i, 0), (i + H, H)], fill=(20, 28, 50), width=1)

    return img

# ── Section: header ───────────────────────────────────────────────────────────

def draw_header(draw: ImageDraw.ImageDraw, today: date,
                period: int, my_score: float, opp_score: float,
                my_team_name: str, opp_team_name: str) -> None:
    pad = 60

    # Gold accent bar
    draw.rectangle([pad, 50, pad + 6, 130], fill=ACCENT)

    f_big   = _load_font(64, bold=True)
    f_small = _load_font(26)
    f_label = _load_font(20)

    draw.text((pad + 24, 48), "FANTASY HOOPS", font=f_big, fill=TEXT_WHITE)
    day_str = f"{today.strftime('%A, %B')} {today.day} {today.strftime('%Y')}"
    draw.text((pad + 24, 122), day_str.upper(), font=f_small, fill=ACCENT)

    # Period badge
    draw_rounded_rect(draw, (W - 260, 50, W - pad, 120),
                      radius=14, fill=(20, 28, 50), outline=ACCENT, width=2)
    draw.text((W - 160, 85), f"WEEK {period}", font=_load_font(30, bold=True),
              fill=ACCENT, anchor="mm")

    # Scoreboard strip
    strip_y = 155
    draw_rounded_rect(draw, (pad, strip_y, W - pad, strip_y + 80),
                      radius=16, fill=(16, 24, 44), outline=(30, 40, 70), width=1)

    cx = W // 2
    score_font  = _load_font(46, bold=True)
    name_font   = _load_font(22)
    vs_font     = _load_font(28)

    # My team
    draw.text((pad+140, strip_y + 40), f"{my_score:.1f}",
              font=score_font, fill=WIN_CLR if my_score >= opp_score else TEXT_WHITE,
              anchor="rm", align="left")
    draw.text((pad+145, strip_y + 40), my_team_name.upper(),
              font=name_font, fill=TEXT_DIM, anchor="lm", align="left")   # crude: just show under

    # VS
    draw.text((cx, strip_y + 40), "VS", font=vs_font, fill=TEXT_DIM, anchor="mm")

    # Opponent
    draw.text((W-pad-140, strip_y + 40), f"{opp_score:.1f}",
              font=score_font, fill=WIN_CLR if opp_score > my_score else TEXT_WHITE,
              anchor="lm", align="right")
    draw.text((W-pad-145, strip_y + 40), opp_team_name.upper(),
              font=name_font, fill=TEXT_DIM, anchor="rm", align="right")

# ── Section: position column ──────────────────────────────────────────────────

def draw_position_column(draw: ImageDraw.ImageDraw,
                          title: str, color: tuple,
                          scores: dict,          # {name: pts}
                          top_n: int,
                          x: int, y: int,
                          col_w: int, topPlayers: dict) -> int:
    """Draw a position block, return the y-coordinate after the block."""
    f_title  = _load_font(22, bold=True)
    f_name   = _load_font(20)
    f_pts    = _load_font(20, bold=True)
    f_label  = _load_font(16)

    # Title
    draw.rectangle([x, y, x + 4, y + 28], fill=color)
    draw.text((x + 14, y + 2), title, font=f_title, fill=color)
    y += 42

    if not scores:
        draw.text((x + 14, y), "No data", font=f_name, fill=TEXT_DIM)
        return y + 36

    max_pts = max(scores.values()) if scores else 1
    row_h   = 52
    for i, (name, pts) in enumerate(scores.items()):
        is_starter = i < top_n or name in topPlayers
        bg_fill = (20, 28, 50) if is_starter else (14, 18, 34)
        outline_clr = color if is_starter else (28, 36, 58)

        draw_rounded_rect(draw,
                          (x, y, x + col_w, y + row_h - 4),
                          radius=10, fill=bg_fill, outline=outline_clr, width=1)

        # Rank number
        draw.text((x + 14, y + row_h // 2 - 2),
                  f"#{i+1}", font=f_label,
                  fill=color if is_starter else TEXT_DIM, anchor="lm")

        # Name (truncated)
        short_name = name.split()[-1] if " " in name else name
        draw.text((x + 46, y + row_h // 2 - 2),
                  short_name[:16], font=f_name, fill=TEXT_WHITE if is_starter else TEXT_DIM,
                  anchor="lm")

        # Points
        draw.text((x + col_w - 12, y + row_h // 2 - 2),
                  f"{pts:.1f}", font=f_pts,
                  fill=ACCENT if is_starter else TEXT_DIM, anchor="rm")

        # Mini bar
        hex_bar(draw, x + 46, y + row_h - 12,
                pts, max_pts, col_w - 90, 4, color)

        y += row_h

    return y + 12

# ── Section: top-players summary ──────────────────────────────────────────────

def draw_top_players(draw: ImageDraw.ImageDraw,
                     top_players: dict,
                     x: int, y: int, col_w: int) -> None:
    f_title = _load_font(22, bold=True)
    f_name  = _load_font(20)
    f_pts   = _load_font(22, bold=True)
    f_sub   = _load_font(16)

    draw.rectangle([x, y, x + 4, y + 28], fill=ACCENT)
    draw.text((x + 14, y + 2), "STARTING LINEUP", font=f_title, fill=ACCENT)
    y += 42

    max_pts = max(top_players.values()) if top_players else 1
    for rank, (name, pts) in enumerate(top_players.items()):
        pct = pts / max_pts
        bar_w = int((col_w - 20) * pct)

        # Background row
        draw_rounded_rect(draw, (x, y, x + col_w, y + 48),
                          radius=10, fill=(18, 26, 48), outline=(32, 42, 72), width=1)

        # Filled accent bar (inside row)
        if bar_w > 10:
            draw.rounded_rectangle([x + 1, y + 1, x + bar_w, y + 47],
                                   radius=10, fill=(30, 44, 80))

        short = name.split()[-1] if " " in name else name
        draw.text((x + 14, y + 24), f"{rank+1}. {short[:18]}",
                  font=f_name, fill=TEXT_WHITE, anchor="lm")
        draw.text((x + col_w - 12, y + 24), f"{pts:.1f}",
                  font=f_pts, fill=ACCENT, anchor="rm")

        y += 54

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_data(league: League, today: date):
    guardScores   = {}
    forwardScores = {}
    centerScores  = {}

    period_num   = league.scoring_dates[today]
    period_start = league.scoring_period_results(True, False)[period_num].start
    currDate     = period_start

    while currDate <= today:
        try:
            live = league.live_scores(currDate)[MY_TEAM_ID]
        except (KeyError, DateNotInSeason):
            currDate += timedelta(days=1)
            continue
        for player in live:
            p = player.pos_short_name
            if p == "G":
                guardScores[player.name]   = guardScores.get(player.name, 0)   + player.points
            elif p == "F":
                forwardScores[player.name] = forwardScores.get(player.name, 0) + player.points
            elif p == "C":
                centerScores[player.name]  = centerScores.get(player.name, 0)  + player.points
        currDate += timedelta(days=1)

    srt = lambda d: dict(sorted(d.items(), key=lambda i: i[1], reverse=True))
    guardSorted   = srt(guardScores)
    forwardSorted = srt(forwardScores)
    centerSorted  = srt(centerScores)

    bottomPlayers = dict(
        list(guardSorted.items())[2:] +
        list(forwardSorted.items())[2:] +
        list(centerSorted.items())[2:]
    )
    bottomSorted = srt(bottomPlayers)
    topPlayers   = srt(dict(
        list(guardSorted.items())[:2] +
        list(forwardSorted.items())[:2] +
        list(centerSorted.items())[:1] +
        list(bottomSorted.items())[:2]
    ))

    # Matchup scores
    my_score   = 0.0
    opp_score  = 0.0
    my_name    = "My Team"
    opp_name   = "Opponent"
    try:
        results = league.scoring_period_results(True, False)[period_num]
        for matchup in results.matchups:
            if matchup.home.id == MY_TEAM_ID:
                my_score  = matchup.home_score
                opp_score = matchup.away_score
                my_name   = matchup.home.name
                opp_name  = matchup.away.name
            elif matchup.away.id == MY_TEAM_ID:
                my_score  = matchup.away_score
                opp_score = matchup.home_score
                my_name   = matchup.away.name
                opp_name  = matchup.home.name
    except Exception:
        pass

    return (guardSorted, forwardSorted, centerSorted,
            topPlayers, my_score, opp_score, my_name, opp_name, period_num)

# ── Wallpaper composer ────────────────────────────────────────────────────────

def build_wallpaper(league: League) -> None:
    today = date.today()
    print(f"[{datetime.now():%H:%M:%S}] Fetching data…")

    (guardSorted, forwardSorted, centerSorted,
     topPlayers, my_score, opp_score,
     my_name, opp_name, period_num) = fetch_data(league, today)

    print(f"[{datetime.now():%H:%M:%S}] Rendering wallpaper…")

    img  = make_background()
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw_header(draw, today, period_num,
                my_score, opp_score, my_name, opp_name)

    # ── Three position columns ─────────────────────────────────────────────
    pad    = 60
    col_w  = (W - pad * 2 - 40 * 2) // 4   # 4 columns total
    col_y  = 270
    gap    = 40

    gx = pad
    fx = pad + col_w + gap
    cx = pad + (col_w + gap) * 2

    gY_end = draw_position_column(draw, "GUARDS",   GUARD_CLR, guardSorted,   2, gx, col_y, col_w, topPlayers)
    fY_end = draw_position_column(draw, "FORWARDS", FWD_CLR,   forwardSorted, 2, fx, col_y, col_w, topPlayers)
    cY_end = draw_position_column(draw, "CENTERS",  CTR_CLR,   centerSorted,  1, cx, col_y, col_w, topPlayers)

    # ── Top players (rightmost column) ────────────────────────────────────
    tx = pad + (col_w + gap) * 3
    draw_top_players(draw, topPlayers, tx, col_y, col_w)

    # ── Thin separator line at bottom ─────────────────────────────────────
    bot = H - 50
    draw.line([(pad, bot), (W - pad, bot)], fill=(30, 40, 70), width=1)
    draw.text((pad, bot + 12), f"Updated {datetime.now():%I:%M %p}  •  Fantrax Fantasy Basketball",
              font=_load_font(18), fill=TEXT_DIM)

    img.save(WALLPAPER_PATH, "PNG")
    shutil.copy(WALLPAPER_PATH, WALLPAPER_PATH_2)
    print(f"[{datetime.now():%H:%M:%S}] Saved → {WALLPAPER_PATH}")
    set_wallpaper(WALLPAPER_PATH)

# ── OS wallpaper setters ──────────────────────────────────────────────────────

def set_wallpaper(path: str) -> None:
    abs_path = os.path.abspath(path)

    # Path to your Wallpaper Engine executable — adjust if installed elsewhere
    we_exe = r"C:\Program Files (x86)\Steam\steamapps\common\wallpaper_engine\wallpaper64.exe"

    if not os.path.exists(we_exe):
        # Fall back to 32-bit version
        we_exe = we_exe.replace("wallpaper64.exe", "wallpaper32.exe")

    if os.path.exists(we_exe):
        subprocess.run([we_exe, "-control", "openPlaylist",
                        "-playlist", WE_PLAYLIST_NAME])
        print(f"Wallpaper set via Wallpaper Engine.")
    else:
        # Fallback: plain Windows API if WE isn't found
        import ctypes
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
        print(f"Wallpaper Engine not found, set via Windows API.")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    league = League(LEAGUE_ID)

    # Run immediately on launch
    build_wallpaper(league)

    # Then refresh every day at 8 PM
    schedule.every().minute.do(build_wallpaper, league=league)

    print("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)