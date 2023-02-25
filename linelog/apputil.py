import argparse
import re

from importlib import resources
from os import getcwd
from pathlib import Path
from shutil import copyfile

import yaml

from .log_util import get_global_username


def get_parser():
    cli_parser = argparse.ArgumentParser()
    cli_parser.add_argument(
        "start_dir",
        nargs="?",
        default=getcwd(),
        help="The directory to scan. Defaults to the current working directory if unspecified",
    )
    cli_parser.add_argument(
        "-u",
        "--username",
        type=str,
        help="Limit the scan to commits by this username. If unspecified, the username set in the global git config file (if present) is used. If no username is given by either of these methods, or if the -c option is passed, all commits are considered regardless of author",
        default=get_global_username(),
    )
    cli_parser.add_argument(
        "-c",
        "--all-commits",
        action="store_true",
        help="Consider all commits by any user. Overrides the --username option if present.",
    )
    cli_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="If no repository is found in the given directory, search all subdirectories recursively and consider any repositories found there. If the top level directory is a repository, this does nothing.",
    )

    cli_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Start the scan in the home directory, and search all subdirectories for repositories. Same as 'linelog ~ -r'",
    )
    cli_parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=1,
        help="The number of days in the past to traverse when scanning a repository for relevant commits. If unspecified defaults to 1 (only today). The output graph is only generated if this is greater than one",
    )

    return cli_parser


def init_config():
    config_path = Path("~/.config/linelog/").expanduser().resolve()
    config_path.mkdir(exist_ok=True, parents=True)

    config_target = config_path.joinpath("config.yaml")

    init_config_handle = resources.files("linelog").joinpath("default_config.yaml")

    with resources.as_file(init_config_handle) as default_config:
        copyfile(default_config, config_target)


def read_config() -> dict:
    config_path = Path("~/.config/linelog/config.yaml").expanduser().resolve()
    if not config_path.exists():
        init_config()

    with open(config_path, "r") as config_file:
        config = yaml.full_load(config_file)

        config["patterns"] = frozenset(
            [re.compile(p) for p in config.get("patterns", [])]
        )

        lines_config: dict = config.get("lines", {})

        split_lines_config = {}

        for lang, patterns in lines_config.items():
            split_lines_config.update(
                {
                    subentry.strip()
                    .replace(" ", "-")
                    .lower(): [
                        re.compile(p, flags=re.MULTILINE | re.DOTALL)
                        for p in patterns
                        if p
                    ]
                    for subentry in lang.split(",")
                }
            )

        config["lines"] = split_lines_config
    return config
