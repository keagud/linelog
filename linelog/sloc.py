import re

# TODO make this a configurable yaml or json
DEFAULT_CONFIG = {
    "ignore-extensions": ["md", "rst", "toml", "json"],
    "ignore_file_patterns": [],
    "ignore-by-extension": {"all": [], "py": [r"#.*$"]},
    "ignore-multiline": {"c(pp)?": [r"/\*.*\\"]},
}

MIN_CHARS = 2


def sloc_from_text(_: str, src_text: str | bytes) -> int:

    try:
        if isinstance(src_text, bytes):
            src_text = src_text.decode()
    except UnicodeDecodeError:
        return 0

    # get rid of c -style /**/ comments

    src_text = re.sub(r"/\*.*\*/", "", src_text, flags=re.MULTILINE)

    # strip whitespace and single line comments
    src_lines = [
        re.sub(r"\s+", "", line)
        for line in src_text.split("\n")
        if not re.match(r"\s*[(//)|#]", line)
    ]

    # get lines with 2 or more non-whitespace characters
    valid_lines = [line for line in src_lines if len(line) > MIN_CHARS]

    return len(valid_lines)
