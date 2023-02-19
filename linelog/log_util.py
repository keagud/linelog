import os
import sys
import re
from pathlib import Path
from itertools import pairwise
from functools import reduce
import datetime
from datetime import datetime as dt
from functools import cache
from mimetypes import guess_type

import pygit2

from sloc import sloc_from_text


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


def get_files(
    repo: pygit2.Repository,
    tree_root: pygit2.Tree,
    ignore_patterns: list[str] | None = None,
):

    contained_files: list[pygit2.Blob] = []
    for item in tree_root:
        

        # TODO this is screwey
        if ignore_patterns and (
            any(map(lambda p: re.match(p, str(item.name)), ignore_patterns))
        ):
            continue

        if isinstance(item, pygit2.Blob) and not item.is_binary:
            contained_files.append(item)

        elif isinstance(item, pygit2.Tree):
            contained_files.extend(
                get_files(repo, item, ignore_patterns=ignore_patterns)
            )

    return contained_files


def main():

    ignore_patterns = [r".*\.txt", r".*\.md"]

    # target_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    target_path = Path("~/Code/C-Studies").expanduser().resolve()
    repo = pygit2.Repository(target_path)

    # TODO diffing against the prev commit on a day fails when there's only one commit on a given day
    # should be the diffs on a day *plus one commit before*

    commit_blobs = {
        commit.id: {
            str(f.name): sloc_from_text("filename.ext", f.data)
            for f in get_files(repo, commit.tree, ignore_patterns=ignore_patterns)
        }
        for commit in get_date_commits(repo, datetime.date.today())
    }

    for k, v in commit_blobs.items():
        print(k)

        for file, sloc in v.items():
            g, _ = guess_type(file)
            print(f"{file} has {sloc} lines ({g})")


main()
