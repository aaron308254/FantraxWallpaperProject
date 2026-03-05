from fantraxapi.objs.league import DateNotInSeason, League, LivePlayer, PeriodNotInSeason, Position, ScoringPeriod, Status, Team, api, Roster
from fantraxapi.objs.roster import RosterRow
from fantraxapi.objs.base import FantraxBaseObject
from datetime import date, datetime, timedelta

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


league_id = "znwhu9scmbsg41j3"
myTeamID = 'ep9ipyv2mcc7u7iy'

league = League(league_id)

##print(league.standings())
##print("")

today = date.today()

guardScores = {}
forwardScores = {}
centerScores = {}

currentPeriodStartDate = league.scoring_period_results(True, False)[league.scoring_dates[today]].start
currDate = currentPeriodStartDate

while currDate <= today:
    myLiveScores = league.live_scores(currDate)[myTeamID]
    for player in myLiveScores:
        if player.pos_short_name == "G":
            guardScores[player.name] = guardScores.get(player.name, 0) + player.points
        elif player.pos_short_name == "F":
            forwardScores[player.name] = forwardScores.get(player.name, 0) + player.points
        elif player.pos_short_name == "C":
            centerScores[player.name] = centerScores.get(player.name, 0) + player.points
    currDate += timedelta(days=1)
guardSorted = dict(sorted(guardScores.items(), key=lambda item: item[1], reverse=True))
forwardSorted = dict(sorted(forwardScores.items(), key=lambda item: item[1], reverse=True))
centerSorted = dict(sorted(centerScores.items(), key=lambda item: item[1], reverse=True))

bottomPlayers = dict(list(guardSorted.items())[2:]+list(forwardSorted.items())[2:]+list(centerSorted.items())[2:])
bottomPlayersSorted = dict(sorted(bottomPlayers.items(), key=lambda item: item[1], reverse=True))
topPlayers = dict(list(guardSorted.items())[:2]+list(forwardSorted.items())[:2]+list(centerSorted.items())[:1]+list(bottomPlayersSorted.items())[:2])
topPlayersSorted = dict(sorted(topPlayers.items(), key=lambda item: item[1], reverse=True))

print("Guard Scores:")
for player, points in guardSorted.items():
    print(f"  {player}: {points}")

print("Forward Scores:")
for player, points in forwardSorted.items():
    print(f"  {player}: {points}")

print("Center Scores:")
for player, points in centerSorted.items():
    print(f"  {player}: {points}")

print("Top Players:")
for player, points in topPlayersSorted.items():
    print(f"  {player}: {points}")

for matchup in league.scoring_period_results(True, False)[league.scoring_dates[today]].matchups:
    myTeam = None
    opponent = None
    if matchup.home.id == myTeamID:
        myTeam = matchup.home
        opponent = matchup.away
    elif matchup.away.id == myTeamID:
        myTeam = matchup.away
        opponent = matchup.home
    else:
        continue
    print(myTeam.roster().rows[0].total_fantasy_points)