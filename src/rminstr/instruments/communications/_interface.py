"""Interface module contains wrappers for pyvisa interfaces."""

import pyvisa as _visa
import warnings as _wrns
import time as _time
from rminstr.instruments.communications import Instrument

__all__ = ['do_after_group_trigger', 'ext_trigger', 'GPIBInterface']


def do_after_group_trigger(*instruments):
    """
    Call to have instruments perform post triggering commands.

    Will call each instruments do_after_group_trigger() method,
    as well as reset measurement start time, if applicable.

    Parameters
    ----------
    *instruments : instruments.communications.instrument
        List of instruments to perform the post triggering commands on.

    Returns
    -------
    float
        Trigger time, from time.time() at the beginning of this method.

    """
    trig_time = _time.time()
    for i in instruments:
        # run do after group trigger function
        if hasattr(i, 'do_after_group_trigger'):
            i.do_after_group_trigger()
        if hasattr(i, 'meas_start_time'):
            i.meas_start_time = trig_time
        i.state = 'measuring'

    return trig_time


# Idk what fun is. delete if it doesnt cause problems not being here
# I feel like fun is supposed to be fun()
# def ext_trigger(self, fun, *instruments):


def ext_trigger(self, *instruments):
    """
    Call when an external trigger occurs so that the state model and other things can be updated.

    Parameters
    ----------
    *instruments
        List of instruments to perform the external trigger on.

    Returns
    -------
    None.

    """
    if len(instruments) > 0:
        do_after_group_trigger(*instruments)
    # fun


class GPIBInterface:
    """
    Calorimeter-python GPIB Interface for group triggering.

    This is a wrapper for the pyvisa interface, and handles state model
    management within calorimeter-python objects.

    Attributes
    ----------
    interface : visa.Resource
        GPIB pyvisa resource

    """

    def __init__(
        self, interface_address: str, resource_manager: _visa.ResourceManager = None
    ):
        """
        Initialize the interface.

        Parameters
        ----------
        interface_address : str
            GPIB interface of form "GPIBX::INTFC".

        resource_manager : _visa.ResourceManager, optional
            Resource manager to instantiate interface with. If none provided,
            a manager will be instantiated. The default is None

        Returns
        -------
        None.

        """
        if resource_manager is None:
            resource_manager = _visa.ResourceManager()
        # generate interfaces
        self.interface = resource_manager.open_resource(interface_address)

    def group_trigger(self, *instruments: Instrument):
        """
        Send a group-execute-trigger (GET) signal to all instruments.

        Instruments being triggered should all be positional arguments. Non
        GPIB instruments will have their visa_resource.assert_trigger() method
        called immediately following the GET command, and a warning will be
        raised to the user.

        Instrument classes that require additional commands/logic to manage
        their state models following a group_trigger command are expected to
        have a "do_after_group_trigger()" class instance
        method that takes no arguments. Any
        instrument class with this method will have it called immediately
        following the GET.

        Parameters
        ----------
        *instruments : instruments.communications.instrument
            Positional arguments all calorimeter-python instrument objects.

        Returns
        -------
        float
            Clock time at do_after_group_trigger() time. Should be very close to GET signal.

        """
        gpib_resources = [
            i.visa_resource
            for i in instruments
            if int(i.visa_resource.interface_type) == 1
        ]
        non_gpib_resources = [
            i.visa_resource
            for i in instruments
            if int(i.visa_resource.interface_type) != 1
        ]
        self.interface.group_execute_trigger(*gpib_resources)
        for i in non_gpib_resources:
            i.assert_trigger()
        if len(non_gpib_resources) > 0:
            _wrns.warn(
                str(non_gpib_resources)
                + ' are non GPIB. Asserting triggers individually',
                stacklevel=2,
            )

        # trig_time = _time.time()
        # for  i in instruments:
        #     # run do after group trigger function
        #     if hasattr(i,'do_after_group_trigger'):
        #         i.do_after_group_trigger()
        #     if hasattr(i,'meas_start_time'):
        #         i.meas_start_time = trig_time
        #     i.state = 'measuring'
        return do_after_group_trigger(*instruments)

    def close(self):
        """Close the instrument."""
        self.interface.close()
