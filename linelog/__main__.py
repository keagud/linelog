#!/bin/env python
import argparse
from datetime import date

from os import getcwd

import pygit2

from log_util import RepoScanner
from log_util import get_global_username

cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("start_dir", nargs="?")
# cli_parser.add_argument("-w", "--week", action="store_true")
cli_parser.add_argument("-r", "--recurse", action="store_true")
cli_parser.add_argument("-", "--username", type=str)
cli_parser.add_argument("-g", "--global-username", action="store_true")


def main():

    ignore_config = [r".*\.txt", r".*\.md", r".*\.rst", r".*\.toml", r".*\.json"]
    args = cli_parser.parse_args()

    if args.start_dir is None:
        args.start_dir = getcwd()

    username: str | None = None

    if args.global_username:
        username = get_global_username()

    elif args.username:
        username = args.username

    r = RepoScanner(username=username, ignore_patterns=ignore_config)
    s = r.get_repo_stats(args.start_dir, date.today())
    print(s)


if __name__ == "__main__":
    main()
