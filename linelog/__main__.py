#!/bin/env python
import argparse
from datetime import date, timedelta
from os import getcwd
from pprint import pprint

from rich.console import Console

from log_util import RepoScanner, get_global_username
from plotter import make_figure

cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("start_dir", nargs="?")
cli_parser.add_argument("-", "--username", type=str)
cli_parser.add_argument("-g", "--global-username", action="store_true")
cli_parser.add_argument("-d", "--days", type=int, default=5)


def main():

    ignore_config = [
        r".*\.txt",
        r".*\.md",
        r".*\.rst",
        r".*\.toml",
        r".*\.json",
        "Example/",
        "build/",
        "dist/",
    ]
    args = cli_parser.parse_args()

    if args.start_dir is None:
        args.start_dir = getcwd()

    args.start_dir = "/home/k/Code"

    username: str | None = None

    if args.global_username:
        username = get_global_username()

    elif args.username:
        username = args.username

    days_count = max(args.days, 3)

    start_date = date.today() - timedelta(days=days_count)
    end_date = date.today() + timedelta(days=1)

    r = RepoScanner(username=username, ignore_patterns=ignore_config)

    console = Console()
    spinner = console.status("[green]Scanning repositories...", spinner="arc")

    spinner.start()
    total_data = r.get_path_stats(args.start_dir, start_date, end_date)
    spinner.stop()

    fig = make_figure(total_data)
    fig.show()
    print(fig.show())

    pprint(total_data)


if __name__ == "__main__":
    main()
