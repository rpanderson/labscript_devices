#####################################################################
#                                                                   #
# /labscript_devices/IMAQdxCamera/labscript_devices.py              #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
from labscript_utils import dedent

from labscript import TriggerableDevice, set_passed_properties
import numpy as np
import labscript_utils.h5_lock
import h5py

class IMAQdxCamera(TriggerableDevice):
    description = 'IMAQdx Camera'

    @set_passed_properties(
        property_names={
            "connection_table_properties": ["serial_number", "orientation"],
            "device_properties": [
                "trigger_edge_type",
                "trigger_duration",
                "minimum_recovery_time",
                "imaqdx_attributes",
            ],
        }
    )
    def __init__(
        self,
        name,
        parent_device,
        connection,
        serial_number,
        orientation='side',
        trigger_edge_type='rising',
        trigger_duration=None,
        minimum_recovery_time=0,
        imaqdx_attributes=None,
        **kwargs
    ):
        """A camera to be controlled using NI IMAQdx and triggered with a digital edge.
        Serial number should be an int or hex string of the camera's serial number, this
        will be used by IMAQdx to identify the camera. Configuring the camera is done by
        passing a dictionary as the keyword argument imaqdx_attributes. These are the
        same attributes settable in NI MAX. After adding an IMAQdxCamera to your
        connection table, a dictionary of these attributes can be obtained from the
        BLACS tab, appropriate for copying and pasting into your connection table and
        passing in as the imaqdx_attributes keyword argument in order to customise the
        attributes you are interested in configuring."""
        self.trigger_edge_type = trigger_edge_type
        self.minimum_recovery_time = minimum_recovery_time
        self.trigger_duration = trigger_duration
        self.orientation = orientation
        if isinstance(serial_number, (str, bytes)):
            serial_number = int(serial_number, 16)
        self.serial_number = serial_number
        self.BLACS_connection = str(self.serial_number)[2:]
        if imaqdx_attributes is None:
            imaqdx_attributes = {}
        self.imaqdx_attributes = imaqdx_attributes
        self.exposures = []
        TriggerableDevice.__init__(self, name, parent_device, connection, **kwargs)

    def expose(self, t, name, frametype='', trigger_duration=None):
        """Request an exposure at the given time. A trigger will be produced by the
        parent trigger object, with duration trigger_duration, or if not specified, of
        self.trigger_duration. The frame should have a `name, and optionally a
        `frametype`, both strings. These determine where the image will be stored in the
        hdf5 file. `name` should be a description of the image being taken, such as
        "insitu_absorption" or "fluorescence" or similar. `frametype` is optional and is
        the type of frame being acquired, for imaging methods that involve multiple
        frames. For example an absorption image of atoms might have three frames:
        'probe', 'atoms' and 'background'. For this one might call expose three times
        with the same name, but three different frametypes.
        """
        # Backward compatibility with code that calls expose with name as the first
        # argument and t as the second argument:
        if isinstance(t, str) and isinstance(name, (int, float)):
            t, name = name, t
        if trigger_duration is None:
            trigger_duration = self.trigger_duration
        if trigger_duration is None:
            msg = """%s %s has not had an trigger_duration set as an instantiation
                argument, and none was specified for this exposure"""
            raise ValueError(dedent(msg) % (self.description, self.name))
        if not trigger_duration > 0:
            msg = "trigger_duration must be > 0, not %s" % str(trigger_duration)
            raise ValueError(msg)
        self.trigger(t, trigger_duration)
        self.exposures.append((t, name, frametype, trigger_duration))
        return trigger_duration

    def generate_code(self, hdf5_file):
        self.do_checks()
        vlenstr = h5py.special_dtype(vlen=str)
        table_dtypes = [
            ('time', float),
            ('name', vlenstr),
            ('frametype', vlenstr),
            ('trigger_duration', float),
        ]
        data = np.array(self.exposures, dtype=table_dtypes)
        group = self.init_device_group(hdf5_file)
        if self.exposures:
            group.create_dataset('EXPOSURES', data=data)
