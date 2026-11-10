"""Collect a snapshot of an account's public activity.

Primary path: one GitHub GraphQL query, which is the only way to read the
contribution calendar. Fallback: the REST API, which needs no special scope but
only sees the last 90 days of public events.

The snapshot is plain JSON, so a render never touches the network and a koi can
be redrawn offline from a saved snapshot.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, timedelta

GRAPHQL_URL = "https://api.github.com/graphql"
API_URL = "https://api.github.com"

QUERY = """
query($login: String!) {
  user(login: $login) {
    databaseId
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        contributions { totalCount }
        repository {
          isFork
          primaryLanguage { name color }
        }
      }
    }
  }
}
"""


class CollectError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, token: str) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "koigen",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _get_json(url: str, token: str | None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "koigen"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _streaks(days: list[dict]) -> dict:
    longest = current = run = 0
    for day in days:
        if day["count"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    for day in reversed(days):
        if day["count"] > 0:
            current += 1
        else:
            break
    return {"longest": longest, "current": current}


def _complete_weeks(days: list[dict]) -> list[int]:
    """Totals of whole Monday-Sunday weeks before the observation date."""
    weeks: list[int] = []
    total = 0
    counted = 0
    for day in reversed(days[:-1]):
        total += day["count"]
        counted += 1
        if counted == 7:
            weeks.append(total)
            total = 0
            counted = 0
    return list(reversed(weeks))


def _is_busy_week(days: list[dict]) -> bool:
    weeks = _complete_weeks(days)
    if len(weeks) < 10:
        return False
    observed_week = [day["count"] for day in days[-7:]]
    if len(observed_week) < 7:
        return False
    compared = weeks[-52:]
    matched = sum(1 for week in compared if week >= sum(observed_week))
    return matched * 10 <= len(compared)


def collect_graphql(login: str, token: str) -> dict:
    payload = _post_json(GRAPHQL_URL, {"query": QUERY, "variables": {"login": login}}, token)
    if payload.get("errors"):
        raise CollectError(payload["errors"][0].get("message", "GraphQL error"))
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise CollectError(f"no such account: {login}")

    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({"date": day["date"], "count": int(day["contributionCount"])})
    days.sort(key=lambda day: day["date"])

    languages: Counter = Counter()
    colors: dict[str, str | None] = {}
    for entry in user["contributionsCollection"]["commitContributionsByRepository"]:
        repository = entry.get("repository") or {}
        if repository.get("isFork"):
            continue
        language = repository.get("primaryLanguage") or {}
        name = language.get("name")
        if not name:
            continue
        languages[name] += int(entry["contributions"]["totalCount"])
        colors.setdefault(name, language.get("color"))

    return {
        "login": login,
        "id": user.get("databaseId") or 0,
        "observed_on": days[-1]["date"] if days else date.today().isoformat(),
        "total_contributions": int(calendar["totalContributions"]),
        "days": days,
        "languages": [
            {"name": name, "color": colors.get(name), "count": count}
            for name, count in languages.most_common()
        ],
        "streak": _streaks(days),
        "busy_week": _is_busy_week(days),
        "source": "graphql",
    }


def collect_rest(login: str, token: str | None) -> dict:
    """Rough fallback: 90 days of public events plus repository languages."""
    user = _get_json(f"{API_URL}/users/{login}", token)
    events = _get_json(f"{API_URL}/users/{login}/events/public?per_page=100", token)

    counts: Counter = Counter()
    for event in events if isinstance(events, list) else []:
        created = event.get("created_at", "")[:10]
        if created:
            counts[created] += 1

    today = date.today()
    days = []
    for offset in range(89, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        days.append({"date": day, "count": counts.get(day, 0)})

    repositories = _get_json(
        f"{API_URL}/users/{login}/repos?per_page=100&sort=pushed", token
    )
    languages: Counter = Counter()
    for repository in repositories if isinstance(repositories, list) else []:
        if repository.get("fork"):
            continue
        language = repository.get("language")
        if language:
            languages[language] += 1

    return {
        "login": login,
        "id": user.get("id") or 0,
        "observed_on": days[-1]["date"],
        "total_contributions": sum(day["count"] for day in days),
        "days": days,
        "languages": [
            {"name": name, "color": None, "count": count}
            for name, count in languages.most_common()
        ],
        "streak": _streaks(days),
        "busy_week": _is_busy_week(days),
        "source": "rest",
    }


def collect(login: str, token: str | None = None) -> dict:
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        try:
            return collect_graphql(login, token)
        except (CollectError, urllib.error.URLError, urllib.error.HTTPError, KeyError) as error:
            print(f"GraphQL collection failed ({error}); falling back to the REST API.")
    return collect_rest(login, token)
