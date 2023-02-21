import re
from itertools import dropwhile
import datetime
from datetime import date, datetime as dt
import json
from os.path import splitext
from os import PathLike, getcwd
from typing import NamedTuple

from functools import partial
from functools import reduce
from itertools import pairwise


import pygit2

from sloc import sloc_from_text


def is_commit_on_date(commit: pygit2.Commit, target_date: datetime.date) -> bool:

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
    if not day_commits or day_commits[-1].commit_time >= interval_min.timestamp():
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


def compare_commit_totals(
    earlier: dict[str, int], later: dict[str, int]
) -> dict[str, int]:

    return {k: max(v - earlier.get(k, 0), 0) for k, v in later.items()}


def sum_dicts(d1: dict, d2: dict):
    combined = {k: d1.get(k, 0) + d2.get(k, 0) for k in d1.keys() | d2.keys()}

    # remove entries with a zero value
    return {k: combined[k] for k in combined if combined[k]}


# TODO maybe it makes more sense for this to be wrapped up in a class?
def get_interval_repo_lines_custom(
    repo: pygit2.Repository,
    start_date: datetime.date,
    end_date: datetime.date | None = None,
    ignore_patterns: list[str] | None = None,
    filetypes_db: dict[str, str] | None = None,
) -> dict[datetime.date, dict[str, int]]:

    if filetypes_db is None:
        with open("filetypes.json", "r") as ftypes:
            filetypes_db = json.load(ftypes)
            assert filetypes_db

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
            files_line_sum(
                c, ignore_patterns=ignore_patterns, filetypes_db=filetypes_db
            )
            for c in get_date_commits(repo, d)
        ]

        commit_line_changes = [
            compare_commit_totals(e, l) for e, l in pairwise(reversed(day_results))
        ]

        totals[d] = reduce(sum_dicts, commit_line_changes, {})

    return totals


def _load_file_config():
    with open("filetypes.json", "r") as exts_file:
        loaded_db = json.load(exts_file)

    return loaded_db


def _get_ignore_config():
    # TODO this should read from an external config yaml eventually
    ignore_config = [r".*\.txt", r".*\.md", r".*\.rst", r".*\.toml", r".*\.json"]
    return ignore_config


get_interval_repo_lines = partial(
    get_interval_repo_lines_custom,
    ignore_patterns=_get_ignore_config(),
    filetypes_db=_load_file_config(),
)


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
        if self.username is None:
            self.username = get_global_username()

        self.filetypes_db_path = filetypes_db_path

        if self.filetypes_db_path is None:
            self.filetypes_db_path = self.default_filetype_db

        with open(self.filetypes_db_path, "r") as dbfile:
            self.filetypes_db = json.load(dbfile)

    def load_file_config(self):
        pass

    def get_repo_lines(self, repo: pygit2.Repository):
        pass

    def files_line_sum(
        self,
        commit: pygit2.Commit | None,
    ):

        if commit is None:
            return {}

        commit_files = self.get_tree_files(commit.tree)

        data_by_type: dict[str, int] = {}

        for file in commit_files:
            if not file.name:
                continue

            filename = file.name
            _, ext = splitext(filename)
            if not ext:
                continue

            cleaned_ext = ext.strip(".").lower()

            matched_filetype = self.filetypes_db.get(cleaned_ext, "Unknown")

            file_lines = sloc_from_text(filename, file.data)

            if not matched_filetype in data_by_type:
                data_by_type[matched_filetype] = file_lines
                continue

            data_by_type[matched_filetype] += file_lines

        return data_by_type

    def get_tree_files(
        self,
        tree_root: pygit2.Tree,
    ):
        contained_files: list[pygit2.Blob] = []
        for item in tree_root:

            if item.name is None:
                continue

            matched_ignores = map(
                lambda p: re.match(p, str(item.name)), self.ignore_patterns
            )

            if any(matched_ignores):
                continue

            if isinstance(item, pygit2.Blob) and not item.is_binary:
                contained_files.append(item)

            elif isinstance(item, pygit2.Tree):
                contained_files.extend(self.get_tree_files(item))

        return contained_files

    def get_repo_stats(
        self,
        repo: pygit2.Repository | str,
        start_date: datetime.date,
        end_date: datetime.date | None = None,
    ) -> dict[datetime.date, dict[str, int]]:


        if isinstance(repo, str):
            repo = pygit2.Repository(repo)


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

            day_results = [files_line_sum(c) for c in get_date_commits(repo, d)]

            commit_line_changes = [
                compare_commit_totals(e, l) for e, l in pairwise(reversed(day_results))
            ]

            totals[d] = reduce(sum_dicts, commit_line_changes, {})

        return totals


def run():

    ignore_config = [r".*\.txt", r".*\.md", r".*\.rst", r".*\.toml", r".*\.json"]

    w = RepoScanner(ignore_patterns=ignore_config)
    current = getcwd()

    s= w.get_repo_stats(current, date(2023, 2,19))
    print(s)
    


if __name__ == "__main__":
    run()
