#!/usr/bin/env python3
"""Data fetcher and metrics aggregator for JPluger Pull Request statistics.

Uses local `gh` CLI and GraphQL batch queries to fetch 12-month PR backlogs, reviewer distributions, and velocity metrics.
"""

from __future__ import annotations

import argparse
import calendar
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.parse
from datetime import timezone
from typing import Any, Dict, List, Optional, Union

BOT_LOGINS = {
    "cursor",
    "bugbot",
    "dependabot",
    "dependabot[bot]",
    "github-actions",
    "github-actions[bot]",
    "renovate",
    "renovate[bot]",
    "codecov",
    "codecov[bot]",
    "sonarcloud",
    "sonarcloud[bot]",
}

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data.json")
REPORT_FILE = os.path.join(HERE, "report.html")
TEMPLATE_FILE = os.path.join(HERE, "template.html")


def check_gh_installed() -> bool:
    """Verify that gh CLI is available and authenticated."""
    try:
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_gh_json(cmd: list[str], max_retries: int = 3) -> list | dict:
    """Run a gh CLI command and parse JSON output with retries."""
    for attempt in range(max_retries):
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if res.returncode == 0:
            try:
                return json.loads(res.stdout)
            except json.JSONDecodeError:
                pass
        time.sleep(1.5)
        
    raise RuntimeError(f"gh command failed after {max_retries} attempts: {' '.join(cmd)}\nError: {res.stderr}")


