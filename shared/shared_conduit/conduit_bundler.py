###############################################################################
# Copyright (c) 2019, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory
# Written by the Merlin dev team, listed in the CONTRIBUTORS file.
# <merlin@llnl.gov>
#
# LLNL-CODE-797170
# All rights reserved.
# This file is part of merlin-spellbook.
#
# For details, see https://github.com/LLNL/merlin-spellbook and
# https://github.com/LLNL/merlin.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
###############################################################################

"""
For more info about conduit, see:
http://llnl-conduit.readthedocs.io/en/latest/user.html.

For documentation and examples, check out the conduit unit tests at:
https://github.com/LLNL/conduit/tree/master/src/tests
"""
import os
import logging
import sys

import numpy as np

import conduit
import conduit.relay.io


LOG = logging.getLogger(__name__)

def determine_protocol(fname):
    """
    Determines a file protocol based on file name extension.
    """
    _, ext = os.path.splitext(fname)
    if ext.startswith("."):
        protocol = ext.lower().strip(".")
    else:
        raise ValueError(fname + " needs an ext (eg .hdf5) to determine protocol!")
    # Map .h5 to .hdf5
    if protocol == "h5":
        protocol = "hdf5"
    return protocol

def pack_conduit_node_from_dict(d):
    """
    If d is a dict, returns a conduit node, unpacked recursively using the
    dictionary to create the conduit hierarchy.

    If d is not a dict, simply returns d, to avoid extra conduit nodes being
    created. The intent is that the return value is then assigned to a conduit
    node by the caller and conduit will handle packing it appropriately.

    Conduit currently supports following basic types:
    int32, uint32, int64, uint64, float32, float64, numpy arrays of (uint32,
    uin64, float32, float64), strings.

    There is a bug in the current version of conduit that prevents usage of
    numpy arrays of signed ints.

    Notably, lists, dicts, tuples, and unicode strings can not be assigned
    directly as a conduit node. numpy is your friend. This method will auto
    convert tuples into numpy arrays of float64, will iterate over lists and
    give them each a separate entry in the hierarchy, labeled by their index,
    and assume any dicts are meant as part of the hierarchy description so the
    dict hierarchy ends up in the conduit hierarchy.
    """
    if isinstance(d, dict):
        node = conduit.Node()
        for k in d:
            try:
                node[str(k)] = pack_conduit_node_from_dict(d[k])
            except TypeError:
                try:
                    if isinstance(d[k], list):
                        node[str(k)] = create_conduit_node_from_list(d[k])
                    elif isinstance(d[k], tuple):
                        node[str(k)] = np.array(list(d[k]), dtype='float64')
                    else:
                        LOG.error(
                            'Conduit does not support following value', k, d[k])
                except TypeError:
                    LOG.error(
                        'Conduit does not support following value', k, d[k])
        return node
    else:
        if d is None:
            return "None"
        return d


def create_conduit_node_from_list(results, prefix=''):
    """
    Results must be a list of dictionaries or conduit nodes, each of which can
    have dictionaries, but all leaves must be a type that conduit can support
    (see description in pack_conduit_node_from_dict).
    """
    n = conduit.Node()
    for i in range(0, len(results)):
        try:
            n[str(prefix) + str(i)] = pack_conduit_node_from_dict(results[i])
        except TypeError:
            LOG.error("Unable to pack ", results[i])

    return n


def dump_node(conduit_node, fname,
              dump_options=(("hdf5/chunking/threshold", 2000),
                            ("hdf5/chunking/chunk_size", 2000))):
    """
    Saves a conduit node to disk. Protocol determined by fname extension.
    Protocol can be conduit_bin, hdf5, json,
    silo, json64, and probably others. Will turn on compression for hdf5.
    """
    protocol = determine_protocol(fname)
    # If hdf5, turn on compression.
    if protocol == 'hdf5':
        save_options = conduit.Node()
        for opt in dump_options:
            save_options[opt[0]] = opt[1]
        try:
            conduit.relay.io.save(conduit_node, fname, protocol,
                                  options=save_options)
        except TypeError:  # Conduit version needs to be updated.
            LOG.error("Unable to customize save: please upgrade conduit to "
                      "expose save options!")
            conduit.relay.io.save(conduit_node, fname, protocol)
    else:
        conduit.relay.io.save(conduit_node, fname, protocol)


def load_node(fname):
    """
    Read a conduit file written with protocol into memory
    """
    protocol = determine_protocol(fname)
    if os.path.exists(fname):
        n = conduit.Node()
        conduit.relay.io.load(n, fname, protocol)
        return n
    else:
        raise IOError('No such file: ' + fname)
