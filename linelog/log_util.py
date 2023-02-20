import re
from itertools import dropwhile
import datetime
from datetime import datetime as dt
import json
from os.path import splitext
from typing import NamedTuple

import pygit2

from sloc import sloc_from_text


class CommitLineData(NamedTuple):
    timestamp: float
    totals: dict[str, int]


def is_commit_on_date(commit, target_date: datetime.date) -> bool:

    interval_start = dt.combine(target_date, datetime.time.min)

    interval_end = dt.combine(target_date, datetime.time.max)

    return interval_start.timestamp() <= commit.commit_time <= interval_end.timestamp()


def get_files(
    tree_root: pygit2.Tree,
    ignore_patterns: list[str] | None = None,
):

    if ignore_patterns is None:
        ignore_patterns = []

    contained_files: list[pygit2.Blob] = []
    for item in tree_root:

        if item.name is None:
            continue

        matched_ignores = map(lambda p: re.match(p, str(item.name)), ignore_patterns)

        if any(matched_ignores):
            continue

        if isinstance(item, pygit2.Blob) and not item.is_binary:
            contained_files.append(item)

        elif isinstance(item, pygit2.Tree):
            contained_files.extend(get_files(item, ignore_patterns=ignore_patterns))

    return contained_files


def get_date_commits(
    repo: pygit2.Repository, target_date: datetime.date
) -> list[pygit2.Commit | None]:

    last = repo[repo.head.target]
    day_commits = []

    walker = repo.walk(last.id, pygit2.GIT_SORT_TIME)

    interval_min = datetime.datetime.combine(target_date, datetime.time.min)
    interval_max = datetime.datetime.combine(target_date, datetime.time.max)

    # get all commits from a given day, _plus_ one commit earlier
    # so that line comparison between files still works if a day
    # only has one commit

    for commit in dropwhile(lambda c: c.commit_time > interval_max.timestamp(), walker):

        if is_commit_on_date(commit, target_date):
            day_commits.append(commit)

        if commit.commit_time < interval_min.timestamp():
            day_commits.append(commit)
            break

    # if the earliest commit is on the target day, add a dummy None commit to signify
    # the line comparison betwen commits should start at 0,
    # not the value of the last commit
    if day_commits[-1].commit_time >= interval_min.timestamp():
        day_commits.append(None)

    return day_commits


def files_line_sum(
    commit: pygit2.Commit | None,
    ignore_patterns: list[str] | None = None,
    filetypes_db: dict[str, str] | None = None,
):

    if commit is None:
        return {}

    # TODO cleanup this logic
    if not filetypes_db:
        with open("filetypes.json", "r") as filetypes_file:
            filetypes_db = json.load(filetypes_file)

        assert filetypes_db

    commit_files = get_files(commit.tree, ignore_patterns=ignore_patterns)

    data_by_type: dict[str, int] = {}

    for file in commit_files:
        if not file.name:
            continue

        filename = file.name
        _, ext = splitext(filename)
        if not ext:
            continue

        cleaned_ext = ext.strip(".").lower()

        matched_filetype = filetypes_db.get(cleaned_ext, "Unknown")

        file_lines = sloc_from_text(filename, file.data)

        if not matched_filetype in data_by_type:
            data_by_type[matched_filetype] = file_lines
            continue

        data_by_type[matched_filetype] += file_lines

    return data_by_type


def counts_for_interval(
    repo: pygit2.Repository,
    start_date: datetime.date,
    end_date: datetime.date,
    ignore_patterns: list[str] | None = None,
) -> list[dict[datetime.date, dict[str, int]]]:  # type:ignore
    pass
