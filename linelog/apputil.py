import yaml
import argparse
from pathlib import Path
from os import getcwd
from shutil import copyfile


def get_parser():
    cli_parser = argparse.ArgumentParser()
    cli_parser.add_argument("start_dir", nargs="?", default=getcwd(), help="The directory to scan. Defaults to the current working directory if unspecified")
    cli_parser.add_argument("-u", "--username", type=str, help="Limit the scan to commits by this username. If unspecified, the username set in the global git config file (if present) is used. If no username is given by either of these methods, or if the -c option is passed, all commits are considered regardless of author")
    cli_parser.add_argument("-c", "--all-commits", action="store_true", help="Consider all commits by any user. Overrides the --username option if present.")
    cli_parser.add_argument('-r', "--recursive",action="store_true", help="")

    cli_parser.add_argument("-a", "--all", help="Start the scan in the home directory, and search all subdirectories for repositories. Same as 'linelog ~ -r'")
    cli_parser.add_argument("-d", "--days", type=int, default=1, help="The number of days in the past to traverse when scanning a repository for relevant commits. If unspecified defaults to 1 (only today). The output graph is only generated if this is greater than one")

    return cli_parser


def init_config():
    config_path = Path("~/.config/linelog/").expanduser().resolve()
    config_path.mkdir(exist_ok=True, parents=True)

    config_target = config_path.joinpath("config.yaml")

    copyfile("default_config.yaml", config_target)


def read_config() -> dict:
    config_path = Path("~/.config/linelog/config.yaml").expanduser().resolve()
    if not config_path.exists():
        init_config()

    with open(config_path, "r") as config_file:
        config = yaml.full_load(config_file)

        lines_config: dict = config.get("lines", {})

        split_lines_config = {}

        for lang, patterns in lines_config.items():
            print(lang)
            split_lines_config.update(
                {
                    subentry.replace(" ", "-").lower(): patterns
                    for subentry in lang.split(",")
                }
            )

        config["lines"] = split_lines_config

    return config
