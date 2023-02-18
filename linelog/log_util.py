import os
import sys
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


def main():
    # exactly one line

    target_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    repo = pygit2.Repository(target_path)

    for commit_later, commit_earlier in pairwise(
        get_date_commits(repo, datetime.date.today())
    ):
        pair_diff = repo.diff(commit_earlier, commit_later)

        # not ideal...guys pls give diff a proper constructor
        # TODO continue on failure instead of aborting
        assert isinstance(pair_diff, pygit2.Diff)

        print(f"Between {commit_earlier.message} and {commit_later.message}")

        totals = reduce(
            lambda acc, d: (a + s for a, s in zip(acc, d.line_stats)),
            pair_diff,
            (0, 0, 0),
        )

        print("Total diff: context: {} added: {}, deleted: {} \n\n".format(*totals))

    return None


main()
