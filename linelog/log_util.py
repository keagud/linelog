import datetime
import json
import re
import collections
from concurrent import futures
from datetime import date
import functools
from functools import reduce
from importlib import resources
from itertools import dropwhile, pairwise
from os.path import splitext
from pathlib import Path
from re import Pattern
from typing import Any

import pygit2
from pygit2 import Blob, Commit, GitError, Repository, Tree


def get_global_username() -> str | None:
    try:
        config = pygit2.Config.get_global_config()
        return config._get_entry("user.name").value
    except GitError | KeyError:
        return None


@functools.singledispatch
def sum_dict_items(a: int | dict, b: int | dict) -> dict | int:
    if not (a is None and b is None):
        if a is None:
            return b

        if b is None:
            return a

    return {}


@sum_dict_items.register
def _(a: dict, b: dict) -> dict:
    common_keys = a.keys() | b.keys()
    return {k: v for k in common_keys if (v := sum_dict_items(a.get(k), b.get(k)))}


@sum_dict_items.register
def _(a: int, b: int) -> int:
    # TODO gotta be a better way to express this
    if a is None:
        return b
    if b is None:
        return a

    return a + b


def sum_dicts(a: dict, b: dict) -> dict:
    common_keys = a.keys() | b.keys()
    return {k: v for k in common_keys if (v := sum_dict_items(a.get(k), b.get(k)))}


@functools.cache
def sloc_from_text(src_text: str | bytes, line_spec: frozenset[Pattern]) -> int:
    try:
        if isinstance(src_text, bytes):
            src_text = src_text.decode()
    except UnicodeDecodeError:
        return 0

    for pattern in (p for p in line_spec if p):
        src_text = re.sub(pattern, "", src_text)

    valid_lines = [line for line in src_text.splitlines() if line]

    return len(valid_lines)


def get_tree_files(
    repo: pygit2.Repository,
    tree_root: pygit2.Tree,
    ignore_config: dict,
) -> list[Blob]:
    contained_files: list[pygit2.Blob] = []
    for item in tree_root:
        filename = item.name

        if filename is None:
            continue

        _, ext = splitext(filename)

        ext = ext.strip(".")
        if ext in ignore_config.get("extensions", []):
            continue

        if repo is not None and repo.path_is_ignored(filename):
            continue

        ignore_patterns = ignore_config.get("patterns", [])

        matched_ignore_patterns = map(
            lambda p: re.match(p, str(filename)), ignore_patterns
        )

        if any(matched_ignore_patterns):
            continue

        if isinstance(item, Blob) and not item.is_binary:
            contained_files.append(item)

        elif isinstance(item, Tree):
            contained_files.extend(get_tree_files(repo, item, ignore_config))

    return contained_files


def blob_stats(
    files: list[pygit2.Blob],
    filetypes_db: dict[str, str],
    ignore_config: dict[str, Any],
) -> dict[str, int]:
    data_by_type: dict[str, int] = {}

    for file in files:
        if not file.name:
            continue

        filename = file.name
        _, ext = splitext(filename)
        if not ext:
            continue

        cleaned_ext = ext.strip(".").lower()

        matched_filetype: str | None = filetypes_db.get(cleaned_ext)

        if matched_filetype is None:
            continue

        filetype_key = matched_filetype.replace(" ", "-").lower()

        filetype_ignores = ignore_config["lines"].get("any", [])
        filetype_ignores_ext = ignore_config["lines"].get(filetype_key, [])

        filetype_ignores.extend(filetype_ignores_ext)

        file_lines = sloc_from_text(file.data, frozenset(filetype_ignores))

        if not matched_filetype in data_by_type:
            data_by_type[matched_filetype] = file_lines
            continue

        data_by_type[matched_filetype] += file_lines

    return data_by_type


def get_commit_stats(
    repo: Repository,
    commit: Commit | None,
    filetypes_db: dict,
    ignore_config: dict[str, Any],
) -> dict[str, int]:
    if commit is None:
        return {}

    files = get_tree_files(repo, commit.tree, ignore_config)

    blob_stats_list = [blob_stats(files, filetypes_db, ignore_config)]

    totals = {}

    for s in blob_stats_list:
        totals: dict = sum_dicts(totals, s)

    return totals


