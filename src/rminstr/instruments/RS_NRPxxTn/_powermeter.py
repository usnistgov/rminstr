"""RS NRP75TWG Powermeter."""

import pyvisa as visa
import numpy as np
import time
from rminstr.instruments.measurement_functionalities import ABC_RFPowerMeter
from rminstr.instruments.communications import Instrument, InstrumentError, SettingError, get_bit
from typing import Union


class RFPowerMeter(Instrument, ABC_RFPowerMeter):
    """Implements the RF powermeter measurment functionality for the Rhode
    * Schwarz NRPxxT(N) power meter."""

    # Zero Cal
    # print("Zeroing monitor power sensor...")
    #     PowerMeter_Mon.write("*CLS") # Clear the Event Status Register (ESR)
    #     PowerMeter_Mon.write("*ESE 1") # Set the Event Status Enable register to allow operation complete (OPC) events to flip bit 32 in the ESR
    #     PowerMeter_Mon.write('CAL:ZERO:AUTO ONCE;*OPC')
    #     while not bool(PowerMeter_Mon.stb >> 5 & 1): # read the status byte and check bit 5
    #         plt.pause(0.1) # [s]
    #     print("Zero complete.")
    # ###

    def __init__(
        self,
        GPIB_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        # raise SystemError('This is untested code and should not be used; exiting. There is also a zero cal you can do so I added that in the comments')

        # open visa resource, and intialize as instrument
        if resource_manager is None:
            resource_manager = visa.ResourceManager()

        visa_resource = resource_manager.open_resource(GPIB_address)
        Instrument.__init__(self, visa_resource)

        # init Voltmeter abstraction
        ABC_RFPowerMeter.__init__(self, log_path=log_path)
        self.num_readings = 0
        self.trigger_source = 'IMM'
        self.trigger_t0 = None
        self.init_t0 = time.time()
        self.info_dict = {}
        self.info_dict['model_number'] = '437B'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # default setup
        self.default_setup_settings = {
            'read_units': 'W',
            'integration_time': 0.16,
            'average_state': 'ON',
            'num_readings': 1,
            'zero_once': False,
            'trig_delay': 'auto',
        }

        # intializing counters and lists for external triggering
        self.arm_settings['trigger_source'] = 'EXT'

        pass

    def initial_setup(self, **kwargs):
        """
        Initiliazation method.

        Returns
        -------
        None.

        """
        # 1 Place the meter in a known state (often the reset state).
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
        # uses status event register to check if measurement is done
        self.write('STAT:OPER:MEAS:NTR 2')
        self.write('STAT:OPER:MEAS:NTR 2')
        # if this is on, the arm function would not be required. Not sure if the arm function would cause issues with it on or not
        self.write('INITiate:CONTinuous OFF')

        self.state = 'init'
        # call the dict constructor to avoid aliasing
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.state = 'init'

        self.raise_errors()

    def raise_errors(self):
        """
        Raise instrument errors the errors as python errors.

        Returns
        -------
        None.

        """
        err_str = self.get_errors()
        err_code = int(err_str.split(',')[0])
        if err_code != 0:
            raise InstrumentError(err_str)

    def get_errors(self):
        """
        Raise instrument errors the errors as python errors.

        Returns
        -------
        None.

        """
        # TODO: make it so it raises errors
        return self.query('SYST:ERR?')

    def setup(
        self,
        read_units: str = None,
        integration_time: int = None,
        average_state: int = None,
        zero_once: bool = None,
        trig_delay: Union[float, str] = None,
        **kwargs,
    ):
        """
        Change powermeter settings.

        Parameters
        ----------
        read_units : str, optional
            W for Watts, dBm for dBm.

        integration_time : str, optional
            time in seconds of an average

        average_state : int, optional
            averaging only effective when ON. 'On' or 'Off'.

        zero_once: bool, optional
            Performs a zeroing measurement on setup call.
            Ensure all input signals are turned
            off. Blocks script while zeroing finishes. Performs if True.

        trig_delay: float, optional
            Sets the delay between the measurement and the trigger event.
            If 'AUTO', the sensor automatically waits until it settles to
            take the measurement. 0.1 to
            5.0 or 'auto'/'AUTO'. Default is 'auto'.

        Returns
        -------
        None.

        """
        vals = dict(locals())
        keys = list(vals.keys())
        keys.remove('self')
        pass_thru = {k: vals[k] for k in keys}
        super().setup(**pass_thru)

        # 2 Change the meter’s settings to achieve the desired configuration.
        if read_units is not None:
            # supporting legacy code
            if read_units == 'dBm':
                read_units = 'DBM'
            if read_units != 'DBM' and read_units != 'W':
                raise SettingError('Read units dBm or DBUV')
            self.write('UNIT:POWer ' + read_units)
            self.raise_errors()

        if integration_time is not None:
            if integration_time < 0.5e-3 or integration_time > 0.3:
                raise SettingError('integration time must be > 0.5e-3 and < 0.3')
            self.write('SENSe:POWer:AVG:APERture ' + str(integration_time))
            self.raise_errors()

        if average_state is not None:
            if (average_state != 'ON') and (average_state != 'OFF'):
                raise SettingError('average_state "ON" or "OFF"')
            self.write('SENSe:AVERage:STATe ' + str(average_state))
            self.raise_errors()

        if trig_delay is not None:
            if trig_delay == 'auto' or trig_delay == 'AUTO':
                self.write('TRIG:DEL:AUTO ON')
            elif trig_delay >= -5 and trig_delay <= 10:
                self.write('TRIG:DEL:AUTO OFF')
                self.write('TRIG:DEL: ' + str(round(trig_delay, 2)))
            else:
                raise SettingError('trig_delay AUTO, auto, or -5<=delay<=10')
            self.raise_errors()

        # keep this as last
        if zero_once:
            stb = self.read_stb()
            # print(get_bit(stb, 32))

            self.write('CAL1:ZERO:AUTO ONCE')
            temp = self.visa_resource.timeout
            # block signals until zeroing is complete
            # i think a minute timeout is long enough
            # the manual says " more then 8 seconds
            self.visa_resource.timeout = 60000
            self.query('*OPC?')
            self.write('*CLS')
            # print('zero complete')
            self.visa_resource.timeout = temp
            self.raise_errors()

        # set state
        self.state = 'unarmed'

    def arm(self, delay: float = 0, trigger_source: str = 'BUS'):
        """
        Arm the Voltmeter to measure when tiggered.

        Parameters
        ----------
        delay : float, optional
            delay after triggered. The default is 0.
        trigger_source : str, optional
            how the instrument will be triggered. The default is "BUS".

        Returns
        -------
        None.

        """
        super().arm()
        # 3 Set-up the triggering conditions.
        self.write('TRIG:SOUR ' + trigger_source)
        self.trigger_source = trigger_source
        self.write('INIT')
        self.write('*OPC')
        self.check_is_measuring()
        self.state = 'armed'

    def trigger(self):
        """
        Send trigger signal over GPIB.

        Returns
        -------
        None.

        """
        super().trigger()
        # 4 Initiate or arm the meter for a measurement.
        # 5 Trigger the meter to make a measurement.
        self.write('*TRG')
        self.write('*OPC')
        self.state = 'measuring'
        self.trigger_t0 = time.time()

    def fetch_data(self, p_column_name: str = None, v_column_name: str = None) -> dict:
        """
        Fetch data from the Voltmeter.

        Parameters
        ----------
        p_column_name: str, optional
            Name to give power clumns in output dictionairy. The default is
            "Power (<UNIT>)"
        v_column_name : str, optional
            alias for p_column_name.

        Returns
        -------
        dict
            dictionary with give names as keys.

        """
        # 6 Retrieve the readings from the output buffer or internal memory.
        # 7 Read the measured data into your bus controller

        # # read in data
        # TODO: this requires default_behaviors = True to work. Should it?
        super().fetch_data()
        # powers = np.zeros(int(self.setup_settings['num_readings']))

        text = self.query('FETC?').strip().split(',')
        powers = np.array([float(t) for t in text])

        out = {}
        if p_column_name is None and v_column_name is None:
            name = 'Power (' + self.setup_settings['read_units'] + ')'
        elif p_column_name is not None:
            name = p_column_name
        elif v_column_name is not None:
            name = v_column_name
        relstart = self.trigger_t0 - self.init_t0
        int_time = self.setup_settings['integration_time']
        out[name] = powers

        out['timestamp'] = np.array(
            [
                relstart
                + 1 / 2 * int_time
                + i * self.setup_settings['integration_time']
                for i in range(len(powers))
            ]
        )

        # clear status byte. Otherwise, trigger will fail state checking
        self.write('*CLS')

        self.raise_errors()
        self.state = 'unarmed'
        return out

    def check_is_measuring(self):
        """Check if power meter is measuring."""
        return int(self.query('STATus:OPERation:MEASuring:EVENt?')) == 2

    def query_state(self) -> str:
        """
        Check the state.

        Returns
        -------
        str
            Instrument state.

        """
        # if not measuring, return saved state
        # stb = self.read_stb()
        if self.state == 'measuring':
            stb = self.read_stb()
            opc = get_bit(stb, 32)
            # print(stb, opc)
            if opc:
                self.state = 'data_available'
                return 'data_available'

        return self.state

    def do_after_group_trigger(self):
        """Perform tasks after a group trigger."""
        self.meas_start_time = self.get_relative_time()
        self.state = 'measuring'
        self.write('*OPC')


if __name__ == '__main__':
    rm = visa.ResourceManager()
    pm = RFPowerMeter('USB0::0x0AAD::0x0156::101576::INSTR', rm)
    print(pm.query_state())
    pm.initial_setup()
    # %%
    pm.setup(
        read_units='W',
        integration_time=0.05,
        average_state='OFF',
        zero_once=False,
    )
    print(pm.query_state())
    for i in range(3):
        pm.arm()
        print(pm.query_state())
        pm.trigger()
        print(pm.query_state())
        pm.wait_until_data_available(timeout = 10,query_delay = 0.1)
        data = pm.fetch_data()
        print(data)
        print(pm.query_state())
