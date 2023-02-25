# Linelog
## Summary

`linelog` is a CLI program that scans your local git repositories generates a summary of your total lines of code committed, broken down by language. For example, if I run `linelog -a` on my main desktop computer, it generates this:
![example-day](screenshots/linelog-example-day.png)

This isn't very exciting since I've not done much today (look, work-life balance is important.)  With the `-d` flag you can look back further in time, and see the results as a nice graph:
![example-2week](screenshots/linelog-example-2week.png)

*Hey, wait a second!*, you exclaim, *This very project has more than 651 lines of Python code, and most of it was committed in that very interval!* That's very astute of you, you have a real eagle eye. The discrepency comes from the fact that `linelog` does its best to count *logical* lines of code by skipping comments and whitespaces. You can customize what counts as a line for a given filetype; see the section on [configuration](https://github.com/keagud/linelog#the-config-file)


## Installation
### Arch Linux and kin (AUR)
`linelog` is on the Arch User Repository (AUR). You can get it in the usual manner with the AUR downloader of your choice:
```
$ yay -S linelog
```

### Other Linuxes/Unixes (Pip)
`linelog` is on PyPI. Install it with `pip` or `pipx`:
```
pipx install linelog
```

## Usage and Configuration

`linelog` uses this algorithm to count lines (simplified a bit):

- For the specified repository, iterate *pairwise* through all commits in the specified timeframe that have the specified author. 
- For each pair of sequential commits, apply the pattern matches specified in the config to count the total lines for each file. Then subtract the earlier line count from the later.
  - If the difference is *negative* (the later commit has fewer net lines), it is instead counted as zero. 
  This is essentially the only part of the counting behavior that the user cannot edit directly, both for technical and philosophical reasons. The point of `linelog` is to get a broad sense of productivity over a timespan, using lines of code written as a proxy. It is *not* meant to work as a diff generator - there are many many tools out there for that!
- Results for each filetype are collected and then summed for the final result. 

### Usage
A summary of available options is viewable with `linelog --help` 
```
usage: linelog [-h] [-u USERNAME] [-c] [-r] [-a] [-d DAYS] [start_dir]

positional arguments:
  start_dir             The directory to scan. Defaults to the current working
                        directory if unspecified

options:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        Limit the scan to commits by this username. If
                        unspecified, the username set in the global git config
                        file (if present) is used. If no username is given by
                        either of these methods, or if the -c option is
                        passed, all commits are considered regardless of
                        author
  -c, --all-commits     Consider all commits by any user. Overrides the
                        --username option if present.
  -r, --recursive       If no repository is found in the given directory,
                        search all subdirectories recursively and consider any
                        repositories found there. If the top level directory
                        is a repository, this does nothing.
  -a, --all             Start the scan in the home directory, and search all
                        subdirectories for repositories. Same as 'linelog ~
                        -r'
  -d DAYS, --days DAYS  The number of days in the past to traverse when
                        scanning a repository for relevant commits. If
                        unspecified defaults to 1 (only today). The output
                        graph is only generated if this is greater than one
```

### The Config File
`linelog` generates a config file at `~/.config/linelog/config.yaml` when run for the first time. The default config contains what I think are sensible defaults, but if you disagree you're free to change almost all of the line counting behavior. 

Config options take the form of regular expressions; when the program encounters a line that matches one of the expressions for a given filetype, it will not count it. See the comments in `config.yaml` for more details




