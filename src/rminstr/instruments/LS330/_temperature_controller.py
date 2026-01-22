"""Control the LS340 as a temperature controller."""

import pyvisa as visa
import time

# import numpy as np
from rminstr.instruments.measurement_functionalities import ABC_TemperatureController
from rminstr.instruments.communications import Instrument, InstrumentError
from functools import wraps


def make_data_available(instrument, fun):
    """Set data available before calling."""

    @wraps(fun)
    def wrap1(*args, **kwargs):
        instrument.set_state('data_available')
        return fun(*args, **kwargs)

    return wrap1


class TemperatureController(Instrument, ABC_TemperatureController):
    """LS340 as a temperature controller."""

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the Voltmeter class instance.

        Parameters
        ----------
        visa_address : str
            Visa address of instrument.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources. The default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """
        # open visa resource, and intialize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()
        self.info_dict = {}
        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)

        # init Voltmeter abstraction
        ABC_TemperatureController.__init__(self, log_path=log_path)
        # Commented out -Zenn. If it breaks uncomment
        # self.num_readings = 0
        # self.trigger_source = "IMM"
        self.info_dict['model_number'] = 'LS330'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # default setup
        # I let the things that will autopopulate autopopulate
        self.default_setup_settings = {
            'assign_curve': 0,
            'sensor_units': 'S',
        }

        self.fetch_data = make_data_available(self, self.fetch_data)

    def initial_setup(self, **kwargs):
        """
        Initiliaze the temperature controllers's local settings to a safe state.

        This funciton should only be run if the instrument is not currently in a safe state,
        otherwise settings will be overwritten

        Returns
        -------
        None.

        """
        super().initial_setup(**kwargs)
        self.clear_output()
        self.write('*RST')
        # self.write("SYST:PRES") # not sure if different
        self.write(
            '*ESE 1'
        )  # Enable “operation complete” using the *ESE 1 command (standard event register).
        self.write(
            '*OPC'
        )  # Send the *OPC? (operation complete query) command and enter the result to assure synchronization.
        self.write('*CLS')  # remove anything left in the output queue

        self.set_state('init')
        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.set_state('init')

        self.raise_errors()

    def setup(self, assign_curve: str = None, sensor_units: str = None):
        """
        Change Settings.

        Parameters
        ----------
        assign_curve : int, optional
            Change curve. See Table 3-1 in manual for curve numbers.
            The default is None.

        sensor_units : str, optional
            K for Kelvin, C for Celsius, S for sensor units (e.g. V for a
            silicon diode). The default is None.

        Returns
        -------
        None.

        """
        super().setup(assign_curve=assign_curve, sensor_units=sensor_units)
        if assign_curve is not None:
            self.write('CURVA ' + str(assign_curve))
        if sensor_units is not None:
            self.write('SUNI ' + sensor_units)

        pass

    def query_state(self):
        """
        Check the state of the machine according to state model.

        Returns
        -------
        state : str
            Current state of the instrument.

        """
        return self.state

    def get_errors(self):
        """
        Get any errors present on the instrument as a string.

        Returns
        -------
        str
            Error string if one is there.

        """
        # TODO: make it so it raises errors
        return self.query('SYST:ERR?')

    def raise_errors(self):
        """
        If the LS330 is in an error state, raise the errors as python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        err_str = self.get_errors()
        err_code = int(float(err_str.split(',')[0]))
        if err_code != 0:
            raise InstrumentError(err_str)

    # This is expanding the SetupOnly state model, Should it be Triggerable? -Zenn
    # I did not add super functions as they wont exist
    def arm(self):
        """Arm, placeholder does nothing."""
        pass

    def trigger(self):
        """Arm, placeholder does nothing."""
        pass

    def fetch_data(self):
        """
        Fetch the data from the temperature controller.

        Returns
        -------
        dict
            Data from the instrument.

        """
        data = {'timestamp': time.time(), 'reading': float(self.query('SDAT?'))}
        return data


if __name__ == '__main__':
    from pyvisa import ResourceManager

    # import time
    rm = ResourceManager()
    gpib_adr = 'GPIB1::13::INSTR'
    lc = TemperatureController(gpib_adr, rm)
    lc.initial_setup()
    lc.setup(sensor_units='C', assign_curve='0')
    while True:
        time.sleep(0.1)
        lc.arm()
        lc.trigger()
        print(lc.fetch_data())
