"""Base class that defines attributes all pyvisa objects should have."""

import abc
import time
from pyvisa import VisaIOError


def get_bit(x, bit):
    """
    Return a specific bit in x. Intended to make the status byte easier to read.

    Parameters
    ----------
    x : int
        Value to get bit from

    bit : int
        A power of 2: 1, 2, 4, 8, 16, 32, 64, 128
        I.E. the 5th bit would be 2^5 = 32

    Returns
    -------
    True if the bit is 1, False otherwise

    """
    return x & bit == bit


class InstrumentError(Exception):
    """InstrumentErrors are raised when an instrument is in an error state."""

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class SettingError(Exception):
    """InstrumentErrors are raised when a bad seeting is passed."""

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class Instrument(abc.ABC):
    """
    Wrapper for pyvisa Resource objects. This class exists to standardize the interface of derived instruments.

    Attributes
    ----------
    visa_resource : visa.Resource
        Pyvisa resource object of the connected instrument.

    time_zero : float
        Absolute time for relative timestamps.

    """

    _STB_ATTEMPT_INTERVAL = 0.1  # seconds

    def __init__(self, visa_resource):
        """
        Initiate the instrument.

        Parameters
        ----------
        visa_resource : visa.Resources
            The pyvisa resource.

        Returns
        -------
        None.

        """
        self.visa_resource = visa_resource
        self.time_zero = None
        self.set_time_zero()

    def write(self, txt):
        """
        Shortened version of self.visa_resource.write(txt).

        Parameters
        ----------
        txt : str
            Text to write.

        Returns
        -------
        None.

        """
        self.visa_resource.write(txt)

    def read_stb(self, num_attempts=3):
        """
        Shortened version of self.visa_resource.read_stb().

        Parameters
        ----------
        num_attempts : int, optional
           Number of attempts for reading the status bit if there is an error.
           The default is 3.

        Returns
        -------
        str
            The status_byte.

        """
        for i in range(num_attempts):
            try:
                status_byte = self.visa_resource.read_stb()
                break

            except VisaIOError as e:
                # print("Visa IO error.")
                # print(f"Attempt {i + 1} of {num_attempts}")
                time.sleep(self._STB_ATTEMPT_INTERVAL)
                if i == num_attempts - 1:
                    print(f'Aborting after {i + 1} failed attempts to read status byte')
                    raise e

        return status_byte

    def read(self):
        """
        Shortened version of self.visa_resource.read().

        Returns
        -------
        str
            Result of self.visa_resource.read().

        """
        return self.visa_resource.read()

    def query(self, txt):
        """
        Shortened version of self.visa_resource.query().

        Parameters
        ----------
        txt : str
           The text to query.

        Returns
        -------
        str
            Result of self.visa_resource.query().

        """
        return self.visa_resource.query(txt)

    def read_bytes(self, n):
        """
        Shortened version of self.visa_resource.read_bytes(n).

        Parameters
        ----------
        n : int
            Number of bytes to read

        Returns
        -------
        str
            Result of self.visa_resource.read_bytes(n)

        """
        return self.visa_resource.read_bytes(n)

    def set_time_zero(self, time_zero=None):
        """
        Set time zero for relative timestamps.

        Parameters
        ----------
        time_zero : float, optional
            Time zero for relative timestamps
            if None, use the result of time.time().
            The default is None.

        Returns
        -------
        None.

        """
        if time_zero is not None:
            self.time_zero = time_zero

        else:
            self.time_zero = time.time()

    def clear_output(self):
        """
        Clear the output buffer on the instrument connection.

        Returns
        -------
        None.

        """
        self.visa_resource.clear()

    def get_relative_time(self):
        """
        Get the relataive time since instantiation.

        Use for making timestamps. Returns the result of
        time.time() - time_zero.

        Returns
        -------
        float
            Time relative to self.time_zero

        """
        return time.time() - self.time_zero

    def get_info(self):
        """
        Get instrument metadata you may want to keep track of.

        Returns
        -------
        dict
            Keys: ex. "GPIB address"
            Values: ex. 11

        """
        return self.info_dict

    @abc.abstractmethod
    def raise_errors(self):
        """
        Query the instrument status.

        Query the status of the instrument. If there are errors, raise them as Python errors.
        Abstract method.

        Returns
        -------
        None.

        """

    @abc.abstractmethod
    def get_errors(self):
        """
        Query the instrument errors.

        Query the status of the instrument. Returns errors as a string.
        Abstract method.

        Returns
        -------
        None.

        """
