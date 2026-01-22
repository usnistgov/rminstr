"""HP437B powermeter."""

import pyvisa as visa
import time
from rminstr.instruments.measurement_functionalities import ABC_RFPowerMeter
from rminstr.instruments.communications import Instrument, get_bit, InstrumentError


class RFPowerMeter(Instrument, ABC_RFPowerMeter):
    """Implements the powermeter measurment functionality for the HP437B."""

    def __init__(
        self,
        GPIB_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the powermeter class instance.

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

        visa_resource = resource_manager.open_resource(GPIB_address)
        Instrument.__init__(self, visa_resource)

        # init powermeter abstraction
        ABC_RFPowerMeter.__init__(self, log_path=log_path)
        # self.trigger_source = "IMM"
        self.info_dict = {}
        self.info_dict['model_number'] = '437B'
        # self.info_dict["serial_number"] = "Unknown"
        self.info_dict['resource_name'] = self.visa_resource.resource_name

        # default setup
        self.default_setup_settings = {
            'meas_freq_MHz': 50,
            'cal_factor_percent': 100,
            'read_units': 'LN',
            'read_range': 4,
            'resolution': 3,
            'averages': 2,
            'zero_cal': False,
        }

        # intializing counters and lists for external triggering
        # self.arm_settings['trigger_source'] = "EXT"

    def initial_setup(self, **kwargs):
        """
        Initialization method.

        Returns
        -------
        None.

        """
        super().initial_setup(**kwargs)
        # 1 Place the meter in a known state (often the reset state).
        self.clear_output()

        self.write("*RST")
        time.sleep(0.5)
        # self.write("SYST:PRES") # not sure if different

        self.write("*ESE 56")
        # self.write("*OPC")  # Send the *OPC? (operation complete query) command and enter the result to assure synchronization.
        # self.write("*CLS")  # remove anything left in the output queue

        self.write('*CLS')  # remove anything left in the output queue

        # # self.write("PP1EN")
        # # self.write("PPE")

        self.state = 'init'
        # call the dict constructor to avoid aliasing
        # Need this so that the instrument doesnt hang on later setup commands
        time.sleep(0.5)
        initial_settings = dict(self.default_setup_settings)
        for key, value in kwargs.items():
            initial_settings[key] = value

        self.setup(**initial_settings)
        self.state = 'init'

        self.raise_errors()
        # Need this so that the instrument doesnt hang on later setup commands
        time.sleep(0.5)
        self.write("GT2")  # Group execute behavior, specific to direct comparison
        self.write("TR0")
        # self.write("*CLS")

    def setup(
        self,
        meas_freq_MHz: int = None,
        cal_factor_percent: int = None,
        read_units: str = None,
        read_range: int = None,
        resolution: int = None,
        averages: int = None,
        zero_cal: bool = False,
        **kwargs,
    ):
        """
        Change powermeter settings.

        Parameters
        ----------
        meas_freq_MHz : int, optional
            Measurement update frequency.

        cal_factor_percent : int, optional
            Cal factor.

        read_units : str, optional
            LN or W for Watts, LG or dBm for dBm.

        read_range : int, optional
            Set range (0 is auto, 1 is -20 dBm, 2 is -10 dBm, ..., 5 is 20 dBm).

        resolution : int, optional
            1 for 1%, 2 for 0.1 %, 3 for 0.01% full scale.

        averages : int, optional
            Filter averages. uncertainties may change with this setting.

        zero_cal : bool, optional
            Will zero calibrate the instrument with a power sensor. Default is False

        Returns
        -------
        None.

        """
        super().setup(
            meas_freq_MHz=meas_freq_MHz,
            cal_factor_percent=cal_factor_percent,
            read_units=read_units,
            read_range=read_range,
            resolution=resolution,
            averages=averages,
            zero_cal=zero_cal,
            **kwargs,
        )
        # # 2 Change the meter’s settings to achieve the desired configuration.
        if meas_freq_MHz is not None:
            self.write('FR' + str(meas_freq_MHz) + 'MZEN')

        if cal_factor_percent is not None:
            self.write('KB' + str(cal_factor_percent) + 'EN')

        if read_units is not None:
            if read_units == 'dBm':
                read_units = 'LG'
            if read_units == 'W':
                read_units = 'LN'
            self.write(read_units)

        if read_range is not None:
            self.write('RM' + str(read_range) + 'EN')

        if resolution is not None:
            self.write('RE' + str(resolution) + 'EN')

        if averages is not None:
            self.write('FM' + str(averages) + 'EN')

        if zero_cal:
            Skip = input(
                'Connect monitor power sensor to 437B meter and hit enter to zero and cal. Type "skip" and hit enter to skip.\n'
            )
            if Skip != 'skip':
                # Zero Cal
                # This is directly from Chris's code
                print('Zeroing power sensor...')
                self.write('OC0EN')  # Reference oscillator off
                self.write('CS')  # clear status byte
                self.write('ZE')  # zero meter
                # self.wait_until_data_available(100)
                while not bool(
                    self.visa_resource.stb >> 1 & 1
                ):  # read the status byte and check bit 2
                    time.sleep(0.1)  # [s]
                print('Zero complete.')
                print('Calibrating power sensor (cal. factor 100 %)...')
                self.write('OC1EN')  # Reference oscillator on
                self.write('CS')  # clear status byte
                self.write(
                    'CL100EN'
                )  # calibrate with 100 % reference calibration factor
                # self.wait_until_data_available(100)
                while not bool(
                    self.visa_resource.stb >> 1 & 1
                ):  # read the status byte and check bit 2
                    time.sleep(0.1)  # [s]
                self.write('OC0EN')  # Reference oscillator off

                print("Cal complete.")

        self.raise_errors()

    # def arm(self, trigger_source: str = "BUS"):
    def arm(self):
        """
        Arm the powermeter to measure when tiggered.

        Returns
        -------
        None.

        """
        # super().arm(trigger_source = trigger_source)
        super().arm()
        # 3 Set-up the triggering conditions.
        # self.trigger_source = trigger_source
        self.write("TR0")
        # self.write("*OPC")
        

    def trigger(self):
        """
        Send trigger signal over GPIB.

        Returns
        -------
        None.

        """
        super().trigger()
        print(
            'WARNING: The previous settings are meant to be used with a group trigger. This may not work'
        )
        # 4 Initiate or arm the meter for a measurement.
        # 5 Trigger the meter to make a measurement.
        self.write("*TRG")
        #self.write("*OPC")


    def fetch_data(self, p_column_name: str = 'Power (W)') -> dict:
        """
        Fetch data from the powermeter.

        Parameters
        ----------
        p_column_name : str, optional
            Name to give power columns in dictionary. The default is "Power (W)"

        Returns
        -------
        dict
            Dictionary with give names as keys.

        """
        super().fetch_data(p_column_name=p_column_name)
        # 6 Retrieve the readings from the output buffer or internal memory.
        # 7 Read the measured data into your bus controller

        # import time
        # while(True):
        #     try:
        #         text = self.read().strip()
        #         break
        #     except:
        #         print("Crashed")
        #         time.sleep(0.01)
        try:
            text = self.read().strip()
        except Exception as e:
            raise e from e
        text = text.replace('+', '')  # sometimes I get a string that starts with ++ instead of just + (e.g., '++3.6440E-03'). Not sure why. This drops the + signs so that the string can be converted to a float.

        power = float(text)

        out = {}
        out[p_column_name] = power

        # clear status byte. Otherwise, trigger will fail state checking

        # self.write("*CLS")


        self.raise_errors()
        return out

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
        Return instrument errors messages if any.

        Returns
        -------
        str
            Instrument errors.

        """
        # TODO: make it so it raises errors

        stb = int(self.visa_resource.read_stb())
        if get_bit(stb, 32):
            return self.query("ERR?")
            
        return "0"


    def query_state(self) -> str:
        """
        Check the state.

        Returns
        -------
        str
            Instrument state.

        """
        # The normal read_stb function was not working. Idk what pyvisa does for the function it calls,
        # but doing what the manual says works
        # stb = self.read_stb()

        # stb = int(self.query("*ESR?"))
        # if get_bit(stb, 32) and (self.state == 'armed' or self.state == 'measuring'):
        #     self.state = 'data_available'
        # self.write("PPU")
        stb = int(self.visa_resource.read_stb())
        if get_bit(stb, 1) and (self.state == 'armed' or self.state == 'measuring'):
            self.state = 'data_available'
            
        

        return self.state

    def do_after_group_trigger(self):
        self.meas_start_time = self.get_relative_time()
        self.state = 'measuring'
        # self.write("*OPC")
