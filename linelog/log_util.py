import datetime
import json
import os
from collections import deque
import re
from datetime import date
from datetime import datetime as dt
from functools import reduce
from itertools import dropwhile, pairwise
from os import getcwd
from os.path import isdir, splitext
from pathlib import Path
from typing import Any

import pygit2

from sloc import sloc_from_text


def sum_dict_items(a: Any, b: Any):
    assert not (a is None and b is None)

    if a is None:
        return b

    if b is None:
        return a

    assert type(a) == type(b)

    if isinstance(a, int):
        return a + b

    assert isinstance(a, dict)

    common_keys = a.keys() | b.keys()

    return {k: sum_dict_items(a.get(k), b.get(k)) for k in common_keys}


def _is_commit_on_date(commit: pygit2.Commit, target_date: datetime.date) -> bool:
    interval_start = dt.combine(target_date, datetime.time.min)

    interval_end = dt.combine(target_date, datetime.time.max)

    return interval_start.timestamp() <= commit.commit_time <= interval_end.timestamp()


def _compare_commit_totals(
    earlier: dict[str, int], later: dict[str, int]
) -> dict[str, int]:
    return {k: max(v - earlier.get(k, 0), 0) for k, v in later.items()}


def _sum_dicts(d1: dict, d2: dict):
    assert type(d1) == type(d2)

    combiner = lambda x, y: x + y

    if type(d1) == dict[str, dict]:
        combiner = _sum_dicts

    combined = {k: d1.get(k, 0) + d2.get(k, 0) for k in d1.keys() | d2.keys()}

    # remove entries with a zero value
    return {k: combined[k] for k in combined if combined[k]}


def get_global_username() -> str:
    config = pygit2.Config.get_global_config()
    return config._get_entry("user.name").value


