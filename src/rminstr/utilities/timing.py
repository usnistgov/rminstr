"""Module for timing related objects."""

import time as _time

__all__ = ['Timer']


class Timer:
    """
    Simple timer class for making getting relative times.

    An instance of a timer class stores its time of initialization. Calling
    the class instance returns its time since
    initialization.

    Attributes
    ----------
    t0 : float
        Absolute time at initialization of class in seconds.

    """

    def __init__(self):
        """
        Timer init, takes no arguments.

        Returns
        -------
        None.

        """
        self.t0 = _time.time()

    def __call__(self):
        """
        Get the relative time.

        Calling an instance of timer will return the time since initialization
        of the instance.

        Returns
        -------
        float
            Time since classes initialization.

        """
        return _time.time() - self.t0
