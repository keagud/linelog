#!/bin/env python
import argparse
from datetime import date, timedelta
from os import getcwd
import re
from re import Pattern
from pprint import pprint

from rich import print as rprint
from rich.console import Console

from log_util import RepoScanner, get_global_username
from plotter import make_figure
from plotter import make_table

cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("start_dir", nargs="?")
cli_parser.add_argument("-", "--username", type=str)
cli_parser.add_argument("-g", "--global-username", action="store_true")
cli_parser.add_argument("-d", "--days", type=int, default=5)


def main():
    args = cli_parser.parse_args()

    if args.start_dir is None:
        args.start_dir = getcwd()

    args.start_dir = "/home/k/Code"

    if args.global_username:
        username = get_global_username()

    elif args.username:
        username = args.username

    days_count = args.days

    start_date = date.today() - timedelta(days=days_count)
    end_date = date.today() + timedelta(days=1)

    ignore_extensions = ["txt", "md", "rst", "toml", "json", "yaml", "html", "yml", "tex"]

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

    console = Console()
    spinner = console.status("[green]Scanning repositories...", spinner="dots10")

    spinner.start()
    total_data = r.scan_path(args.start_dir, start_date, end_date)
    spinner.stop()

    if days_count > 1:

        fig = make_figure(total_data)
        fig.show()
        print(fig.show())

    table = make_table(total_data)
    rprint(table)


if __name__ == "__main__":
    main()
