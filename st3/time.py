import datetime
from time import sleep  # noqa: to prevent namespace clashes


# WSL2 time desync fix: sudo hwclock -s
# fix source: https://stackoverflow.com/questions/65086856/wsl2-clock-is-out-of-sync-with-windows
# git issue:  https://github.com/microsoft/WSL/issues/10006
def now():
    """current time (UTC) as a datetime object"""
    return datetime.datetime.now(datetime.timezone.utc)


def read(t: str):
    """from ISO 8601 format string to datetime"""
    return datetime.datetime.fromisoformat(t)


def write(t: datetime.datetime = None):
    """from datetime to ISO 8601 format string"""
    if t is None:
        t = now()
    return f"{t.isoformat()[:23]}Z"


def remaining(t: str or datetime.datetime):
    """in seconds"""
    if isinstance(t, str):
        t = read(t)
    t = max(0.0, (t - now()).total_seconds())
    return t


def pretty(t: int or float):
    """round time to the largest unit (hours/minutes/seconds)"""
    if t > 3600:
        t = t / 3600
        u = "hrs"
    elif t > 60:
        t = t / 60
        u = "min"
    else:
        u = "sec"
    return f"{round(t, 2):.02f} {u!s}"


def total(t: int or float):
    """convert time to hh:mm:ss"""
    t = round(t)
    h = t // 3600
    t = t - h * 3600
    m = t // 60
    t = t - m * 60
    s = t // 1
    return f"{h:02d}:{m:02d}:{s:02d}"
