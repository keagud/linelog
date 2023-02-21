#!/bin/env python
import argparse

from os import getcwd

import pygit2

from log_util import get_interval_repo_lines
from plotter import make_figure


cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("start_dir", nargs="?")
# cli_parser.add_argument("-w", "--week", action="store_true")
cli_parser.add_argument("-r", "--recurse", action="store_true")


def main():

    args = cli_parser.parse_args()

    if args.start_dir is None:
        args.start_dir = getcwd()


if __name__ == "__main__":
    main()
