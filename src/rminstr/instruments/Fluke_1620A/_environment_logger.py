"""Module for using a Fluke 1620A as an enviornment logger."""

import pyvisa as visa
import time
import numpy as np
import logging
from rminstr.utilities.graphics import progressbar
from rminstr.instruments.measurement_functionalities import ABC_EnvironmentLogger
from rminstr.instruments.communications import Instrument, InstrumentError
from datetime import datetime
from itertools import cycle


logger = logging.getLogger(__name__)

def _format_date_for_input(date: datetime):
    out = str(date.year)
    out += ',' + str(date.month)
    out += ',' + str(date.day)
    out += ',' + str(date.hour)
    out += ',' + str(date.minute)
    out += ',' + str(date.second)
    return out


# map byte codes to record interval in seconds
record_interval_map = {
    0: 1.0,
    1: 2.0,
    2: 5.0,
    3: 10.0,
    4: 15.0,
    5: 30.0,
    6: 60.0,
    7: 120.0,
    8: 5.0 * 60.0,
    9: 600.0,
    10: 15.0 * 60,
    11: 20.0 * 60,
    12: 30.0 * 60,
    13: 60.0 * 60,
}


class EnvironmentLogger(Instrument, ABC_EnvironmentLogger):
    """Class for using a Fluke 1620A as an environment logger."""

    def __init__(
        self,
        visa_address: str,
        resource_manager: visa.ResourceManager = None,
        log_path: str = None,
    ):
        """
        Initialize the enviornment_logger class instance.

        Parameters
        ----------
        visa_address : str
            Visa address of instrument.

        resource_manager : visa.ResourceManager, optional
            Pyvisa resource manager for opening visa resources.
            The default is None.

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

        ABC_EnvironmentLogger.__init__(self, log_path=log_path)
        self.clear_output()
        self.write('*RST')

        idstr = str(self.query('*IDN?')).split(',')
        self.info_dict['model'] = idstr[1]
        self.info_dict['serial'] = idstr[2]
        self.info_dict['firmware'] = idstr[3]

        self.default_setup_settings = {'temp_unit': 'C', 'channel': 1}

    def initial_setup(self):
        """
        Put the instrument into a safe, known state.

        Returns
        -------
        None.

        """
        super().initial_setup()
        self.visa_resource.clear()
        self.write('*RST')
        self.write('FORMat:TDSTamp:STAT ON')
        self.state = 'init'
        self.setup(**self.default_setup_settings)
        self.state = 'init'
        self.raise_errors()

    def setup(self, temp_unit: str = None, channel: int = None):
        """
        Adjust settings on the Fluke 1620A.

        Parameters
        ----------
        temp_unit : str, optional
            'C' or 'F'. 'Units to report temperature readings in,
            doesn't apply to readings
            downloaded from the intruments data-record, which are always
            in Celcius. The default is None.

        channel : int, optional
            What sensor channel current readings should be taken from. Only
            applies to fetch_data calls for the current reading, reading
            downloaded from data record always include both sensors.
            The default is None.

        Returns
        -------
        None.

        """
        super().setup(temp_unit=temp_unit, channel=channel)
        if temp_unit is not None:
            self.write('UNIT:TEMPerature ' + temp_unit)

        if channel is not None:
            self.write('')

        self.raise_errors()

    def arm(self):
        """Do nothing except check for errors. Added for compatibility."""
        super().arm()
        self.raise_errors()

    def trigger(self):
        """Do nothing except check for errors. Added for compatibility."""
        super().trigger()
        self.raise_errors()

    def fetch_data(
        self,
        since: datetime = None,
        until: datetime = None,
        verbose_download: bool = False,
        verbose_parse: bool = False,
        chunk_size: int = 256,
    ):
        """
        Fetch data from the enviornment logger.

        If neither since, until, or at are provided this function will fetch
        the most recent reading from the active channel - use setup to set the
        active channel.

        Parameters
        ----------
        since : datetime, optional
            What date to pull the data record since. If provided, and
            'until' isn't, will pull data record up untill the current
            datetime. If 'all', all readings stored on the instruments
            memory will be downloaded. The default is None.

        until : datetime, optional
            End datetime to pull the data record of. If provided, the since.
            must also be provided and can't be 'all'. The default is None.

        verbose_download : bool, optional
            Creates a progress bar for download (can take a few minutes to
            download the data). The default is False.

        verbose_parse : bool, optional
            Prints information about the data blocks. The default is False.

        chunk_size : int, optional
            For since/until data fetches. Size of chunks (in bytes) to download
            data-record file in. The default is 256.

        Raises
        ------
        Exception
            If confusing parameters are given.

        Returns
        -------
        dict
            Dict containing ndarrays of temperature, humidity, and time stamps
            of readings.
            If fetching the current readings, out is a dict of ndarrays with
            timestamps, humidity, and temperature. The sensor that took the
            readings and the temperature units are defined in the setup comand.
            If since/until is provided temperature is always in Celcius and both
            sensors are ALWAYS provided. That data is provided in a heirarchical
            dictionary. The first level keys are the sensor idsc and the second
            level is a dictionary of timpstamps, temperature readings as an
            ndarray, humidity as an ndarry, and metadata strings about the
            instrument and sensor.


        """
        # because this always has data available
        self.state = 'data_available'
        super().fetch_data()
        channel = self.setup_settings['channel']

        if sum([a is not None for a in [since]]) > 1:
            raise Exception('Must provide since OR at OR neither. Not both.')

        # return range of data from record
        if since is not None:
            if since == 'all':
                range_str = ''
            else:
                range_str = _format_date_for_input(since)
                if until is not None:
                    range_str += ',' + _format_date_for_input(until)

            # open record, clear the output for new data

            self.write('DAT:REC:OPEN ' + range_str)
            # self.clear_output()
            opening_record = True
            count = 0
            while opening_record:
                try:
                    int(self.query('*ESR?'))
                    opening_record = False
                except Exception:
                    count += 1

            # print(count)

            self.visa_resource.clear()
            # print(self.get_errors())

            # figure out the bytes of data in the data range
            nbytes = int(self.query('DATa:RECord:OPEN?'))

            total = nbytes

            # read out the data you asked fo
            reading = True
            read_bytes = chunk_size
            data = []

            # NOTES FROM CALL WITH FLUKE:
            # what is the binary encoding: sent email with documentation
            # binary read
            while reading:
                self.write('DAT:REC:READ? ' + str(read_bytes))
                # read header
                read_bytes = min(nbytes, read_bytes)
                header_bytes = len(str(read_bytes) + ',#11')
                # print(read_bytes)
                raw = self.read_bytes(header_bytes + read_bytes)[header_bytes:]

                data.append(raw)

                nbytes -= read_bytes
                if nbytes == 0:
                    reading = False

                if verbose_download:
                    # print('bytes left ', nbytes, 'bytes read = ',
                    #       len(raw), self.get_errors())
                    progressbar(
                        'downloading data from '
                        + self.info_dict['model']
                        + ' ('
                        + str(total / 1000)
                        + ' kBytes)',
                        total,
                        total - nbytes,
                    )

            out = data[0]
            for d in data:
                out += d
            out = self.parse_binary_file(out, verbose=verbose_parse)

            # parse out data that isn't in the window asked for
            if since != 'all':
                for s in ['s1', 's2']:
                    ind = out[s + '_timestamp'] >= since.timestamp()
                    lengths = {}
                    for k, v in out.items():
                        if isinstance(v, np.ndarray) and s in k:
                            lengths[k] = len(v)

                    last_sample = -1
                    min_l = min(lengths.values())
                    if not all([l == min_l for l in lengths.values()]):
                        
                        delta = max([(l - min_l) for l in lengths.values()])
                        logger.info(f"Truncating {delta} corrupted samples on {out[s + '_id']} .")
                        last_sample = min_l

                    if until is not None:
                        ind = np.logical_and(
                            ind, out[s + '_timestamp'] < until.timestamp()
                        )
                    for k, v in out.items():
                        if isinstance(v, np.ndarray) and s in k:
                            try:
                                out[k] = v[:min_l][ind]
                            except IndexError as e:
                                raise e from e
                        


            # pack into a nicer format
            tempout = {}
            for sensor in ['s1', 's2']:
                sdict = {
                    'instr_model': out['instr_model'],
                    'instr_serial': out['instr_serial'],
                    'instr_firmware': out['instr_fw'],
                    'sensor_model': out[sensor + '_model'],
                    'sensor_serial': out[sensor + '_serial'],
                    'sensor_id': out[sensor + '_id'],
                    'timestamp': out[sensor + '_timestamp'],
                    'Temp C': out[sensor + '_temp'],
                    'RH %': out[sensor + '_hum'],
                }
                if sdict['sensor_id'] == 'NO ID':
                    sdict['sensor_id'] = sensor
                tempout[sdict['sensor_id']] = sdict
            out = tempout

        # return current measurement
        else:
            # fetch most recent measurement
            data = self.query('FETch? ' + str(channel))

            # turn date string into timestamp
            date = data.split('%')[-1][1:].split(',')
            date = [int(d) for d in date]
            ts = datetime(*date).timestamp()

            # parse the measurement
            meas = data.split(',')
            T = float(meas[2])
            RH = float(meas[4])

            out = {
                'timestamp': np.array([ts]),
                'Temp ' + self.setup_settings['temp_unit']: np.array([T]),
                'RH %': np.array([RH]),
            }

        self.raise_errors()
        return out

    def query_state(self):
        """
        Check the state of the machine.

        Returns
        -------
        str
            Current state of the instrument.

        """
        return self.state

    def set_time_zero(self):
        """Set current time as time zero."""
        return time.time()

    def get_errors(self):
        """
        Get any error messages on the intstrument.

        Returns
        -------
        str
            Result of an error query on the insturment.

        """
        return self.query('SYSTem:ERRor?')

    def raise_errors(self):
        """
        Raise any error messages on instrument as InstrumentErrors in python.

        Raises
        ------
        InstrumentError
            Error associated with an instrument.

        Returns
        -------
        None.

        """
        errors = self.get_errors()
        ecode = int(errors.split(',')[0])
        if ecode:
            errors = (
                'Caught from '
                + self.info_dict['model']
                + ' s/n '
                + self.info_dict['serial']
                + ' : '
                + errors
            )
            raise InstrumentError(errors)

    def parse_binary_file(self, data, verbose=False):
        """
        Parse a binary file downloaded from the instrument.

        Parameters
        ----------
        data : bytes
            Raw bytes data as a large string of bytes, as downloaded from
            the instrument.

        verbose : bool, optional
            If True, prints info about parsing. The default is False.

        Returns
        -------
        dict:
            Dictionary of data parsed from the logger.

        """
        # expects data as bytes
        # split by headers
        data = data.split(b'\x8e')
        # checksum = data[1]
        data = data[0]
        headers = data.split(b'\x80')
        headers = headers[1:]

        out = {
            'instr_model': None,
            'instr_serial': None,
            'instr_fw': None,
            's1_model': None,
            's1_serial': None,
            's1_id': None,
            's2_model': None,
            's2_serial': None,
            's2_id': None,
            's1_timestamp': np.array([]),
            's1_temp': np.array([]),
            's1_hum': np.array([]),
            's2_timestamp': np.array([]),
            's2_temp': np.array([]),
            's2_hum': np.array([]),
        }

        for i, head in enumerate(headers):
            try:
                # fileversion = head[0]
                # instrument info
                instrid = head.split(b'\x8d')[1]
                out['instr_model'] = instrid.split(b'\x00')[0].decode('utf-8')
                out['instr_serial'] = instrid.split(b'\x00')[1].decode('utf-8')
                out['instr_fw'] = instrid.split(b'\x00')[2].decode('utf-8')

                # sensor 1
                s1 = head.split(b'\x89')[1]
                out['s1_model'] = s1.split(b'\x00')[0].decode('utf-8')
                out['s1_serial'] = s1.split(b'\x00')[1].decode('utf-8')
                out['s1_id'] = s1.split(b'\x00')[2].decode('utf-8')

                # sensor 2
                s2 = head.split(b'\x8a')[1]
                out['s2_model'] = s2.split(b'\x00')[0].decode('utf-8')
                out['s2_serial'] = s2.split(b'\x00')[1].decode('utf-8')
                out['s2_id'] = s2.split(b'\x00')[2].decode('utf-8')

                # channel listr
                clist = head.split(b'\x81')[1][0]
                read_map = {
                    's1_temp': clist & (1 << 0),
                    's1_hum': clist & (1 << 1),
                    's2_temp': clist & (1 << 2),
                    's2_hum': clist & (1 << 3),
                }

                # recording interval
                inter = head.split(b'\x88')[1][0:2]
                record_interval = record_interval_map[inter[0]]
                resolution = inter[1]  # fixed value useless
                resolution = {
                    's1_temp': 0.01,
                    's1_hum': 0.1,
                    's2_temp': 0.01,
                    's2_hum': 0.1,
                }

                # base time
                base_time = head.split(b'\x87')[1][0:6]
                basetime = datetime(
                    year=base_time[0] + 2000,
                    month=base_time[1],
                    day=base_time[2],
                    hour=base_time[3],
                    minute=base_time[4],
                    second=base_time[5],
                )

                dblck = head.split(b'\x8f')[1]

                bases = {
                    's1_temp': None,
                    's1_hum': None,
                    's2_temp': None,
                    's2_hum': None,
                }

                # make cycling iterator to identify which readings are which
                read_meas = [k for k, v in read_map.items() if v]
                read_cycle = cycle(read_meas)
                cycle_counter = cycle(range(len(read_meas)))

                t_meas = basetime.timestamp()
                count = 0
                cycle_count = 0

                def twos_comp(val, bits):
                    """Compute the 2's complement of int value val."""
                    # if sign bit is set e.g., 8bit: 128-255
                    if (val & (1 << (bits - 1))) != 0:
                        val = val - (1 << bits)  # compute negative value
                    return val  # return positive value as is

                while count < len(dblck):
                    byte = dblck[count]
                    new_base = False
                    # check if a new base is being presented
                    if byte == 130:
                        new_base = True
                        meas = 's1_temp'

                    elif byte == 131:
                        new_base = True
                        meas = 's1_hum'

                    elif byte == 132:
                        new_base = True
                        meas = 's2_temp'

                    elif byte == 133:
                        new_base = True
                        meas = 's2_hum'
                    # update base measurement
                    if new_base:
                        b2 = dblck[count + 1 : count + 3]
                        bases[meas] = int(b2[0]) + int(b2[1]) * resolution[meas]
                        # print(bases)
                        count += 3
                        # print(bases)
                    # add to new measurement
                    else:
                        meas = next(read_cycle)
                        cycle_count = next(cycle_counter)

                        offset = twos_comp(dblck[count], 8) * resolution[meas]
                        # print(bases)
                        out[meas] = np.append(out[meas], bases[meas] + offset)

                        # print(meas,cycle_count,len(out[meas])
                        count += 1
                        # add a time stamp at the end of sensor 1 reading swhich
                        # always come first
                        if cycle_count == sum(['s1' in m for m in read_meas]) - 1:
                            if any(['s1' in m for m in read_meas]):
                                out['s1_timestamp'] = np.append(
                                    out['s1_timestamp'], t_meas
                                )
                        # sensor 2 is always at the end of cycle count
                        if cycle_count == len(read_meas) - 1:
                            if any(['s2' in m for m in read_meas]):
                                out['s2_timestamp'] = np.append(
                                    out['s2_timestamp'], t_meas
                                )
                            t_meas += record_interval
                            # print('    N Readings: ', len(out['timestamp']), [
                            #       len(out[m]) for m in read_meas])

                if verbose:
                    print('Block ', i)
                    print('-------------')
                    print('    in record ')
                    for k, v in read_map.items():
                        print('    ', k, ' ', v)
                    print('    record interval ', record_interval)
                    print('    base time', basetime)
                    print(
                        '    N Readings: ',
                        len(out['s1_timestamp']),
                        len(out['s1_temp']),
                        len(out['s1_hum']),
                    )
                    print(
                        '    N Readings: ',
                        len(out['s2_timestamp']),
                        len(out['s2_temp']),
                        len(out['s2_hum']),
                    )
                    print('    cycle count ', cycle_count)
                    pass
            except TypeError:
                print('Block ', i)
                print('-------------')
                print('    failed')
        return out
