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


if __name__ == "__main__":
    main()
