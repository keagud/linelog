from datetime import date
from shutil import get_terminal_size

import plotille as pl
import pygit2
import rich


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

    fig.scatter(*format_for_plot(data), marker="*", lc="cyan")

    return fig




