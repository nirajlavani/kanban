import os
import re

import httpx

_GITHUB_PR_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(url: str) -> tuple[str, str, int] | None:
    m = _GITHUB_PR_RE.match(url.strip())
    if not m:
        return None
    return m.group("owner"), m.group("repo"), int(m.group("number"))


async def fetch_pr_status(owner: str, repo: str, pr_number: int) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        pr_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
            headers=headers,
        )
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        if pr_data.get("merged"):
            pr_status = "merged"
        else:
            pr_status = pr_data.get("state", "open")

        head_sha = pr_data.get("head", {}).get("sha", "")
        pr_checks = "pending"
        if head_sha:
            status_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/status",
                headers=headers,
            )
            if status_resp.status_code == 200:
                combined = status_resp.json()
                state = combined.get("state", "pending")
                if state == "success":
                    pr_checks = "passing"
                elif state == "failure" or state == "error":
                    pr_checks = "failing"
                else:
                    pr_checks = "pending"

        pr_review_state = "pending"
        reviews_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            headers=headers,
        )
        if reviews_resp.status_code == 200:
            reviews = reviews_resp.json()
            latest_by_user: dict[str, str] = {}
            for review in reviews:
                user = review.get("user", {}).get("login", "")
                state = review.get("state", "")
                if state in ("APPROVED", "CHANGES_REQUESTED"):
                    latest_by_user[user] = state

            if latest_by_user:
                if any(s == "CHANGES_REQUESTED" for s in latest_by_user.values()):
                    pr_review_state = "changes_requested"
                elif all(s == "APPROVED" for s in latest_by_user.values()):
                    pr_review_state = "approved"

    return {
        "pr_status": pr_status,
        "pr_checks": pr_checks,
        "pr_review_state": pr_review_state,
    }
