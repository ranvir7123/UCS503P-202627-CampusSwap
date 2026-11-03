"""How long things take: the normal times, or a fast demo where hours become minutes.

create_app() picks one for the whole process (run.py --demo picks DEMO), so a
live demo can show a whole swap, the reminder email and an automatic round
without waiting for hours. The rules are the same; only the clock is shorter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Timing:
    demo: bool
    confirm_window: timedelta  # time everyone in a chain has to answer
    remind_before: timedelta  # reminder email once this much time is left
    schedule_unit: timedelta  # what one step of the automatic-round interval means
    signin_window: timedelta  # how long failed sign-ins are remembered
    tick_seconds: int  # how often the background check runs

    def view(self) -> dict:
        return {"demo": self.demo, "confirm": _words(self.confirm_window), "reminder": _words(self.remind_before),
                "unit": _words(self.schedule_unit).split()[1].rstrip("s")}


def _words(span: timedelta) -> str:
    minutes = int(span.total_seconds() // 60)
    if minutes % 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''}"


NORMAL = Timing(demo=False, confirm_window=timedelta(hours=48), remind_before=timedelta(hours=12),
                schedule_unit=timedelta(hours=1), signin_window=timedelta(minutes=15), tick_seconds=30)
# Demo: the reminder comes 1 minute after a round and a chain closes after 3, so a
# whole swap, its reminder and an expiry fit into a 5-minute demo.
DEMO = Timing(demo=True, confirm_window=timedelta(minutes=3), remind_before=timedelta(minutes=2),
              schedule_unit=timedelta(minutes=1), signin_window=timedelta(minutes=1), tick_seconds=5)

_current = NORMAL


def current() -> Timing:
    return _current


def use(choice: Timing) -> None:
    global _current
    _current = choice
