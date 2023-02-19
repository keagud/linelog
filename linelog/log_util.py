import os
import sys
import re
from pathlib import Path
from itertools import pairwise
from functools import reduce
import datetime
from datetime import datetime as dt

import pygit2


def is_commit_on_date(commit, target_date: datetime.date) -> bool:

    interval_start = dt.combine(target_date, datetime.time.min)

    interval_end = dt.combine(target_date, datetime.time.max)

    return interval_start.timestamp() <= commit.commit_time <= interval_end.timestamp()


def get_date_commits(repo: pygit2.Repository, target_date: datetime.date):

    last = repo[repo.head.target]

    return [
        c
        for c in repo.walk(last.id, pygit2.GIT_SORT_TIME)
        if is_commit_on_date(c, target_date)
    ]


def get_files(repo: pygit2.Repository, tree_root: pygit2.Tree):

    contained_files: list[pygit2.Blob] = []
    for item in tree_root:
        if isinstance(item, pygit2.Blob):
            contained_files.append(item)

        elif isinstance(item, pygit2.Tree):
            contained_files.extend(get_files(repo, item))

    return contained_files


def main():

    ignore_patterns = ["*.txt"]

    target_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    repo = pygit2.Repository(target_path)

    # TODO diffing against the prev commit on a day fails when there's only one commit on a given day
    # should be the diffs on a day *plus one commit before*

    commit_blobs = [
        sorted(get_files(repo, commit.tree))
        for commit in get_date_commits(repo, datetime.date.today())
    ]


main()


def main_old():
    return None
    # exactly one line

    target_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    repo = pygit2.Repository(target_path)

    for commit_later, commit_earlier in pairwise(
        get_date_commits(repo, datetime.date.today())
    ):
        pair_diff = repo.diff(
            commit_earlier, commit_later, flags=pygit2.GIT_DIFF_IGNORE_WHITESPACE
        )

        for e in commit_later.tree:
            print(e.name)

        # not ideal...guys pls give diff a proper constructor
        # TODO continue on failure instead of aborting
        assert isinstance(pair_diff, pygit2.Diff)

        print(
            f'Between "{commit_earlier.message.strip()}" and "{commit_later.message.strip()}"'
        )

        totals = reduce(
            lambda acc, d: (a + s for a, s in zip(acc, d.line_stats)),
            pair_diff,
            (0, 0, 0),
        )

        print("Total diff: context: {} added: {}, deleted: {} \n\n".format(*totals))

    return None
