import yaml
import argparse
from pathlib import Path
from shutil import copyfile


def get_parser():
    cli_parser = argparse.ArgumentParser()
    cli_parser.add_argument("start_dir", nargs="?")
    cli_parser.add_argument("-", "--username", type=str)
    cli_parser.add_argument("-g", "--global-username", action="store_true")
    cli_parser.add_argument("-d", "--days", type=int, default=5)

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
            split_lines_config.update(
                {subentry: patterns for subentry in lang.split(",")}
            )

        config["lines"] = split_lines_config

    return config
