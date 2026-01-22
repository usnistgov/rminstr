"""Control the HP34420A as a Voltmeter."""

import pyvisa as visa
import numpy as np
import time
from scipy.interpolate import interp1d
from rminstr.instruments.measurement_functionalities import ABC_Voltmeter
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError


# Reading Rates
# These may not be entirely accurate from testing
_nplc = [200, 100, 20, 10, 1, 0.2, 0.02]
_per_sec = [0.15, 0.3, 1.5, 3, 25, 100, 250]
_dcv_readings_per_second = interp1d(_nplc, _per_sec)


class Voltmeter(Instrument, ABC_Voltmeter):
    """Implementation the HP34420A as a Voltmeter."""

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

        visa_resource = resource_manager.open_resource(visa_address)
        Instrument.__init__(self, visa_resource)

        # init Voltmeter abstraction
        ABC_Voltmeter.__init__(self, log_path=log_path)
        # Commented out -Zenn. If it breaks uncomment
        # self.num_readings = 0
        # self.trigger_source = "IMM"

        self.info_dict['model_number'] = 'HP34420A'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # default setup
        self.default_setup_settings = {
            'nplc': 1,
            'v_range': 1,
            'num_readings': 1,
            'channel': 1,
            'null': 0,
        }

        # intializing counters and lists for external triggering
        # I don't see where this is used; commenting out and seeing if it breaks things -Zenn
        # self.arm_settings['trigger_source'] = "EXT"
        # self.n_counted_readings = 0
        # self.counted_readings = []

    def initial_setup(self, **kwargs):
        """
        Initiliaze the Voltmeters's local settings to a safe state.

        Returns
        -------
        None.

        """
        # 1 Place the meter in a known state (often the reset state).
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

        self.state = 'init'
        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.state = 'init'

        self.raise_errors()

    def setup(
        self,
        nplc: float = None,
        v_range: float = None,
        num_readings: int = None,
        channel: int = None,
        zero_now: bool = None,
        **kwargs,
    ):
        """
        Change Voltmeter settings.

        Parameters
        ----------
        nplc : float, optional
            Power line cycle intergration. The default is None.

        v_range : float, optional
            Voltage measurement range. If it is set to 0 it will use auto. The default is None.

        num_readings : int, optional
            Number of readings to take on trigger. The default is None.

        channel : int, optional
            The channel to measure from: 1 or 2. The default is None.

        zero_now: float, optional
            If true, sets the current reading as the NULL value. 0 turns off
            the null operation on the NVM. The default is None. NVM will
            subtract the NULL value from each measurement.

        Returns
        -------
        None.

        """
        # 2 Change the meter’s settings to achieve the desired configuration.
        # 3 Set-up the triggering conditions.
        # ORDER MATTERS HERE
        super().setup(
            nplc=nplc,
            v_range=v_range,
            num_readings=num_readings,
            channel=channel,
            zero_now=zero_now,
            **kwargs,
        )
        if channel is not None:
            self.channel = channel
            self.write('ROUT:TERM FRONt' + str(channel))

        if v_range is not None:
            if v_range == 0 or v_range == 'auto':
                self.write('SENSe:VOLT:DC:RANG:AUTO ON')
                self.write('SENSe:VOLT:DC:RES MAX')
            else:
                self.write(
                    'CONF:VOLT:DC '
                    + str(v_range)
                    + ', MAX, (@FRONt'
                    + str(self.channel)
                    + ')'
                )
        if nplc is not None:
            self.write('SENSe:VOLT:DC:NPLC ' + str(nplc))

        if num_readings is not None:
            self.write('SAMP:COUNt ' + str(num_readings))

        if zero_now is not None:
            if zero_now:
                self.write('VOLTage:DC:NULL:STAT ON')
                self.write('VOLTage:DC:NULL:VAL ' + str(zero_now))
            else:
                self.write('VOLTage:DC:NULL:STAT OFF')
        self.raise_errors()

    def arm(self, delay: float = 0, trigger_source: str = 'BUS'):
        """
        Arm the instrument, and define how it will trigger.

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
        self.write('TRIG:DEL ' + str(delay))
        self.write('TRIG:SOUR ' + trigger_source)
        self.trigger_source = trigger_source
        # raising errors after calling an external trigger source and can INIT causes
        # errors. INIT shouldn't cause errors alone so moving the raise errors call
        # here.

        # self.raise_errors()
        self.write('INIT')
        # self.write("*OPC")

    def trigger(self):
        """
        Send trigger signal over GPIB.

        Returns
        -------
        None.

        """
        # 4 Initiate or arm the meter for a measurement.
        # 5 Trigger the meter to make a measurement.
        super().trigger()
        self.meas_start_time = self.get_relative_time()
        self.write('*TRG')
        self.write('*OPC')

    def fetch_data(
        self,
        time_column_name: str = 'timestamp',
        v_column_name: str = 'Voltage (V)',
        meas_start_time: float = None,
    ) -> dict:
        """
        Fetch data from the Voltmeter.

        Parameters
        ----------
        time_column_name : str, optional
            Name to give timestamps in dictionary. The default is "timestamp".

        v_column_name : str, optional
            Name to give voltage columns in dictionary. The default is "Voltage (V)".

        meas_start_time : float, optional
            If provided, will be used as timestamp for time of trigger. The default is None.

        Returns
        -------
        dict
            Measurement data.

        """
        # 6 Retrieve the readings from the output buffer or internal memory.
        # 7 Read the measured data into your bus controller

        # wait parameters
        # sleep_count = 0
        # sleep_duration = 0.1

        # check status byte until measurement is done
        # 16 is "Message Available"
        # 32 is "Standard Event"
        # status_byte = self.read_stb()

        # while not get_bit(status_byte, 32):
        #     status_byte = self.read_stb()
        #     sleep_count += 1
        #     time.sleep(sleep_duration)

        # # read in data
        super().fetch_data(
            time_column_name=time_column_name,
            v_column_name=v_column_name,
            meas_start_time=meas_start_time,
        )
        times = np.zeros(int(self.setup_settings['num_readings']))
        voltages = np.zeros(int(self.setup_settings['num_readings']))
        try:
            delay = self.arm_settings['delay']
        except KeyError:
            delay = 0
        if meas_start_time is None:
            timestamp = self.meas_start_time + delay
        else:
            timestamp = meas_start_time + delay

        self.write('FETCh?')
        text = self.read()
        text = text.replace('\n', '')
        strdata = text.split(',')

        for i, s in enumerate(strdata):
            if not s:  # new_data.split returns an empty string at the end
                continue

            v = float(s)
            times[i] = timestamp
            voltages[i] = v
            # this instrument does not keep track of time
            # interpolating from a datasheet reading rates table
            # TODO: verify that these are correct. The datasheet might be
            # specify the readings per second under different conditions.
            timestamp += (
                1 / float(_dcv_readings_per_second(self.setup_settings['nplc'])) + delay
            )

        out = {}
        out[time_column_name] = times
        out[v_column_name] = voltages

        # clear status byte. Otherwise, trigger will fail state checking
        self.write('*CLS')

        self.raise_errors()
        return out

    def query_state(self) -> str:
        """
        Check the state of the machine.

        Returns
        -------
        str
            Current state of the instrument.

        """
        # if not measuring, return saved state

        stb = self.read_stb()

        if get_bit(stb, 32) and (self.state == 'armed' or self.state == 'measuring'):
            self.state = 'data_available'

        # otherwise return measuring
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
        If the HP34420A is in an error state, raise the errors as python errors.

        Raises
        ------
        InstrumentError
            Instrument error if the instrument has errors or is in an error state.

        Returns
        -------
        None.

        """
        err_str = self.get_errors()
        err_code = int(err_str.split(',')[0])
        if err_code != 0:
            raise InstrumentError(err_str)


if __name__ == '__main__':
    nplc = 10
    v_range = 2e-3
    num_readings = 5
    rm = visa.ResourceManager()
    NVM = Voltmeter('GPIB0::16::INSTR', rm)

    NVM.initial_setup()
    print(NVM.query_state())
    NVM.setup(nplc=nplc, v_range=v_range, num_readings=num_readings)
    print(NVM.query_state())

    for i in range(1):
        print('i = ', i)
        NVM.arm()
        time.sleep(2)
        print(NVM.query_state())
        NVM.trigger()
        print(NVM.query_state())
        NVM.wait_until_data_available(timeout=10)
        print(NVM.query_state())
        NVM_data = NVM.fetch_data()
        print(NVM_data['Voltage (V)'])
        time.sleep(1)
