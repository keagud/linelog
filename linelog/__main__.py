import json
import datetime

import argparse
from itertools import pairwise
from functools import partial
from functools import reduce

import pygit2

from log_util import files_line_sum
from log_util import get_date_commits


cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("start_dir")
cli_parser.add_argument("-w", "--week", action="store_true")


def main():

    args = cli_parser.parse_args()

    def compare_commit_totals(
        earlier: dict[str, int], later: dict[str, int]
    ) -> dict[str, int]:

        return {k: max(v - earlier.get(k, 0), 0) for k, v in later.items()}

    def sum_dicts(d1: dict, d2: dict):
        return {k: d1.get(k, 0) + d2.get(k, 0) for k in d1.keys() | d2.keys()}

    ignore_patterns = [r".*\.txt", r".*\.md", r".*\.rst", r".*\.json", r".*\.toml"]

    target_path = args.start_dir

    repo = pygit2.Repository(target_path)

    with open("filetypes.json", "r") as exts_file:
        loaded_db = json.load(exts_file)

    loaded_linesum = partial(files_line_sum, filetypes_db=loaded_db)

    commit_blobs = [
        loaded_linesum(commit, ignore_patterns=ignore_patterns)
        for commit in get_date_commits(repo, datetime.date.today())
    ]

    commit_line_changes = [
        compare_commit_totals(e, l) for e, l in pairwise(reversed(commit_blobs))
    ]
    line_totals = reduce(sum_dicts, commit_line_changes, {})

    for k, v in line_totals.items():
        print(f"{k} +{v}")


if __name__ == "__main__":
    main()
