#!/bin/env python

import sys
from datetime import date, timedelta
from importlib.resources import as_file
from os import path

from rich import print as rprint
from rich.console import Console

from .apputil import get_parser, read_config
from .log_util import RepoScanner
from .plotter import make_figure, make_table


def run():
    cli_parser = get_parser()
    args = cli_parser.parse_args()

    config = read_config()

    days_count: int = args.days

    if args.all_commits:
        args.username = None

    if args.all:
        args.start_dir = path.expanduser("~")
        args.recursive = True

    if not path.exists(args.start_dir):
        rprint(f"[bold red]The path '{args.start_dir}' could not be resolved")
        sys.exit(1)

    start_date = date.today() - timedelta(days=days_count)
    end_date = date.today() + timedelta(days=1)

    scanner = RepoScanner(config, username=args.username)

    console = Console()
    spinner = console.status("[cyan]Scanning repositories...", spinner="dots")

    spinner.start()
    total_data = scanner.scan_path(
        args.start_dir, start_date, end_date, recursive=bool(args.recursive)
    )
    spinner.stop()

    if total_data is None:
        rprint(
            f"[bold red]No repositories could be found at {args.start_dir} \n(use the -r flag to search subdirectories)"
        )
        sys.exit(1)

    if days_count > 1:
        fig = make_figure(total_data)
        fig.show()
        print(fig.show())

    table = make_table(total_data)
    rprint(table)


if __name__ == "__main__":
    run()
