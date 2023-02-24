from datetime import date
from functools import reduce
from shutil import get_terminal_size

import plotille as pl
from rich.table import Table

from .log_util import sum_dicts


def format_for_plot(data: dict[date, dict[str, int]]):
    dates = []
    date_info = []

    for d, i in data.items():
        dates.append(d)
        date_info.append(sum(i.values()))

    return (dates, date_info)


def date_formatter(val: date, chars: int, delta, left: bool = False):
    date_str = f"{val.month}/{val.day}"
    return "{0:{1}s}".format(date_str, chars, "<" if left else "")


def linescount_formatter(val: int, chars: int, delta, left: bool = False):
    return "{0:^10d}".format(int(val))


def make_figure(data: dict[date, dict[str, int]]) -> pl.Figure:
    fig = pl.Figure()

    term_width, term_height = get_terminal_size()
    fig.width = min(term_width // 2, (len(data) * 8))
    fig.height = term_height // 3

    fig.set_y_limits(min_=0)

    if not min(data) == max(data):
        fig.set_x_limits(min_=min(data), max_=max(data))

    fig.register_label_formatter(date, date_formatter)
    fig.y_label = "lines"

    fig.origin = True

    fig.register_label_formatter(float, linescount_formatter)

    fig.scatter(*format_for_plot(data), marker="+", lc="cyan")

    return fig


def make_table(data: dict[date, dict[str, int]]):
    total_lines = sum([sum(d.values()) for d in data.values()])

    language_totals = reduce(sum_dicts, data.values())

    table = Table(show_header=True, header_style="bold green")
    table.add_column("Language")
    table.add_column("Lines")
    table.add_column("Proportion", style="dim italic")

    lang_tuples = [(k, v) for k, v in language_totals.items()]

    lang_tuples.sort(key=lambda x: x[1], reverse=True)

    for language, lines in lang_tuples:
        prop = f"{(lines / total_lines) * 100:.2f}%"
        table.add_row(f"[dim]{language}", f"[dim]{lines}", prop)

    linestr = str(total_lines)

    table.add_row("[default][bold cyan]Total", f"[bold]{linestr}", "")

    return table
