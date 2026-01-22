"""State model definitions all intstruments inherit from."""

import abc
from inspect import signature, _empty
from collections import namedtuple
from rminstr.utilities.timing import Timer
from rminstr.instruments.measurement_functionalities.common_behaviours import (
    _state_warning,
    log_arguments,
)
from rminstr.instruments.communications import InstrumentError
# from instruments.communications.interface import GPIB


__all__ = ('SetupOnly', 'Triggerable')


class SetupOnly(abc.ABC):
    """
    A state model of an instrument that can only call setup commands.

    Attributes
    ----------
    states : list(str)
        List of possible states for the machine to be in.

    state : str
        Current state of the machine.

    default_setup_settings : dict
        Dictionary of the default setup values. Only runs in the initial_setup function.
        This is defined in each child class.

    initial_setup_settings : dict
        Dictionary of most recent initial_setup arguments.

    setup_settings : dict
        Dictionary of most recent setup arguments.

    info_dict : dict
        Dictionary of information about the instrument.
    """

    # exists for functionality abstractios to overide with the
    # correct definitions
    acceptable_args = {
        'initial_setup': [],
        'setup': [],
    }

    def __init__(self, log_path: str = None):
        # store measurement functionality

        # define states in model, start in unsafe
        self.states = ('uninit', 'init', 'unarmed')  # tuple so you can't change it

        # create some data storage parameters
        # this is None since all the classes declare and define the dict individually
        self.default_setup_settings = None
        self.initial_setup_settings = {}
        self.setup_settings = {}

        # wrapping default behaviours of model around functions, the order
        # each function is wrapped in matters here
        # make the query function set the data_available/measuring state when it returns it
        self._state = None
        self.state = 'uninit'

        # leaving these as wrappers since it helps performance when its not being logged
        # save logs
        if log_path is not None:
            self.setup = log_arguments(__name__, log_path, self.setup)
            self.initial_setup = log_arguments(__name__, log_path, self.initial_setup)

        # make the setup function save passed keyword argument to the settings class instance variable
        # self.setup = save_kwargs_to_dict(self.setup_settings, self.setup)
        # self.initial_setup = save_kwargs_to_dict(self.initial_setup_settings, self.initial_setup)

        # make  function set a state after it runs
        # self.initial_setup = set_state_after_running(
        #     'init', self.initial_setup, self.set_state)
        # self.setup = set_state_after_running(
        #     'unarmed', self.setup, self.set_state)

        # make function  throw a warning if called from wrong state
        # self.setup = warn_if_wrong_state(
        #     ['init', 'unarmed'], self.setup, self.query_state, 'setup')

        # info_dict
        self.info_dict = {}

    # value check state model
    @property
    def state(self):
        """State attribute, reflects current position in state model."""
        return self._state

    @state.setter
    def state(self, value):
        """Set the current value in the state model."""
        assert value in self.states
        self._state = value

    def close(self):
        """
        Close the instrument.

        Good to call if the kernel will continue running after use.
        """
        self.visa_resource.close()

    @abc.abstractmethod
    def initial_setup(self, *args, **kwargs):
        """
        Run the initial setup of the instrument.

        This function is defined in the child classes.
        Keyword arguments passed in that are not part of the header are passed to the instrument
        as a raw command.

        Parameters
        ----------
        *args : list
            The function may need arguments. Arguemnts on this parent function do nothing.

        **kwargs : dict
            Any keyword arguments the instrument should have.

        Returns
        -------
        None.
        """
        self.state = 'init'
        for k in kwargs.keys():
            if kwargs[k] is not None:
                self.initial_setup_settings[k] = kwargs[k]

    @abc.abstractmethod
    def setup(self, *args, **kwargs):
        """
        Run the setup function of the instrument.

        Defined mainly in the child classes.
        Keyword arguments passed in that are not part of the header are passed to the instrument
        as a raw command.

        Parameters
        ----------
        *args : list
            The function may need arguments. Arguemnts on this parent function do nothing.

        **kwargs : dict
            Any keyword arguments the instrument should have.

        Returns
        -------
        None.
        """
        if self.state != 'init' and self.state != 'unarmed':
            _state_warning(self.state, 'setup', __file__, 45, 5)
        self.state = 'unarmed'
        for k in kwargs.keys():
            if kwargs[k] is not None:
                self.setup_settings[k] = kwargs[k]

    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        str
            Current state of the instrument.

        """
        return self.state

    @classmethod
    def _check_method_syntax(cls, method_name: str):
        """
        Check that a particular method adheres to syntax rules.

        Looks inside the 'acceptable_args' attribute for the class, which is
        defined by its measurement functionality, and checks that the key-word
        arguments are following the established names. Additionally, checks
        that all function arguments are key-word (except for self) as that
        is the convention.

        This function returns a named tuple, with the fields outlined in the
        returns section.


        Parameters
        ----------
        method_name : str
            Name of the method to check against.

        Returns
        -------
        SyntaxReport with fields:
            passed_check: bool
                Boolean,True if method passed the check
            contains_postional: bool
                Flag True if the functionc contains positional arguments. The
                convention is for state method function to only accept key-word
                arguments (except for self). For a passed check this should be
                False.
            missing_in_impl : list[st]
                List of argument names that are defined in the
                measurement_functionality
                but not defined by the instruments implementaion.If a **kwargs is
                present, this will be empty. For a passed check this should be
                empty.
            undefined_in_abc : list[str]
                List of argument names defined by the instrument inmplementation
                but not defined by the measurement_functionality abc class. For a
                passed check this should be empty.
        """
        contains_position = False
        missing = []
        undefined = []

        acceptable = cls.acceptable_args[method_name]
        sig = signature(getattr(cls, method_name))

        # check that all are acceptable
        for k, v in sig.parameters.items():
            if (
                k not in acceptable
                and '**' not in str(sig.parameters[k])
                and k != 'self'
            ):
                undefined.append(k)

        # check that all parameters are defined, or '**' is provided to catch
        # anything not defined explicitly
        if any(['**' in str(param) for param in sig.parameters.values()]):
            missing = []
        else:
            for defined in acceptable:
                if (
                    defined not in sig.parameters.keys()
                    and '**' not in str(sig.parameters[k])
                    and k != 'self'
                ):
                    missing.append(defined)

        # check for positional arguments
        for k, v in sig.parameters.items():
            # print(v.default)
            if (
                '*' not in str(sig.parameters[k])
                and '**' not in str(sig.parameters[k])
                and k != 'self'
            ):
                if v.default is _empty:
                    contains_position = True

        # make a report for the output
        SyntaxReport = namedtuple(
            'SyntaxReport', 'passed contains_position missing_in_impl  undefined_in_abc'
        )

        passed = not any([contains_position, undefined])
        report = SyntaxReport(passed, contains_position, missing, undefined)

        return report


class Triggerable(SetupOnly, abc.ABC):
    """
    A state model of an instrument that can be armed and triggered.

    Attributes
    ----------
    arm_settings: dict
        Dictionary of most recent arm arguments

    trigger_settings: dict
        Dictionary of most recent trigger arguments

    fetch_data_settings: dict
        Dictionary of most recent fetch_data arguments

    meas_start_time: float
        Absolute time used for calculating measurement start times

    """

    acceptable_args = {
        'initial_setup': [],
        'setup': [],
        'arm': [],
        'trigger': [],
        'fetch_data': [],
        'do_after_group_trigger': [],
    }

    def __init__(self, log_path: str = None):
        # inherit unTriggerable state model
        SetupOnly.__init__(self, log_path=log_path)

        # add Triggerable state model elements
        self.states = tuple(
            list(self.states) + ['armed', 'measuring', 'data_available']
        )

        # create some data storage parameters
        self.arm_settings = {}
        self.trigger_settings = {}
        self.fetch_data_settings = {}

        # used to calculate measurement start times
        self.meas_start_time = 0

        # leaving these as wrappers since it helps performance when its not being logged
        # save logs
        if log_path is not None:
            self.arm = log_arguments(__name__, log_path, self.arm)
            self.trigger = log_arguments(__name__, log_path, self.trigger)
            self.fetch_data = log_arguments(__name__, log_path, self.fetch_data)

    def wait_until_data_available(self, timeout: float = None):
        """
        Wait until the state attribute is data_available.

        Raise an error after a timeout number of seconds if data_available
        is not detected.

        Parameters
        ----------
        timeout : float, optional
            Seconds to wait before raising an error. If None, check
            settings for "timeout". If timeout is not in settings,
            default to 2 seconds.

        Raises
        ------
        InstrumentError
            If timeout occurs waiting for data.

        Returns
        -------
        None.

        """
        # timeout = timeout
        if timeout is None:
            try:
                timeout = self.setup_settings['timeout']
            except KeyError:
                timeout = 2

        mytimer = Timer()
        while self.query_state() != 'data_available':
            if mytimer() > timeout:
                raise InstrumentError('Timeout waiting for data_available state')

    @abc.abstractmethod
    def arm(self, *args, **kwargs):
        """
        Take arguments and keyword arguments that define the arming of the instrument.

        Implemented in the child classes. Kwargs get passed as raw commands
        if they are not in the header of the function.

        Parameters
        ----------
        *args : list
            The function may need arguments. Arguemnts on this parent function do nothing.

        **kwargs : dict
            Any keyword arguments the arm function should have.

        Returns
        -------
        None.
        """
        if self.state != 'unarmed':
            _state_warning(self.state, 'setup', __file__, 45, 5)
        self.state = 'armed'
        for k in kwargs.keys():
            if kwargs[k] is not None:
                self.arm_settings[k] = kwargs[k]

    @abc.abstractmethod
    def trigger(self, *args, **kwargs):
        """
        Take arguments and keyword arguments that define the triggering of the instrument.

        Implemented in the child classes. Kwargs get passed as raw commands
        if they are not in the header of the function.


        Parameters
        ----------
        *args : list
            The function may need arguments. Arguemnts on this parent function do nothing.

        **kwargs : dict
            Any keyword arguments the arm trigger should have.

        Returns
        -------
        None.
        """
        if self.state != 'armed':
            _state_warning(self.state, 'setup', __file__, 45, 5)
        self.state = 'measuring'
        for k in kwargs.keys():
            if kwargs[k] is not None:
                self.trigger_settings[k] = kwargs[k]

    @abc.abstractmethod
    def fetch_data(self, *args, **kwargs):
        """
        Take arguments and keyword arguments that definef fetching_data of the instrument.

        Implemented in the child classes. Kwargs get passed as raw commands
        if they are not in the header of the function.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments the fetch_data function should have.

        Returns
        -------
        None.
        """
        if self.state != 'data_available':
            _state_warning(self.state, 'setup', __file__, 45, 5)
        self.state = 'unarmed'
        for k in kwargs.keys():
            if kwargs[k] is not None:
                self.fetch_data_settings[k] = kwargs[k]

    # @abc.abstractmethod
    def do_after_group_trigger(self):
        """
        Perform operations immediatley after a grouptrigger is called.

        This function should take not arguments. Don't override if nothing is
        required for the specific instrument.

        Returns
        -------
        None.

        """
        self.meas_start_time = self.get_relative_time()
        self.state = 'measuring'
        self.write('*OPC')


if __name__ == '__main__':
    from rminstr.instruments.LS330 import TemperatureController as instr

    setup_report = instr._check_method_syntax('setup')