def fetch_12_months_counts(repo: str) -> list[dict]:
    """Fetch 12-month opened and merged PR counts in a single GraphQL query."""
    now = datetime.datetime.now(timezone.utc)
    month_tuples = []
    for i in range(11, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        month_tuples.append((y, m))

    query_parts = []
    for idx, (y, m) in enumerate(month_tuples):
        last_day = calendar.monthrange(y, m)[1]
        is_current_month = (m == now.month and y == now.year)
        end_day = now.day if is_current_month else last_day
        
        start_str = f"{y:04d}-{m:02d}-01"
        end_str = f"{y:04d}-{m:02d}-{end_day:02d}"
        
        opened_q = f"repo:{repo} is:pr created:{start_str}..{end_str}"
        merged_q = f"repo:{repo} is:pr is:merged merged:{start_str}..{end_str}"
        
        query_parts.append(f'o{idx}: search(query: "{opened_q}", type: ISSUE) {{ issueCount }}')
        query_parts.append(f'm{idx}: search(query: "{merged_q}", type: ISSUE) {{ issueCount }}')

    full_gql = "query { " + " ".join(query_parts) + " }"

    res = subprocess.run(["gh", "api", "graphql", "-f", f"query={full_gql}"], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"GraphQL monthly query failed: {res.stderr}")
        
    data = json.loads(res.stdout).get("data", {})

    results = []
    for idx, (y, m) in enumerate(month_tuples):
        month_name = calendar.month_abbr[m]
        is_current_month = (m == now.month and y == now.year)
        label = f"{month_name}'{str(y)[2:]}" if not is_current_month else f"{month_name}'{str(y)[2:]}*"
        
        cnt_o = data.get(f"o{idx}", {}).get("issueCount", 0)
        cnt_m = data.get(f"m{idx}", {}).get("issueCount", 0)
        net_overflow = cnt_o - cnt_m
        
        results.append({
            "year": y,
            "monthNum": m,
            "month": month_name,
            "label": label,
            "opened": cnt_o,
            "merged": cnt_m,
            "netOverflow": net_overflow,
            "isPartial": is_current_month
        })

    return results


def fetch_open_prs(repo: str) -> list[dict]:
    """Fetch all open pull requests with reviews, requested reviewers, diff sizes, base branch, and timestamps."""
    cmd = [
        "gh", "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", "300",
        "--json", "number,title,createdAt,updatedAt,url,reviews,reviewRequests,author,isDraft,additions,deletions,changedFiles,baseRefName"
    ]
    return run_gh_json(cmd)


def process_stats(repo: str, prs: list[dict], monthly_trends: list[dict]) -> dict:
    """Calculate KPI metrics, aging, bottleneck root-causes, and 6-tier diff sizes."""
    now = datetime.datetime.now(timezone.utc)
    
    total_open = len(prs)
    unreviewed_count = 0
    unassigned_count = 0
    stale_30d_count = 0
    older_90d_count = 0
    over_1yr_count = 0
    approved_unmerged_count = 0
    changes_requested_count = 0
    
    age_bins = {
        "0-7d": 0,
        "8-18d": 0,
        "19-90d": 0,
        "3-12m": 0,
        ">1y": 0
    }
    
    size_bins = {
        "Small (<100)": 0,
        "Medium (100-500)": 0,
        "Large (500-1k)": 0,
        "Huge (1k-5k)": 0,
        "The Mountain (>5k)": 0
    }
    
    reviewer_counts = {}
    author_counts = {}
    base_counts = {}
    processed_prs = []
    
    for pr in prs:
        created_at = datetime.datetime.fromisoformat(pr["createdAt"].replace("Z", "+00:00"))
        updated_at = datetime.datetime.fromisoformat(pr["updatedAt"].replace("Z", "+00:00"))
        
        age_seconds = (now - created_at).total_seconds()
        age_days = age_seconds / 86400.0
        inactive_days = (now - updated_at).total_seconds() / 86400.0
        
        is_draft = bool(pr.get("isDraft", False))
        author_login = (pr.get("author") or {}).get("login", "unknown")
        
        # Author counts (exclude draft PRs)
        if not is_draft:
            author_counts[author_login] = author_counts.get(author_login, 0) + 1
        
        base_branch = pr.get("baseRefName", "master")
        base_counts[base_branch] = base_counts.get(base_branch, 0) + 1
        
        # Review requests (exclude draft PRs)
        raw_reqs = pr.get("reviewRequests") or []
        requested_reviewers = [r.get("login") or r.get("name", "") for r in raw_reqs if r]
        
        if not requested_reviewers:
            if not is_draft:
                unassigned_count += 1
        else:
            if not is_draft:
                for r_name in requested_reviewers:
                    reviewer_counts[r_name] = reviewer_counts.get(r_name, 0) + 1
        
        # Human reviews (exclude bots and exclude the PR author themselves)
        raw_reviews = pr.get("reviews") or []
        human_reviews = [
            r for r in raw_reviews
            if (r.get("author") or {}).get("login", "").lower() not in BOT_LOGINS
            and (r.get("author") or {}).get("login", "").lower() != author_login.lower()
        ]
        
        has_human_review = len(human_reviews) > 0
        if not has_human_review:
            unreviewed_count += 1
            
        review_state = "NO_REVIEW"
        if human_reviews:
            states = [r.get("state") for r in human_reviews]
            if "APPROVED" in states:
                review_state = "APPROVED"
                approved_unmerged_count += 1
            elif "CHANGES_REQUESTED" in states:
                review_state = "CHANGES_REQUESTED"
                changes_requested_count += 1
            else:
                review_state = "COMMENTED"
        elif not requested_reviewers:
            review_state = "UNASSIGNED"
        else:
            review_state = "PENDING_REVIEW"
            
        if inactive_days >= 30.0:
            stale_30d_count += 1
            
        if age_days > 90.0:
            older_90d_count += 1
            
        if age_days > 365.0:
            over_1yr_count += 1
            
        # Age bucket classification
        if age_days <= 7.0:
            age_bins["0-7d"] += 1
        elif age_days <= 18.0:
            age_bins["8-18d"] += 1
        elif age_days <= 90.0:
            age_bins["19-90d"] += 1
        elif age_days <= 365.0:
            age_bins["3-12m"] += 1
        else:
            age_bins[">1y"] += 1
            
        # 6-tier Size Classification
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        total_lines = additions + deletions
        changed_files = pr.get("changedFiles", 0)
        
        if total_lines < 100:
            size_bins["Small (<100)"] += 1
            size_cat = "Small"
        elif total_lines <= 500:
            size_bins["Medium (100-500)"] += 1
            size_cat = "Medium"
        elif total_lines <= 1000:
            size_bins["Large (500-1k)"] += 1
            size_cat = "Large"
        elif total_lines <= 5000:
            size_bins["Huge (1k-5k)"] += 1
            size_cat = "Huge"
        else:
            size_bins["The Mountain (>5k)"] += 1
            size_cat = "The Mountain"
            
        last_activity_str = updated_at.strftime("%b %Y")
        
        processed_prs.append({
            "number": pr["number"],
            "title": pr["title"],
            "url": pr.get("url", f"https://github.com/{repo}/pull/{pr['number']}"),
            "createdAt": pr["createdAt"],
            "updatedAt": pr["updatedAt"],
            "author": author_login,
            "base": base_branch,
            "requestedReviewers": requested_reviewers,
            "reviewState": review_state,
            "ageDays": round(age_days, 1),
            "inactiveDays": round(inactive_days, 1),
            "hasReview": has_human_review,
            "reviewsCount": len(human_reviews),
            "additions": additions,
            "deletions": deletions,
            "totalLines": total_lines,
            "changedFiles": changed_files,
            "sizeCategory": size_cat,
            "lastActivity": last_activity_str,
            "isDraft": pr.get("isDraft", False)
        })
        
    # Sort PRs by creation date (oldest first)
    processed_prs.sort(key=lambda x: x["createdAt"])
    
    top_reviewers = [
        {"name": k, "count": v}
        for k, v in sorted(reviewer_counts.items(), key=lambda x: x[1], reverse=True)[:6]
    ]
    
    top_authors = [
        {"name": k, "count": v}
        for k, v in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    top_bases = [
        {"name": k, "count": v}
        for k, v in sorted(base_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    older_than_week = total_open - age_bins["0-7d"]
    older_than_18d = older_than_week - age_bins["8-18d"]
    
    overflow_parts = [f"+{m['netOverflow']}" if m['netOverflow'] >= 0 else str(m['netOverflow']) for m in monthly_trends]
    net_overflows_str = ", ".join(overflow_parts[-4:])
    
    total_12m_deficit = sum(m['netOverflow'] for m in monthly_trends)
    
    unassigned_pct = round((unassigned_count / total_open) * 100) if total_open > 0 else 0
    mountain_pct = round((size_bins["The Mountain (>5k)"] / total_open) * 100) if total_open > 0 else 0
    
    return {
        "repo": repo,
        "fetchedAt": now.isoformat(),
        "formattedDate": now.strftime("%d %b %Y"),
        "totalOpen": total_open,
        "unreviewedCount": unreviewed_count,
        "unreviewedFraction": f"{round((unreviewed_count / total_open) * 10)}/10" if total_open > 0 else "0/10",
        "unassignedCount": unassigned_count,
        "unassignedPct": unassigned_pct,
        "approvedUnmergedCount": approved_unmerged_count,
        "changesRequestedCount": changes_requested_count,
        "stale30dCount": stale_30d_count,
        "older90dCount": older_90d_count,
        "over1yrCount": over_1yr_count,
        "olderThanWeek": older_than_week,
        "olderThan18d": older_than_18d,
        "mountainCount": size_bins["The Mountain (>5k)"],
        "mountainPct": mountain_pct,
        "netOverflowsStr": net_overflows_str,
        "total12mDeficit": total_12m_deficit,
        "ageBins": age_bins,
        "sizeBins": size_bins,
        "topReviewers": top_reviewers,
        "topAuthors": top_authors,
        "topBases": top_bases,
        "monthlyTrends": monthly_trends,
        "oldestPrs": processed_prs[:25],
        "allPrs": processed_prs
    }


def fetch_all(repo: str = "Anchanto/JPluger") -> dict:
    """Perform full 12-month data fetch and calculation with fallback."""
    print(f"[*] Fetching PRs for {repo} using `gh` CLI...")
    try:
        prs = fetch_open_prs(repo)
        print(f"[✓] Retrieved {len(prs)} open PRs.")
    except Exception as e:
        print(f"[!] Error fetching live PRs ({e}); falling back to cache.", file=sys.stderr)
        cached = load_cached_data()
        if cached:
            return cached
        raise

    print(f"[*] Fetching 12-month velocity metrics via GraphQL batch query...")
    monthly_trends = fetch_12_months_counts(repo)
    print(f"[✓] Retrieved 12-month velocity trends ({len(monthly_trends)} months).")
    
    stats = process_stats(repo, prs, monthly_trends)
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"[✓] Saved stats to {DATA_FILE}")
    
    generate_static_report(stats)
    return stats


def generate_static_report(stats: dict | None = None) -> str:
    """Generate a self-contained report.html with embedded data."""
    if stats is None:
        stats = load_cached_data() or {}
        
    if not os.path.exists(TEMPLATE_FILE):
        raise FileNotFoundError(f"Template not found: {TEMPLATE_FILE}")
        
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        html = f.read()
        
    json_str = json.dumps(stats)
    html = html.replace("__REPORT_DATA_JSON__", json_str)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[✓] Generated static HTML report at {REPORT_FILE}")
    return REPORT_FILE


def load_cached_data() -> dict | None:
    """Load data from local cache if available."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch PR statistics for JPluger")
    parser.add_argument("--repo", default="Anchanto/JPluger", help="GitHub repo in Owner/Repo format")
    parser.add_argument("--static", action="store_true", help="Generate static HTML report")
    args = parser.parse_args()
    
    if not check_gh_installed():
        print("Error: `gh` CLI is not authenticated or not installed.", file=sys.stderr)
        sys.exit(1)
        
    stats = fetch_all(args.repo)
    print(f"\nSuccessfully updated statistics for {args.repo} at {stats['formattedDate']}.")
