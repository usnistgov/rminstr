# -*- coding: utf-8 -*-
"""Control the HP3458A as an ammeter."""

import pyvisa as visa
import time
import numpy as np
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError
from rminstr.instruments.communications import do_after_group_trigger
from rminstr.instruments.measurement_functionalities import ABC_Ammeter


class Ammeter(Instrument, ABC_Ammeter):
    """Implementation the HP3458A as an Ammeter."""

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the Ammeter class instance.

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
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)

        Instrument.__init__(self, visa_resource)

        # init ammeter abstraction
        ABC_Ammeter.__init__(self, log_path=log_path)
        # open visa resource, and intitlize
        self.info_dict['model_number'] = 'HP3458A'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name
        # default setup settings
        self.default_setup_settings = {
            'nplc': 1,
            'i_range': 'AUTO',
            'num_readings': 1,
            'timer': 1 / 60,
        }

    # %% Make_Safe
    def initial_setup(self, display: bool = False, **kwargs):
        """
        Initiliaze the ammeter's local settings to a safe state.

        Parameters
        ----------
        display : bool, optional
            Boolean to turn on the front display or not. The default is False.

        Returns
        -------
        None.

        """
        super().initial_setup(display=display, **kwargs)
        self.clear_output()
        self.write('RESET')
        if display:
            self.write('DISP ON')
        else:
            self.write('DISP OFF')  # makes measurements faster
        self.write('MATH OFF')  # makes measurements faster
        self.write('ARANGE OFF')  # makes measurements faster
        # clear out the machines output
        self.state = 'init'

        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value
        self.setup(**self.default_setup_settings)

        self.state = 'init'

        self.write('TRIG HOLD')
        self.write('CSB')
        self.write('OFORMAT ASCII')
        # self.write("RQS 255") # enable "data available" staus bit

    # %% Setup
    def setup(
        self,
        nplc: float = None,
        i_range: float = None,
        num_readings: int = None,
        timer: float = None,
        measure_autozero: bool = None,
        **kwargs,
    ):
        """
        Change measurement settings.

        Parameters
        ----------
        nplc : float, optional
            Number of power line cycles to integrate over. The default is None.

        i_range : float, optional
            Current measurement range. The default is None.

        num_readings : int, optional
            Number of readings to take. The default is None.

        timer : float, optional
            Timer between measurements. Needs to be long enough or there will be an error. The default is None.

        measure_autozero : bool, optional
            Whether or not to auto zero each measurement. If False it will auto zero once at the beginning.
            The default is None.

        Returns
        -------
        None.

        """
        super().setup(
            nplc=nplc,
            i_range=i_range,
            num_readings=num_readings,
            timer=timer,
            measure_autozero=measure_autozero,
            **kwargs,
        )
        if nplc is not None:
            self.write('NPLC ' + str(nplc))  # set number of power-line cycles
        if i_range is not None:
            self.write('DCI ' + str(i_range))
        if num_readings is not None:
            if num_readings == 1:
                self.write('NRDGS ' + str(num_readings) + ', AUTO')
            else:
                self.write('NRDGS ' + str(num_readings) + ', TIMER')
        if timer is not None:
            self.write('TIMER ' + str(timer))
        if measure_autozero is not None:
            if measure_autozero:
                self.write('AZERO ON')
            else:
                self.write('AZERO ONCE')
        self.write('NDIG 6')
        self.raise_errors()
        self.write('INBUF, ON')
        self.raise_errors()
        self.write('MEM FIFO')
        self.raise_errors()
        # self.raise_errors()

    # %% Arm

    def arm(self, delay: float = 0, trigger_source: str = 'BUS'):
        """
        Arm the machine.

        Currently just sets the machine to auto trigger, hold.

        Parameters
        ----------
        delay : float, optioanl
            Delay between receiving a trigger command and taking the measurement. The default is 0.

        trigger_mode: str, optional
            BUS for triggering via GPIB, EXT for external triggering. The default is 'BUS'.

        Returns
        -------
        None.

        """
        super().arm(delay=delay, trigger_source=trigger_source)
        if trigger_source == 'BUS':
            self.write('TARM AUTO')
        elif trigger_source == 'EXT':
            self.write('TARM AUTO;TRIG EXT')

        self.write('DELAY ' + str(int(delay)))
        self.write('TARM AUTO')
        self.raise_errors()

    # %% Trigger

    def trigger(self, *instruments):
        """
        Send trigger signal over GPIB.

        Parameters
        ----------
        instruments : list
            List of positional arguments of instruments to trigger from the HP,
            if applicable.

        Returns
        -------
        None.

        """
        super().trigger(*instruments)
        msg = 'TRIG SGL'
        # add a trigger out signal if instruments are added to arguments
        if len(instruments) > 0:
            msg = 'EXTOUT ONCE;' + msg
        self.write(msg)
        # tell instruments they were triggered
        if len(instruments) > 0:
            do_after_group_trigger(*instruments)

        self.meas_start_time = self.get_relative_time()
        self.raise_errors()

    # %% Fetch Data

    def fetch_data(
        self,
        time_column_name: str = 'timestamp',
        i_column_name: str = 'Current (A)',
        meas_start_time: float = None,
    ) -> dict:
        """
        Fetch data from the machine.

        Parameters
        ----------
        time_column_name : str, optional
            Name you want for timestamps key. The default is "timestamp".

        i_column_name : str, optional
            Name you want for current key. The default is "Current (A)".

        meas_start_time : float, optional
            If provided, will be used as timestamp for time of trigger. The default is None.

        Returns
        -------
        dict
            Measurement data.

        """
        super().fetch_data(
            time_column_name=time_column_name,
            i_column_name=i_column_name,
            meas_start_time=meas_start_time,
        )
        # wait parameters
        # sleep_count = 0
        # sleep_duration = 0.1

        # check status byte until measurement is done
        # 16 is "ready for instructions"
        # 128 is "data available"

        # status_byte = self.read_stb()

        # while not get_bit(status_byte, 16):
        #     status_byte = self.read_stb()
        #     sleep_count += 1
        #     time.sleep(sleep_duration)

        # read in data
        times = np.zeros(self.setup_settings['num_readings'])
        currents = np.zeros(self.setup_settings['num_readings'])
        try:
            delay = self.arm_settings['delay']
        except KeyError:
            delay = 0
        if meas_start_time is None:
            timestamp = self.meas_start_time + delay
        else:
            timestamp = meas_start_time + delay

        new_data = self.read_bytes(self.setup_settings['num_readings'] * 18).decode(
            'utf-8'
        )
        strdata = new_data.split('\r\n')
        for i, s in enumerate(strdata):
            if not s:  # new_data.split returns an empty string at the end
                continue
            v = float(s)  # .strip("\\r\\n'"))
            times[i] = timestamp
            currents[i] = v
            timestamp += self.setup_settings['timer']

        out = {}
        out[time_column_name] = times
        out[i_column_name] = currents

        # self.raise_errors()
        # mostly trying to catch "TRIGGER TOO FAST"
        return out

    # %% Query State
    def query_state(self):
        """
        Check the state of the machine.

        Returns
        -------
        str
            Current state of the instrument.

        """
        # if measuring, check if data is available
        if get_bit(self.read_stb(), 128) and (
            self.state == 'armed' or self.state == 'measuring'
        ):
            self.state = 'data_available'

        # otherwise return measuring
        return self.state

    # %%

    def special_read(self):
        """
        Read from HP3458A output buffer.

        The HP3458A is unusual, and pyvisa's read() does not work.
        read_bytes works, but requires extra work to parse correctly.
        This funtion does that work for you.

        Returns
        -------
        str
            Whatever happens to be on the HP3458A's output buffer.

        """
        out_str = ''
        time.sleep(0.1)

        status_byte = self.read_stb()
        while get_bit(status_byte, 128):  # 128 means "data available"
            char = self.read_bytes(1).decode('utf-8')
            out_str += char
            status_byte = self.read_stb()

        return out_str

    def raise_errors(self):
        """
        If the HP3458A is in an error state, raise the errors as python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        status_byte = self.read_stb()
        if get_bit(status_byte, 32):
            self.write('ERRSTR?')
            errstr = self.special_read()
            raise (InstrumentError(errstr))

    def get_errors(self) -> str:
        """
        Get any errors present on the instrument as a string.

        Returns
        -------
        str
            Error string if one is there.

        """
        status_byte = self.read_stb()
        if get_bit(status_byte, 32):
            self.write('ERRSTR?')
            return

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        self.meas_start_time = self.get_relative_time()
        self.raise_errors()


if __name__ == '__main__':
    NPLC = 1
    i_range = 0.001
    num_readings = 5
    timer = 1
    # correct workflow
    DVM = Ammeter('GPIB0::22::INSTR', default_behaviours=True)
    print(DVM.query_state())
    DVM.initial_setup()
    print(DVM.query_state())
    DVM.setup(nplc=NPLC, i_range=i_range, num_readings=num_readings, timer=timer)
    print(DVM.query_state())
    for i in range(1):
        DVM.arm()
        print(DVM.query_state())
        time.sleep(0.1)
        DVM.trigger()
        print(DVM.read_stb())
        DVM.wait_until_data_available(timeout=10)
        print(DVM.read_stb())
        DVM_data = DVM.fetch_data()
        print(DVM_data['Current (A)'])
