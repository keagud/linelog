import os
import sys
import re
from pathlib import Path
from itertools import pairwise
from itertools import takewhile, dropwhile
from functools import reduce
import datetime
from datetime import datetime as dt
from functools import cache
from mimetypes import guess_type
from functools import partial
import json
from os.path import splitext

from typing import NamedTuple

import pygit2

from sloc import sloc_from_text


class LineData(NamedTuple):
    language: str
    lines: int


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


def get_date_commits(repo: pygit2.Repository, target_date: datetime.date):

    last = repo[repo.head.target]
    day_commits: list[pygit2.Commit] = []

    walker = repo.walk(last.id, pygit2.GIT_SORT_TIME)

    interval_min = datetime.datetime.combine(target_date, datetime.time.min)
    interval_max = datetime.datetime.combine(target_date, datetime.time.max)

    for commit in dropwhile(lambda c: c.commit_time > interval_max.timestamp(), walker):

        if is_commit_on_date(commit, target_date):
            day_commits.append(commit)

        if commit.commit_time < interval_min.timestamp():
            day_commits.append(commit)
            break

    return day_commits


def files_line_sum(
    commit: pygit2.Commit,
    ignore_patterns: list[str] | None = None,
    filetypes_db: dict[str, str] | None = None,
):

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


def main():

    ignore_patterns = [r".*\.txt", r".*\.md"]

    target_path = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    repo = pygit2.Repository(target_path)

    with open("filetypes.json", "r") as exts_file:
        loaded_db = json.load(exts_file)

    loaded_linesum = partial(files_line_sum, filetypes_db=loaded_db)

    commit_blobs = {
        commit.id: {
            str(f.name): sloc_from_text("filename.ext", f.data)
            for f in get_files(commit.tree, ignore_patterns=ignore_patterns)
        }
        for commit in get_date_commits(repo, datetime.date(2023, 2, 18))
    }

    for k, v in commit_blobs.items():
        print(k)

        for file, sloc in v.items():
            g, _ = guess_type(file)
            print(f"{file} has {sloc} lines ({g})")


main()
