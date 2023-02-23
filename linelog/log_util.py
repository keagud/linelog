import pygit2
from pygit2 import Repository, Commit, Blob, Tree
import re
from re import Pattern
from typing import Callable, Any
from typing import NamedTuple
import datetime
from datetime import date
from pathlib import Path
from itertools import dropwhile
from functools import reduce, partial
import os
from os.path import splitext
import json
from pprint import pprint
from itertools import pairwise
from collections import deque
from copy import deepcopy
import multiprocessing
from concurrent import futures


def get_global_username() -> str:
    config = pygit2.Config.get_global_config()
    return config._get_entry("user.name").value


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

    return {k: v for k in common_keys if (v := sum_dict_items(a.get(k), b.get(k)))}


def sloc_from_text(
    src_text: str | bytes, line_spec: list[Pattern], min_chars: int
) -> int:
    try:
        if isinstance(src_text, bytes):
            src_text = src_text.decode()
    except UnicodeDecodeError:
        return 0

    # get rid of c -style /**/ comments

    for pattern in line_spec:
        src_text = re.sub(pattern, "", src_text)

    # get lines with 2 or more non-whitespace characters
    valid_lines = [line for line in src_text.splitlines() if len(line) > min_chars]

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

        filetype_ignores = ignore_config["lines"].get("any", [])
        filetype_ignores_ext = ignore_config["lines"].get(cleaned_ext, [])

        filetype_ignores.extend(filetype_ignores_ext)

        file_lines = sloc_from_text(file.data, filetype_ignores, 2)

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
        totals = sum_dict_items(totals, s)

    return totals


def get_date_commits(
    repo: pygit2.Repository,
    target_date: date,
    user: str,
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

    #import pdb; pdb.set_trace()

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


def get_interval_commits(repo: Repository, start_date: date, end_date: date, user: str):
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
    user: str,
    filetypes_db: dict[str, str],
    ignore_config: dict[str, Any],
) -> dict[date, dict[str, int]]:
    if isinstance(repo, Path):
        repo = pygit2.Repository(repo)

    interval_commits = get_interval_commits(repo, start_date, end_date, user)

    stats = partial(
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
            day_total = sum_dict_items(day_total, combined)

        totals[d] = day_total

    return totals


class RepoScanner:
    def __init__(self, username: str, ignore_config: dict):
        with open("filetypes.json", "r") as filetypes_file:
            self.filetypes_db = json.load(filetypes_file)

        self.ignore_config = ignore_config

        self.username = username

    def find_repo_paths(self, startpath_str: str) -> list[Path]:
        startpath = Path(startpath_str).expanduser().resolve()

        def get_subdirs(p: Path):
            return list(filter(lambda x: x.is_dir(), p.iterdir()))

        start_dirs = get_subdirs(startpath)
        dirs_queue = deque(start_dirs)

        repos = []

        while dirs_queue:
            current_dir = dirs_queue.pop()


            assert current_dir.is_dir()

            if current_dir.stem.startswith('.'):
                continue

            if pygit2.discover_repository(str(current_dir)) is not None:
                repo = pygit2.Repository(current_dir)

                if repo.head_is_unborn:
                    continue

                repos.append(current_dir)
                continue

            dirs_queue.extendleft(get_subdirs(current_dir))

        return repos

    def make_finder(self, path: Path, start_date: date, end_date: date):
        username = deepcopy(self.username)

        filetypes_db = deepcopy(self.filetypes_db)
        ignore_config = deepcopy(self.ignore_config)

        return partial(
            get_interval_stats,
            path,
            start_date,
            end_date,
            username,
            filetypes_db,
            ignore_config,
        )

    def scan_path(self, start_dir: str, start_date: date, end_date: date):
        repos = self.find_repo_paths(start_dir)

        sf = partial(self.make_finder, start_date=start_date, end_date=end_date)

        with futures.ProcessPoolExecutor() as executor:
            results = reduce(sum_dict_items, (s() for s in executor.map(sf, repos)))
        return results


#        pprint(results)


def main():
    ignore_extensions = [
        "txt",
        "md",
        "rst",
        "toml",
        "json",
        "yml",
    ]

    ignore_patterns = [
        "Example/",
        "build/",
        "dist/",
    ]

    line_patterns_any = [r"/\*.*\*/", r"^\s*#$", r"^\s*$", r"#.*$"]

    test_ignore_config = {
        "extensions": ignore_extensions,
        "patterns": [re.compile(p) for p in ignore_patterns],
        "lines": {
            "any": [re.compile(p, flags=re.MULTILINE) for p in line_patterns_any]
        },
    }

    r = RepoScanner("keagud", test_ignore_config)

    r.scan_path("~", date(2023, 2, 15), date.today())


if __name__ == "__main__":
    main()
