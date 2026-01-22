"""Control the HP3458A as a Voltmeter."""

import pyvisa as visa
import time
import numpy as np
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError
from rminstr.instruments.communications import do_after_group_trigger
from rminstr.instruments.measurement_functionalities import ABC_Voltmeter


class Voltmeter(Instrument, ABC_Voltmeter):
    """Implementation the HP3458A as a Voltmeter."""

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
            Pyvisa resource manager for opening visa resources. The Default is None.

        log_path : str, optional
            If provided, will log at the specified path. The default is None.

        Returns
        -------
        None.

        """
        # open visa resource, and intialize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)

        # init Voltmeter abstraction
        ABC_Voltmeter.__init__(self, log_path=log_path)
        # open visa resource, and intitlize
        self.info_dict['model_number'] = 'HP3458A'
        self.info_dict['serial_number'] = 'Unknown'
        self.info_dict['resource_name'] = self.visa_resource.resource_name
        # default setup settings
        self.default_setup_settings = {
            'nplc': 1,
            'v_range': 'AUTO',
            'num_readings': 1,
            'timer': 1e-3,
            'measure_autozero': 'ON',
            'extout_mode': 'ONCE',
            'extout_polarity': 'POS',
        }

    # %% Make_Safe
    def initial_setup(self, display: bool = False, **kwargs):
        """
        Initialize the Voltmeters local settings to a safe state.

        Parameters
        ----------
        display : bool, optional
            Boolean to turn on the front display or not. The default is False.

        Returns
        -------
        None.

        """
        # clear out the machines output
        super().initial_setup(display=display, **kwargs)
        self.clear_output()
        self.write('RESET')
        if display:
            self.write('DISP ON')
        else:
            self.write('DISP OFF')  # makes measurements faster

        self.write('MATH OFF')  # makes measurements faster
        self.write('ARANGE OFF')  # makes measurements faster

        # at this point, the state should be uninit
        # set state to init so that we can call setup
        # but keep the state as init
        self.state = 'init'

        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.state = 'init'

        # set to uninit so that, if this function fails for some reason,
        # the Voltmeter is in an uninitialized state
        # we trust the _ABC_Voltmeter object to set the state to init when
        # this method completes successfully.

        # I commented out since this seems like a depricated thing (no other instruments do this).
        # Also the function will either terminate above this or finish
        # self.set_state('uninit')

        self.write('TRIG HOLD')
        # self.write("RQS 255") # enable "data available" staus bit

    # %% Setup
    def setup(
        self,
        nplc: float = None,
        v_range: float = None,
        num_readings: int = None,
        timer: float = None,
        autozero=None,
        extout_mode: str = None,
        extout_polarity: str = None,
        **kwargs,
    ):
        """
        Change Voltmeter settings.

        Parameters
        ----------
        nplc : float, optional
            Number of power line cycles to integrate over. The default is None.

        v_range : float, optional
            Voltage measurement range The default is None.

        num_readings : int, optional
            Number of readings to take. The default is None.

        timer : float, optional
            Time between measuring points. If it is smaller then the time it
            takes to measure (from nplc), will throw a trigger too fast error.
            Be warned. The default is None.

        autozero: bool, optional
            Set the autozero settings TRUE or FALSE. TRUE will have
            instrument zero before every measurement, doubling sample time. False
            will have instrument zero once, then it will do it again only if
            settings are changed. The default is None.

        extout_mode: str, optional
            Adjust how the external trigger signal is generated.
            The initial state is 'ONCE' where the trigger() method needs
            to be called with "generate_extout" in order to produce a signal.
            The default is None.

        extout_polarity: str, optional
            Adjust the polarity of the external trigger signal. The default is None.

        Returns
        -------
        None.
        """
        super().setup(
            nplc=nplc,
            v_range=v_range,
            num_readings=num_readings,
            timer=timer,
            autozero=autozero,
            extout_mode=extout_mode,
            extout_polarity=extout_polarity,
            **kwargs,
        )

        if nplc is not None:
            self.write('NPLC ' + str(nplc))  # set number of power-line cycles
        if v_range is not None:
            self.write('DCV ' + str(v_range))
        if num_readings is not None:
            if num_readings == 1:
                self.write('NRDGS ' + str(num_readings) + ', AUTO')
            else:
                self.write('NRDGS ' + str(num_readings) + ', TIMER')
        if timer is not None:
            self.write('TIMER ' + str(timer))
        if autozero is not None:
            if autozero:
                self.write('AZERO ON')
            else:
                self.write('AZERO ONCE')

        # external trigger settings
        if extout_mode is not None or extout_polarity is not None:
            if extout_mode is None:
                extout_mode = self.setup_settings['extout_mode']

            if extout_polarity is None:
                extout_polarity = self.setup_settings['extout_polarity']

            if extout_mode == 'ONCE':
                self.write('EXTOUT ONCE')
            else:
                self.write('EXTOUT ' + extout_mode + ',' + extout_polarity)

        self.write('NDIG 8')
        self.raise_errors()
        self.write('INBUF ON')
        self.raise_errors()
        self.write('MEM FIFO')
        self.raise_errors()

    # %% Arm

    def arm(self, delay: float = 0, trigger_source: str = 'BUS'):
        """
        Arm the instrument, and define how it will trigger/send out trigger signals.

        Parameters
        ----------
        delay : float, optional
            Delay between trigger and reading start. The default is 0.

        trigger_source: str, optional
            'BUS' or 'EXT', source of triggering. The default is 'BUS'.

        Returns
        -------
        None.

        """
        super().arm(delay=delay, trigger_source=trigger_source)
        self.write('TARM AUTO')
        self.write('TRIG HOLD')
        self.write('DELAY ' + str(delay))

        if trigger_source == 'EXT':
            self.write('TRIG EXT')

        self.raise_errors()

    # %% Trigger
    def trigger(self, *instruments):
        """
        Send trigger signal over GPIB.

        Parameters
        ----------
        instruments : list
            List of positional arguments of instruments to trigger from the HP.

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
        v_column_name: str = 'Voltage (V)',
        meas_start_time: float = None,
    ) -> dict:
        """
        Fetch data from the machine.

        Parameters
        ----------
        time_column_name : str, optional
            Name you want for timestamps key. The default is "timestamp".

        v_column_name : str, optional
            Name you want for voltage key. The default is "Voltage (V)".

        meas_start_time : float, optional
            If provided, will be used as timestamp for time of trigger. The default is None.

        Returns
        -------
        dict
            Measurement data.

        """
        super().fetch_data(
            time_column_name=time_column_name,
            v_column_name=v_column_name,
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
        voltages = np.zeros(self.setup_settings['num_readings'])
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
            voltages[i] = v
            timestamp += self.setup_settings['timer']

        out = {}
        out[time_column_name] = times
        out[v_column_name] = voltages

        # self.raise_errors()
        # mostly trying to catch "TRIGGER TOO FAST"
        return out

    # %% Query State
    def query_state(self) -> str:
        """
        Check the state of the machine according to state model.

        Returns
        -------
        str
            Current state of the instrument.

        """
        time.sleep(0.1)
        # if measuring, check if data is available
        # check status byte until measurement is done
        # 16 is "ready for instructions"
        # 128 is "data available"

        if (
            get_bit(self.read_stb(), 128)
            and get_bit(self.read_stb(), 16)
            and (self.state == 'armed' or self.state == 'measuring')
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
            time.sleep(0.2)
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
            return self.special_read()

    def do_after_group_trigger(self):
        """
        Run post-trigger commands after an external trigger event.

        Returns
        -------
        None.

        """
        self.meas_start_time = self.get_relative_time()
        self.raise_errors()


# %%
if __name__ == '__main__':
    NPLC = 1
    V_range = 5
    num_readings = 20
    timer = 0.05

    # correct workflow
    rm = visa.ResourceManager()
    intf = rm.open_resource('GPIB0::INTFC')

    DVM = Voltmeter('GPIB0::22::INSTR', rm)
    print(DVM.query_state())
    DVM.initial_setup()
    print(DVM.query_state())
    DVM.setup(
        nplc=NPLC,
        v_range=V_range,
        num_readings=num_readings,
        timer=timer,
        measure_autozero=False,
        timeout=10,
    )
    print(DVM.query_state())
    for i in range(1):
        print('i = ', i)
        DVM.arm()
        print(DVM.query_state(), DVM.read_stb())
        # DVM.trigger()
        intf.group_execute_trigger(DVM.visa_resource)
        print(DVM.query_state(), DVM.read_stb())
        DVM.wait_until_data_available()
        print(DVM.query_state(), DVM.read_stb())
        DVM_data = DVM.fetch_data()

        print(DVM.query_state(), DVM.read_stb())

        print(DVM_data['Voltage (V)'])

    # incorrect workflow