def get_date_commits(
    repo: pygit2.Repository,
    target_date: date,
    user: str | None,
) -> list[pygit2.Commit | None]:
    last = repo[repo.head.target]
    day_commits = []

    walker = repo.walk(last.id, pygit2.GIT_SORT_TIME)

    interval_min = datetime.datetime.combine(target_date, datetime.time.min)
    interval_max = datetime.datetime.combine(target_date, datetime.time.max)

    def is_commit_on_date(commit: pygit2.Commit, target_date: datetime.date) -> bool:
        interval_start = datetime.datetime.combine(target_date, datetime.time.min)

        interval_end = datetime.datetime.combine(target_date, datetime.time.max)

        return (
            interval_start.timestamp() <= commit.commit_time <= interval_end.timestamp()
        )

    def compare_names(commit: pygit2.Commit, target_name: str | None) -> bool:
        if target_name is None:
            return True
        clean_author = commit.author.name.lower().strip()
        clean_target = target_name.lower().strip()

        return clean_author == clean_target

    # get all commits from a given day, _plus_ one commit earlier
    # so that line comparison between files still works if a day
    # only has one commit

    for commit in dropwhile(lambda c: c.commit_time > interval_max.timestamp(), walker):
        if not compare_names(commit, user):
            continue
        if is_commit_on_date(commit, target_date):
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


def get_interval_commits(
    repo: Repository, start_date: date, end_date: date, user: str | None
):
    def iter_days(start: datetime.date, end: datetime.date):
        days = end.toordinal() - start.toordinal()

        iter_delta = datetime.timedelta(days=-1 if days < 0 else 1)

        iter_day = start

        while iter_day != end:
            yield iter_day
            iter_day += iter_delta

    return {d: get_date_commits(repo, d, user) for d in iter_days(start_date, end_date)}


def get_interval_stats(
    repo: Repository | Path,
    start_date: date,
    end_date: date,
    user: str | None,
    filetypes_db: dict[str, str],
    ignore_config: dict[str, Any],
) -> dict[date, dict[str, int]]:
    if isinstance(repo, Path):
        repo = pygit2.Repository(repo)

    interval_commits = get_interval_commits(repo, start_date, end_date, user)

    stats = functools.partial(
        get_commit_stats,
        repo=repo,
        filetypes_db=filetypes_db,
        ignore_config=ignore_config,
    )

    def sum_stats(earlier_stats: dict[str, int], later_stats: dict[str, int]):
        keys = earlier_stats.keys() | later_stats.keys()

        return {
            k: max(later_stats.get(k, 0) - earlier_stats.get(k, 0), 0) for k in keys
        }

    totals = {}
    for d, l in interval_commits.items():
        day_total: dict[str, int] = {}

        for earlier, later in pairwise(reversed(l)):
            combined = sum_stats(stats(commit=earlier), stats(commit=later))
            day_total = sum_dicts(day_total, combined)

        totals[d] = day_total

    return totals


class RepoScanner:
    def __init__(self, ignore_config: dict, username: str | None = None):
        filetype_data_ref = resources.files("linelog").joinpath("filetypes.json")

        with filetype_data_ref.open("r") as filetypes_file:
            self.filetypes_db = json.load(filetypes_file)

        self.ignore_config = ignore_config

        self.username = username

    def find_repo_paths(self, startpath_str: str, recursive: bool = True) -> list[Path]:
        startpath = Path(startpath_str).expanduser().resolve()

        def get_subdirs(p: Path):
            return list(filter(lambda x: x.is_dir(), p.iterdir()))

        dirs_queue = collections.deque([startpath])

        repos = []

        while dirs_queue:
            current_dir = dirs_queue.pop()

            assert current_dir.is_dir()

            if current_dir.stem.startswith("."):
                continue

            if pygit2.discover_repository(str(current_dir)) is not None:
                repo = pygit2.Repository(current_dir)

                if repo.head_is_unborn:
                    continue

                repos.append(current_dir)
                continue

            if recursive:
                dirs_queue.extendleft(get_subdirs(current_dir))

        return repos

    def make_finder(self, path: Path, start_date: date, end_date: date):
        username = self.username

        filetypes_db = self.filetypes_db
        ignore_config = self.ignore_config

        return functools.partial(
            get_interval_stats,
            path,
            start_date,
            end_date,
            username,
            filetypes_db,
            ignore_config,
        )

    def scan_path(
        self, start_dir: str, start_date: date, end_date: date, recursive: bool = True
    ) -> dict[date, dict[str, int]] | None:
        repos = self.find_repo_paths(start_dir, recursive=recursive)

        if not repos:
            return None

        def eval_repo(r):
            f = functools.partial(
                self.make_finder, start_date=start_date, end_date=end_date
            )
            return f(r)()

        #        res = map(eval_repo, repos)
        #        return reduce(sum_dict_items, res)

        with futures.ProcessPoolExecutor() as executor:
            repo_futures = []
            for r in repos:
                f = self.make_finder(r, start_date, end_date)
                x = executor.submit(f)
                repo_futures.append(x)

        results = reduce(
            sum_dicts, (r.result() for r in futures.as_completed(repo_futures))
        )

        return results
