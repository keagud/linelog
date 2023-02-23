#!/bin/env python

from datetime import date, timedelta
from os import getcwd
import re
from re import Pattern
from pprint import pprint

from rich import print as rprint
from rich.console import Console

from log_util import RepoScanner, get_global_username
from apputil import get_parser, read_config
from plotter import make_figure
from plotter import make_table


def main():
    cli_parser = get_parser()
    args = cli_parser.parse_args()

    if args.start_dir is None:
        args.start_dir = getcwd()

    

    if args.username:
        username = args.username

    else: 
        username = get_global_username()


    config = read_config()

    days_count = args.days

    days_count = 10
    args.start_dir = "/home/k"

    start_date = date.today() - timedelta(days=days_count)
    end_date = date.today() + timedelta(days=1)

    r = RepoScanner(username, config)

    console = Console()
    spinner = console.status("[cyan]Scanning repositories...", spinner="dots")

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
