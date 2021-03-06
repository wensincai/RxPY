import logging
from datetime import datetime
from typing import Optional
import threading

from rx.internal import PriorityQueue
from rx.internal.constants import DELTA_ZERO
from rx.core import typing
from rx.concurrency import ScheduledItem
from rx.concurrency.schedulerbase import SchedulerBase

pygame = None
log = logging.getLogger("Rx")


class PyGameScheduler(SchedulerBase):
    """A scheduler that schedules works for PyGame. Note that this class expects
    the caller to invoke run() repeatedly.

    http://www.pygame.org/docs/ref/time.html
    http://www.pygame.org/docs/ref/event.html"""

    def __init__(self):
        global pygame
        import pygame

        self._lock = threading.Lock()
        self._queue: PriorityQueue[ScheduledItem[typing.TState]] = PriorityQueue()

    def schedule(self,
                 action: typing.ScheduledAction,
                 state: Optional[typing.TState] = None
                 ) -> typing.Disposable:
        """Schedules an action to be executed.
        Args:
            action: Action to be executed.
            state: [Optional] state to be given to the action function.
        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """

        log.debug("PyGameScheduler.schedule(state=%s)", state)
        return self.schedule_absolute(self.now, action, state)

    def schedule_relative(self,
                          duetime: typing.RelativeTime,
                          action: typing.ScheduledAction,
                          state: Optional[typing.TState] = None
                          ) -> typing.Disposable:
        """Schedules an action to be executed after duetime.
        Args:
            duetime: Relative time after which to execute the action.
            action: Action to be executed.
            state: [Optional] state to be given to the action function.
        Returns:
            The disposable object used to cancel the scheduled action
            (best effort).
        """

        duetime = SchedulerBase.normalize(self.to_timedelta(duetime))
        return self.schedule_absolute(self.now + duetime, action, state=state)

    def schedule_absolute(self, duetime: typing.AbsoluteTime,
                          action: typing.ScheduledAction,
                          state: Optional[typing.TState] = None
                          ) -> typing.Disposable:
        """Schedules an action to be executed at duetime.

        Args:
            duetime: Absolute time after which to execute the action.
            action: Action to be executed.
            state: [Optional] state to be given to the action function.
        """

        duetime = self.to_datetime(duetime)
        si: ScheduledItem[typing.TState] = ScheduledItem(self, state, action, duetime)

        with self._lock:
            self._queue.enqueue(si)

        return si.disposable

    @property
    def now(self) -> datetime:
        """Represents a notion of time for this scheduler. Tasks being
        scheduled on a scheduler will adhere to the time denoted by
        this property."""

        return datetime.utcnow()

    def run(self) -> None:
        while self._queue:
            with self._lock:
                item: ScheduledItem[typing.TState] = self._queue.peek()
                diff = item.duetime - self.now

                if diff > DELTA_ZERO:
                    break

                item = self._queue.dequeue()

            if not item.is_cancelled():
                item.invoke()
