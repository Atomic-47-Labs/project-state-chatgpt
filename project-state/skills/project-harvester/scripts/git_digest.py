#!/usr/bin/env python3
"""Read-only commit digests from a git clone on this machine, for project-harvester (issue #118).

    python3 git_digest.py --repo ~/code/widget-api --since 2026-10-20T00:00:00Z [--branch main] [--name widget-api] [--tags]

Prints one JSON object on stdout:

    {"repo": "widget-api", "path": "/Users/me/code/widget-api", "branch": "main", "ref": "refs/heads/main",
     "head": "<sha of the ref>", "since": "2026-10-20T00:00:00Z", "cursor": "2026-10-25T23:30:00Z",
     "commit_count": 6,
     "days": [{"date": "2026-10-24", "source_id": "widget-api#commit-digest:2026-10-24@<sha12>",
               "dedup_key": "git:widget-api#commit-digest:2026-10-24@<sha12>",
               "first_at": "...", "last_at": "...", "count": 2,
               "commits": [{"sha", "short", "ref": "widget-api@<sha>", "parents": [...], "merge": false,
                            "author", "email", "authored_at", "committed_at", "subject"}]}],
     "tags": [{"tag", "sha", "created_at", "subject", "source_id", "dedup_key"}]}   # only with --tags

Rules (the skill relies on them; scripts/test-git-digest.py checks them):
  - A commit is in range when its committer time is strictly after --since. Days are UTC dates of the committer
    time, the same bucketing the GitHub API's commit dates give the hosted path.
  - `cursor` is the newest committer time seen, or --since unchanged when the range is empty.
  - The day's source_id ends with the newest commit's short sha, so a later harvest the same day that finds more
    commits is a new digest, and a re-run over the same commits is the same key (dedup by harvest/seen.json).
  - Merge commits are kept and marked `merge: true`. Names and subjects that are not UTF-8 are decoded as Latin-1.
  - Read-only: only `git rev-parse`, `symbolic-ref`, `log` and `for-each-ref`, with GIT_OPTIONAL_LOCKS=0. Never
    fetch, pull, checkout, or write anything in the clone.

Exit codes: 0 ok (including an empty range), 2 the path is not a git repository, the branch does not exist, or an
argument is malformed (the JSON then carries {"error": ...}).

Stdlib only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

US = b"\x1f"
LOG_FORMAT = "%H%x1f%P%x1f%cI%x1f%aI%x1f%an%x1f%ae%x1f%s"
TAG_FORMAT = "%(refname:short)%1f%(objectname)%1f%(*objectname)%1f%(creatordate:iso-strict)%1f%(contents:subject)"
READ_ONLY = {"rev-parse", "symbolic-ref", "log", "for-each-ref"}
# `git log --since` can stop walking early when committer dates are out of order (a rebase, a pulled branch).
# Ask git for a wider window and filter exactly here.
SINCE_SLOP = timedelta(days=2)


class GitError(Exception):
    pass


def text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1")


def git(repo: str, *args: str, check: bool = True) -> bytes:
    if args[0] not in READ_ONLY:
        raise GitError(f"refusing git {args[0]}: this helper only reads")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    cmd = ["git", "--no-pager", "-C", repo, "-c", "core.fsmonitor=false", "-c", "log.showSignature=false", *args]
    p = subprocess.run(cmd, capture_output=True, env=env)
    if check and p.returncode != 0:
        raise GitError(text(p.stderr).strip() or f"git {args[0]} exited {p.returncode}")
    return p.stdout if p.returncode == 0 else b""


def parse_time(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_ref(repo: str, branch: str | None) -> tuple[str | None, str | None]:
    """(branch name or None when detached, ref to log) — or (None, None) for a repository with no commits."""
    if branch:
        if branch.startswith("-"):
            raise GitError(f"branch {branch!r} is not a branch name")
        for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}", branch):
            if git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).strip():
                return branch, ref
        raise GitError(f"no branch {branch!r} in {repo}")
    if not git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False).strip():
        return None, None
    name = text(git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)).strip()
    return (name or None), (f"refs/heads/{name}" if name else "HEAD")


def commits_since(repo: str, ref: str, since: datetime, name: str) -> list[dict]:
    out = git(repo, "log", ref, "--no-color", "--no-show-signature", "--no-decorate", "-z",
              f"--format={LOG_FORMAT}", f"--since={iso(since - SINCE_SLOP)}")
    rows = []
    for rec in out.split(b"\0"):
        rec = rec.strip(b"\n")
        if not rec:
            continue
        f = rec.split(US, 6)
        if len(f) < 7:
            continue
        sha, parents, cdate, adate, author, email, subject = (text(x) for x in f)
        committed = parse_time(cdate)
        if committed <= since:
            continue
        rows.append({
            "sha": sha, "short": sha[:12], "ref": f"{name}@{sha}",
            "parents": parents.split(), "merge": len(parents.split()) > 1,
            "author": author, "email": email,
            "authored_at": iso(parse_time(adate)), "committed_at": iso(committed),
            "subject": subject,
        })
    rows.sort(key=lambda c: (c["committed_at"], c["sha"]))
    return rows


def day_digests(commits: list[dict], name: str) -> list[dict]:
    days: dict[str, list[dict]] = {}
    for c in commits:
        days.setdefault(c["committed_at"][:10], []).append(c)
    out = []
    for date in sorted(days):
        cs = days[date]
        sid = f"{name}#commit-digest:{date}@{cs[-1]['short']}"
        out.append({"date": date, "source_id": sid, "dedup_key": f"git:{sid}",
                    "first_at": cs[0]["committed_at"], "last_at": cs[-1]["committed_at"],
                    "count": len(cs), "commits": cs})
    return out


def tags_since(repo: str, since: datetime, name: str) -> list[dict]:
    out = git(repo, "for-each-ref", "refs/tags", f"--format={TAG_FORMAT}")
    tags = []
    for line in out.split(b"\n"):
        if not line.strip():
            continue
        f = line.split(US, 4)
        if len(f) < 5:
            continue
        tag, obj, target, created, subject = (text(x) for x in f)
        if not created:
            continue
        when = parse_time(created)
        if when <= since:
            continue
        sid = f"{name}#tag:{tag}"
        tags.append({"tag": tag, "sha": target or obj, "created_at": iso(when), "subject": subject,
                     "source_id": sid, "dedup_key": f"git:{sid}"})
    tags.sort(key=lambda t: (t["created_at"], t["tag"]))
    return tags


def digest(path: str, since: datetime, branch: str | None = None, name: str | None = None,
           with_tags: bool = False) -> dict:
    repo = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(repo):
        raise GitError(f"{repo} is not a directory")
    git(repo, "rev-parse", "--git-dir")  # raises when not a repository (or not a safe.directory)
    if text(git(repo, "rev-parse", "--is-bare-repository")).strip() != "true":
        top = text(git(repo, "rev-parse", "--show-toplevel")).strip()
        if os.path.realpath(top) != os.path.realpath(repo):
            raise GitError(f"{repo} is a folder inside the repository at {top}, not a clone's root")
    name = name or os.path.basename(repo.rstrip(os.sep))
    br, ref = resolve_ref(repo, branch)
    result = {"repo": name, "path": repo, "branch": br, "ref": ref, "head": None, "since": iso(since),
              "cursor": iso(since), "commit_count": 0, "days": []}
    if ref:
        result["head"] = text(git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")).strip()
        commits = commits_since(repo, ref, since, name)
        result["commit_count"] = len(commits)
        result["days"] = day_digests(commits, name)
        if commits:
            result["cursor"] = commits[-1]["committed_at"]
    if with_tags:
        result["tags"] = tags_since(repo, since, name)
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Read-only per-day commit digests from a local git clone.")
    ap.add_argument("--repo", required=True, help="path to the clone (~ is expanded)")
    ap.add_argument("--since", help="ISO-8601 cursor; commits strictly after it (default: 7 days ago)")
    ap.add_argument("--branch", help="branch to read (default: the branch HEAD is on)")
    ap.add_argument("--name", help="repo name used in source ids (default: the folder name)")
    ap.add_argument("--tags", action="store_true", help="also list tags created after --since")
    a = ap.parse_args(argv)
    try:
        since = parse_time(a.since) if a.since else datetime.now(timezone.utc) - timedelta(days=7)
    except ValueError:
        print(json.dumps({"error": f"--since {a.since!r} is not an ISO-8601 time"}))
        return 2
    try:
        res = digest(a.repo, since, a.branch, a.name, a.tags)
    except GitError as e:
        print(json.dumps({"error": str(e), "repo": a.name or os.path.basename(a.repo.rstrip("/"))}))
        print(f"git_digest: {e}", file=sys.stderr)
        return 2
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