class RepoScanner:
    default_filetype_db = "filetypes.json"

    def __init__(
        self,
        username: str | None = None,
        filetypes_db_path: str | None = None,
        ignore_patterns: list[str] | None = None,
    ):
        if ignore_patterns is None:
            self.ignore_patterns = []

        else:
            self.ignore_patterns = ignore_patterns

        self.username = username

        self.filetypes_db_path = filetypes_db_path

        if self.filetypes_db_path is None:
            self.filetypes_db_path = self.default_filetype_db

        with open(self.filetypes_db_path, "r") as dbfile:
            self.filetypes_db = json.load(dbfile)

    def get_date_commits(
        self,
        repo: pygit2.Repository,
        target_date: datetime.date,
        user: str | None = None,
    ) -> list[pygit2.Commit | None]:
        if user is None:
            user = self.username

        try:
            last = repo[repo.head.target]

        except Exception as e:
            from pprint import pprint

            pprint(repo.path)
            raise e
            pass

        day_commits = []

        walker = repo.walk(last.id, pygit2.GIT_SORT_TIME)

        interval_min = datetime.datetime.combine(target_date, datetime.time.min)
        interval_max = datetime.datetime.combine(target_date, datetime.time.max)

        def compare_names(commit: pygit2.Commit, target_name: str | None) -> bool:
            if target_name is None:
                return True
            clean_author = commit.author.name.lower().strip()
            clean_target = target_name.lower().strip()

            return clean_author == clean_target

        # get all commits from a given day, _plus_ one commit earlier
        # so that line comparison between files still works if a day
        # only has one commit

        for commit in dropwhile(
            lambda c: c.commit_time > interval_max.timestamp(), walker
        ):
            if not compare_names(commit, user):
                continue

            if _is_commit_on_date(commit, target_date):
                day_commits.append(commit)

            if commit.commit_time < interval_min.timestamp():
                day_commits.append(commit)
                break

        # if the earliest commit is on the target day, add a dummy None commit to signify
        # the line comparison betwen commits should start at 0,
        # not the value of the last commit
        if not day_commits or day_commits[-1].commit_time >= interval_min.timestamp():
            day_commits.append(None)

        return day_commits

    def files_line_sum(
        self,
        repo: pygit2.Repository,
        commit: pygit2.Commit | None,
    ):
        if commit is None:
            return {}

        commit_files = self.get_tree_files(repo, commit.tree)

        data_by_type: dict[str, int] = {}

        for file in commit_files:
            if not file.name:
                continue

            filename = file.name
            _, ext = splitext(filename)
            if not ext:
                continue

            cleaned_ext = ext.strip(".").lower()

            matched_filetype: str | None = self.filetypes_db.get(cleaned_ext)

            if matched_filetype is None:
                continue

            file_lines = sloc_from_text(filename, file.data)

            if not matched_filetype in data_by_type:
                data_by_type[matched_filetype] = file_lines
                continue

            data_by_type[matched_filetype] += file_lines

        return data_by_type

    def get_repo_paths(self, start_path_str: str) -> list[pygit2.Repository]:
        def get_subdirs(p: Path):
            return list(filter(lambda x: x.is_dir(), p.iterdir()))

        start_path = Path(start_path_str).expanduser().resolve()
        start_dirs = get_subdirs(start_path)
        dirs_queue = deque(start_dirs)

        repos = []

        # it's our old friend, BFS!
        while dirs_queue:
            current_dir = dirs_queue.pop()

            assert current_dir.is_dir()

            # ignore hidden directories
            if current_dir.stem.startswith("."):
                continue

            if pygit2.discover_repository(str(current_dir)) is not None:
                repo = pygit2.Repository(current_dir)

                if repo.head_is_unborn:
                    continue

                repos.append(repo)
                continue

            dirs_queue.extendleft(get_subdirs(current_dir))
            

        return repos

    def file_ignored(self, filepath: str, repo: pygit2.Repository | None = None):
        if repo is not None and repo.path_is_ignored(filepath):
            return True

        matched_ignores = map(lambda p: re.match(p, filepath), self.ignore_patterns)
        return any(matched_ignores)

    def get_tree_files(
        self,
        repo: pygit2.Repository,
        tree_root: pygit2.Tree,
    ):
        contained_files: list[pygit2.Blob] = []
        for item in tree_root:
            if item.name is None:
                continue

            if self.file_ignored(item.name, repo=repo):
                continue

            if isinstance(item, pygit2.Blob) and not item.is_binary:
                contained_files.append(item)

            elif isinstance(item, pygit2.Tree):
                contained_files.extend(self.get_tree_files(repo, item))

        return contained_files

    def get_path_stats(
        self,
        path_root: Path | str,
        start_date: datetime.date,
        end_date: datetime.date | None,
    ) -> dict[datetime.date, dict[str, int]]:
        if isinstance(path_root, str):
            path_root = Path(path_root)

        assert path_root.is_dir()

        path_totals: dict[datetime.date, dict[str, int]] = {}

        if pygit2.discover_repository(str(path_root)) is None:
            for subdir in filter(lambda p: p.is_dir(), path_root.iterdir()):
                subdir_totals = self.get_path_stats(subdir, start_date, end_date)
                path_totals = sum_dict_items(path_totals, subdir_totals)

            return path_totals

        repo = pygit2.Repository(str(path_root))

        return self.get_repo_stats(repo, start_date, end_date)

    def get_repo_stats(
        self,
        repo: pygit2.Repository,
        start_date: datetime.date,
        end_date: datetime.date | None = None,
    ) -> dict[datetime.date, dict[str, int]]:
        if repo.head_is_unborn:
            return {}

        if end_date is None:
            end_date = start_date + datetime.timedelta(days=1)

        def iter_days(start: datetime.date, end: datetime.date):
            days = end.toordinal() - start.toordinal()

            iter_delta = datetime.timedelta(days=-1 if days < 0 else 1)

            iter_day = start

            while iter_day != end:
                yield iter_day
                iter_day += iter_delta

        totals: dict[datetime.date, dict[str, int]] = {}
        for d in iter_days(start_date, end_date):
            day_results = [
                self.files_line_sum(repo, c) for c in self.get_date_commits(repo, d)
            ]

            commit_line_changes = [
                _compare_commit_totals(e, l) for e, l in pairwise(reversed(day_results))
            ]

            totals[d] = reduce(_sum_dicts, commit_line_changes, {})

        return totals


def run():
    ignore_config = [r".*\.txt", r".*\.md", r".*\.rst", r".*\.toml", r".*\.json"]

    w = RepoScanner(ignore_patterns=ignore_config)
    current = getcwd()


if __name__ == "__main__":
    run()
