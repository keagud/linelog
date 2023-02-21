import pygit2
import plotille as pl

from datetime import date
from shutil import get_terminal_size

from log_util import get_interval_repo_lines


from os import getcwd


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
    fig.width = term_width // 2
    fig.height = term_height // 3

    fig.set_y_limits(min_=0)
    fig.set_x_limits(min_=min(data))

    fig.register_label_formatter(date, date_formatter)

    fig.x_label = "date"
    fig.y_label = "lines"

    fig.origin = False

    fig.register_label_formatter(float, linescount_formatter)

    fig.plot(*format_for_plot(data), marker="*", lc="cyan")

    return fig


def main():

    repo = pygit2.Repository(getcwd())

    d = get_interval_repo_lines(repo, date.today(), date(2023, 2, 15))

    s = make_figure(d)
    print(s.show())


main()
