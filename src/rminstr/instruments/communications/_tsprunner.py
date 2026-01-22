# -*- coding: utf-8 -*-
"""
TSPRunner is a set of protocols for interacting with TSP enabled instruments.

TSPRunner inherits from the base instrument class, and utilizes pyvisa.
"""

import time
import numpy as np
from rminstr.instruments.communications import Instrument, InstrumentError
import sys
from typing import Union
from os.path import dirname, join


class BusyError(Exception):
    """Raise when trying to command a TSP instrument that is busy."""

    pass


class StatusByteError(Exception):
    """Raise when trying to command a TSP instrument has an incorrect status byte."""

    pass


class SMUTimeoutError(Exception):
    """Raise when timeouts occur during specieal read methods for TSP instruments."""

    pass


# %% Tsp Wrapper class


class TSPRunner(Instrument):
    """
    Protocols for interacting with TSP enabled instruments.

    The TSPRunner is a communication class that inherits from instrument, the more
    fundemental communication object. It is design to handle communication over pyvisa
    with instruments that are tsp enabled, and expect tsp langauage commands (Lua).

    Attributes
    ----------
    timeout : float
        Seconds for timeout when trying to read off data.

    stb_reg : dict
        Dictionary of status byte bit places.

    termination_str : str
        Termination string that is sent at the end of run scripts to signal its end.

    busy : bool
        If True, it means that the instrument is running a tsp script, trying to command
        it at that moment will raise an error.

    busy_count : int
        Counter for busy checks, used in some methods for debugging.

    logs : bool
        When True, the class will print logs of commands, states, and other
        debugging information to the console.

    last_scr : str
        String of the last tsp script that was commmanded to run through run_script.

    """

    def __init__(self, visa_resource):
        """
        Initialize a tsp instrument.

        Parameters
        ----------
        visa_resource : visa.Resource
            Pyvisa resource that is the tsp enabled instrument.

        Returns
        -------
        None.

        """
        Instrument.__init__(self, visa_resource)
        self.info_dict = {}

        # self.info_dict["resource_name"] = self.visa_resource.resource_name
        self.visa_resource.timeout = 2000
        self.timeout = 2

        # status byte register
        self.stb_reg = {'EAV': 2, 'QSB': 3, 'MAV': 4}

        # define termination string and add it to global variable space of smu
        self.termination_str = 'script_complete'
        self.assign('termination_str', r'"script_complete"')
        # busy state and count

        self.busy = False
        self.busy_count = 0

        # last state and log
        self.logs = False
        self.last_scr = ''

    # returns smu info dict
    def get_info(self):
        """
        Get machine info.

        Returns
        -------
        dict
            instrument information.

        """
        return self.info_dict

    def raise_errors(self):
        """
        Raise an error if error bit is high on instrument.

        Needs to be reworked to actually get the error message,
        TSP scripts block sending commands for error information, need to work
        out a protocl that accounts for this. Currently, this will just raise
        an error, telling you to check the instrument.

        Raises
        ------
        InstrumentError
            Error if the error bit is high.

        Returns
        -------
        None

        """
        error = self.get_output_bit(self.stb_reg['EAV']) == 1
        if error:
            raise InstrumentError('Error flagged on SMU, check display')

    # read stb and checks if bit is active
    def get_output_bit(self, bit: int):
        """
        Check a bit in the status byte register.

        Parameters
        ----------
        bit : int
            Bit placement you want to check.

        Returns
        -------
        bool
            Returns True if bit is high. False otherwise.

        """
        try:
            stb = self.read_stb()
            out_bit = stb >> bit & 1
        # i'm sorry. I don't remeber why I put this here. I will come back later
        # -Cole
        # if I had to guess it would probably be if red_stb() throws and error
        # -Zenn
        # I'm adding an ignore to the linter here
        # because it throws errors, and this has been
        # around for a long time.
        except Exception as e:  # noqa: E722
            out_bit = 0
        return out_bit

    # print current state of SMU
    def tsp_trace(self):
        """
        Print the status of the TSPRunner instance.

        Returns
        -------
        None.

        """
        print('TSP STATE')
        print('  busy       : ', repr(self.busy))
        print('  last script: ', repr(self.last_scr))
        stb = self.read_stb()
        print('  status byte: ', repr(bin(stb)))

    # check if script finished by reading through all the available messages for a termination_str,
    # adjust busy if termination found

    def check_busy(self, showGarbage: bool = False):
        """
        Check if the instrument is busy running a TSP script.

        Checks if the instrument is busy by checking for termination strings,
        and applying a zero order hold where the termination string sets the status False,
        not busy, and sending a run script command sets the status True, busy.

        Parameters
        ----------
        showGarbage : bool, optional
            If true, logs information about the method. The default is False.

        Returns
        -------
        bool
            True if busy, False if not.

        """
        # check status byte for readable message
        # if termination present, set to not busy
        termination_str_count = 0
        # while message is available
        while self.get_output_bit(self.stb_reg['MAV']) == 1:
            time.sleep(0.01)
            try:
                txt = self.read()
                # if  termination present
                if self.termination_str in txt:
                    self.busy = False
                    self.busy_count = 0
                    # log termination_str read
                    if self.logs:
                        termination_str_count += 1
                        sys.stdout.write(
                            '\rTermination read: %i' % (termination_str_count)
                        )
                        sys.stdout.flush()
                # if asked too, print the garbage messages collected
                elif self.logs:  # and showGarbage:
                    print('check_busy() found:', txt)
            except Exception as ex:
                template = 'An exception of type {0} occurred. Arguments:\n{1!r}'
                message = template.format(type(ex).__name__, ex.args)
                print(message)
                self.tsp_trace()
                pass
        # so logs don't get filled with empy lines on repeat calls
        if not self.busy and termination_str_count > 0 and self.logs:
            print('')

        return self.busy

    # checks the error bit on the SMU
    def check_error_bit(self):
        """
        Generate a status byte error if the error bit is high.

        Raises
        ------
        StatusByteError
            Error if the error bit in the status byte is high.

        Returns
        -------
        None.

        """
        if self.get_output_bit(self.stb_reg['EAV']) == 1:
            raise StatusByteError('SMU ERROR BIT HIGH')

    # wait till not busy
    def wait(self, timeout: float):
        """
        Wait until not busy, raise error if takes longer than timeout seconds.

        Parameters
        ----------
        timeout : float
            Time to wait before raising an error.

        Raises
        ------
        SMUTimeoutError
            Error if the SMU is busy for longer than the timeout amount.

        Returns
        -------
        None.

        """
        t0 = time.time()

        while self.check_busy():
            self.check_error_bit()
            time.sleep(0.05)
            t = time.time() - t0

            # to avoid getting stuck in infinite read loops, throw timeout error
            if t > timeout:
                # self.shutDown(force = True)
                raise SMUTimeoutError('Timed out on SMU busy checks')

    # prints everything backlogged in SMU readout buffer
    def flush_readout(self):
        """
        Flushes the output buffer of the tsp enabled instrument.

        Returns
        -------
        None.

        """
        while self.get_output_bit(self.stb_reg['MAV']) == 1:
            out = self.read()
            if self.logs:
                print(out)

    def get_errors(self):
        """
        Either prints outs instrument events or raises and error if the event is an error.

        Raises
        ------
        Exception
            Error if the SMU shows an error in its events.

        Returns
        -------
        None.

        """
        keep_reading = True
        while keep_reading:
            msg = self.query_print('eventlog.next(2)').split('\t')
            severity = int(msg[2])
            if severity == 1:
                severity = 'Error'
            else:
                severity = 'Warning'
            descr = msg[1]
            event = int(msg[0])
            if 'No error' in msg[1]:
                keep_reading = False
            elif severity == 'Error':
                raise Exception(str(severity) + ' ' + str(event) + ', ' + descr + '')
            else:
                print(str(severity) + ' ' + str(event) + ', ' + descr + '')

    # assign val to global variable varname in volatile memory
    def assign(self, varname: str, val: Union[int, float]):
        """
        Assign a variable to the TSP instruments global variable space.

        Assigns a variable to the global namespace of the instrument. val is cast
        as str(variable). If the tsp namespace variable is being assign a string,
        enclose in quationtion marks. eg. val = "'string'". This is not the best
        and could be reworked to account for more data types.

        Parameters
        ----------
        varname : str
            Name of the variable that will be used in the tsp instruments namespace.

        val : float or int
            The value to assign.

        Returns
        -------
        None.

        """
        self.write(varname + ' = ' + str(val))

    # ask SMU to print a variable or list of variables
    def print_number(self, varname: str):
        """
        Command the TSP instument to print a number from its namespace.

        Parameters
        ----------
        varname : str
            String of tsp namespace variable.

        Returns
        -------
        None.

        """
        txt = 'printnumber(' + varname + ')'
        self.write(txt)

    def query_print(self, msg):
        """
        Query the instrument.

        Parameters
        ----------
        msg : str
            String of message type to have it print.

        Returns
        -------
        str
            Message query.

        """
        return self.query('print(' + msg + ')')

    # run script, all script calls should pass through here for status tracking
    def run_script(self, scriptVar: str, force: bool = False):
        """
        Run a TSP script stored on the instruments memory.

        Parameters
        ----------
        scriptVar : str
            String of script name on instruments non-volatile memory.

        force : bool, optional
            If true, will by-pass the busy checks. The default is False.

        Raises
        ------
        BusyError
            If force is False and instrument is busy while trying to be commanded,
            this will be raised.

        Returns
        -------
        None.

        """
        txt = scriptVar + '()'
        # if asked too, ignore busy check and push command
        if not force:
            if self.check_busy():
                raise BusyError('SMU is Busy on ' + scriptVar + ' call')
        self.busy = True
        self.last_scr = txt
        self.get_errors()
        self.write(txt)
        forceStr = ''
        if force:
            forceStr = 'FORCED '
        if self.logs:
            print(forceStr + 'Run ' + scriptVar + ' request sent')

    # Read out the buffer used to store measurment data, clear buffer after
    def read_buffer(self, deleteBuffer: bool = True):
        """
        Read data from a data buffer of the TSP instrument.

        This is the general purpose function for reading data off the instruments
        memory buffer. This could be better generalized to usable for buffers with different names,
        and for getting different types of data from the buffer.

        Parameters
        ----------
        deleteBuffer : bool, optional
            If true, read buffer will deallocate the buffer from the instruments
            memory after the data has been read. The default is True.

        Raises
        ------
        BusyError
            If instrument is busy when asking for data.

        SMUTimeoutError
            If instrument isn't busy, but a timeout occured while trying to download the data.

        Returns
        -------
        dict
            Dictionary of values from instrument. They are 'time', 'measure', 'source.'

        """
        if self.check_busy():
            raise BusyError('SMU is Busy on readBuffer() call')
        self.get_errors()
        # print('calling print buffer')
        # self.tsp_trace()
        self.write(
            'printbuffer(1,bf.n,bf.relativetimestamps,bf.readings,bf.sourcevalues)'
        )
        # read and parse
        read = False
        iFails = 0
        t0 = time.time()
        t1 = 0
        # print('starting read loop')
        # self.tsp_trace()
        while not read and t1 < self.timeout:
            if self.get_output_bit(self.stb_reg['MAV']) == 1:
                try:
                    strOut = self.read()
                    strOut = strOut.split(', ')
                    n = len(strOut)
                    readOut = np.zeros(n)
                    i = 0
                    for s in strOut:
                        readOut[i] = float(s)
                        i += 1
                    data = {
                        'time': readOut[np.arange(0, n, 3)],
                        'measure': readOut[np.arange(1, n, 3)],
                        'source': readOut[np.arange(2, n, 3)],
                    }
                    read = True
                # incase something is read that we don't want
                except Exception as ex:
                    template = 'An exception of type {0} occurred. Arguments:\n{1!r}'
                    message = template.format(type(ex).__name__, ex.args)
                    print(message)
                    iFails += 1
                    data = 0
                    pass
            # print count of failed reads
            if self.logs:
                sys.stdout.write('\rFailed buffer reads: %i' % (iFails + 1))
                sys.stdout.flush()

            iFails += 1
            t1 = time.time() - t0
        # print('cleaning up')
        # self.tsp_trace()
        if self.logs:
            print('')
        if not read:
            raise SMUTimeoutError('Timeout on printBuffer read')

        # clear buffer to avoid a memory leak
        # print('clearing buffer')
        # self.tsp_trace()
        self.write('bf.clear()')
        if self.logs:
            print('Buffer read and cleared from machine memory')
            self.tsp_trace()
        # MAV bit will sometimes stay high after buffer is read out, even though nothing
        # is actually in the output queue. This is meant to deal with that specifc cas(1/100 times)
        # but still print/make it obviosu that it happened.
        try:
            self.flush_readout()
        except Exception as ex:
            template = 'An exception of type {0} occurred. Arguments:\n{1!r}'
            message = template.format(type(ex).__name__, ex.args)
            print(message)
            print('Printing nothing from SMU to reset MAV bit')
            self.printNumber('')
            self.flush_readout()
            self.tsp_trace()
            self.write('eventlog.clear()')
            pass

        if deleteBuffer:
            self.write('buffer.delete(bf)')
            self.write('collectgarbage()')
        # print('Checking after data fetched')
        # self.tsp_trace()
        return data

    def load_script(self, project_name: str, script_name: str, file_names: list[str]):
        """
        Load a tsp project saved in the package's TSP directory.

        Parameters
        ----------
        project_name : str
            The name of the project, directory name in instruments//TSP.

        script_name : str
            The name to save the script as on the tsp instrument memory.

        file_names : list [str]
            List of files in the project, in order to be loaded onto the tsp
            instrument.

        Returns
        -------
        None.

        """
        code_dir = dirname(dirname(dirname(__file__)))
        proj_dir = join(code_dir, 'TSP', project_name)
        self.write('script.delete("' + script_name + '")')
        self.write('loadscript ' + script_name)
        if type(file_names) is str:
            file_names = [file_names]
        for tsp_file in file_names:
            with open(join(proj_dir, tsp_file), 'r') as f:
                for line in f:
                    self.write(line)
        self.write('endscript')
        self.write(script_name + '.save()')
        self.write('collectgarbage()')
