import time

from .ophydobj import (OphydObject, DeviceStatus)
from .components import (Component, DynamicComponent)
from ..utils import TimeoutError


class ComponentMeta(type):
    '''Creates attributes for Components by inspecting class definition'''

    def __new__(cls, name, bases, clsdict):
        clsobj = super().__new__(cls, name, bases, clsdict)

        # map component attribute names to Component classes
        sig_dict = {attr: value for attr, value in clsdict.items()
                    if isinstance(value, (Component, DynamicComponent))}

        # maps component to attribute names
        clsobj._sig_attrs = {cpt: name
                             for name, cpt in sig_dict.items()}

        for cpt, attr in clsobj._sig_attrs.items():
            cpt.attr = attr

        # List Signal attribute names.
        clsobj.signal_names = list(sig_dict.keys())

        # Store EpicsSignal objects (only created once they are accessed)
        clsobj._signals = {}
        return clsobj


class DeviceBase(metaclass=ComponentMeta):
    """Base class for device objects

    This class provides attribute access to one or more Signals, which can be
    a mixture of read-only and writable. All must share the same base_name.
    """
    def __init__(self, prefix, read_signals=None):
        self.prefix = prefix
        if self.signal_names and prefix is None:
            raise ValueError('Must specify prefix if device signals are being '
                             'used')

        if read_signals is None:
            read_signals = self.signal_names

        self.read_signals = read_signals

        # Instantiate non-lazy signals
        [getattr(self, attr) for cpt, attr in self._sig_attrs.items()
         if not cpt.lazy]

    def wait_for_connection(self, all_signals=False, timeout=2.0):
        '''Wait for signals to connect

        Parameters
        ----------
        all_signals : bool, optional
            Wait for all signals to connect (including lazy ones)
        timeout : float or None
            Overall timeout
        '''
        names = [attr for cpt, attr in self._sig_attrs.items()
                 if not cpt.lazy or all_signals]

        # Instantiate first to kickoff connection process
        signals = [getattr(self, name) for name in names]

        t0 = time.time()
        while timeout is None or (time.time() - t0) < timeout:
            connected = [sig.connected for sig in signals]
            if all(connected):
                return
            time.sleep(min((0.05, timeout / 10.0)))

        unconnected = [sig.name for sig in signals
                       if not sig.connected]

        raise TimeoutError('Failed to connect to all signals: {}'
                           ''.format(', '.join(unconnected)))

    @property
    def connected(self):
        return all(signal.connected for name, signal in self._signals.items())

    def read(self):
        # map names ("data keys") to actual values
        values = {}
        for name in self.read_signals:
            signal = getattr(self, name)
            values.update(signal.read())

        return values

    def describe(self):
        desc = {}
        for name in self.read_signals:
            signal = getattr(self, name)
            desc.update(signal.describe())

        return desc

    def stop(self):
        "to be defined by subclass"
        pass

    def trigger(self):
        "to be defined by subclass"
        pass


class OphydDevice(DeviceBase, OphydObject):
    SUB_ACQ_DONE = 'acq_done'  # requested acquire

    def __init__(self, prefix=None, read_signals=None,
                 name=None, alias=None):
        if name is None:
            name = prefix

        OphydObject.__init__(self, name=name, alias=alias)
        DeviceBase.__init__(self, prefix, read_signals=read_signals)

        # set should work using signature-stuff

    @property
    def trigger_signals(self):
        names = [attr for cpt, attr in self._sig_attrs.items()
                 if cpt.trigger_value is not None]

        return [getattr(self, name) for name in names]

    def trigger(self, **kwargs):
        """Start acquisition"""
        # TODO mass confusion here
        signals = self.trigger_signals
        if len(signals) > 1:
            raise NotImplementedError('TODO more than one trigger')
        elif len(signals) == 0:
            raise RuntimeError('Device has no trigger signal(s)')

        acq_signal = signals[0]
        status = DeviceStatus(self)
        self.subscribe(status._finished,
                       event_type=self.SUB_ACQ_DONE, run=False)

        def done_acquisition(**kwargs):
            self._done_acquiring()

        acq_signal.put(1, wait=False, callback=done_acquisition)
        return status

    def _done_acquiring(self, **kwargs):
        '''Call when acquisition has completed.'''
        self._run_subs(sub_type=self.SUB_ACQ_DONE,
                       success=True, **kwargs)

        self._reset_sub(self.SUB_ACQ_DONE)
