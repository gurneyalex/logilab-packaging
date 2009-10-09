# -*- coding: utf-8 -*-
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" lgp piuparts [options] FILES...

    Execute piuparts in a chrooted distribution
"""
__docformat__ = "restructuredtext en"

import os
import sys
import logging
from subprocess import check_call, CalledProcessError
from debian_bundle import (deb822, debfile)

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException


def run(args):
    """Main function of lgp piuparts command"""
    try :
        piuparts = Piuparts(args)

        if len(piuparts.arguments)==0:
            raise LGPException("need command line arguments: names of packages or package files")

        for arg in piuparts.arguments:
            if os.path.isfile(arg):
                packages = list()
                if arg.endswith('.changes'):
                    f        = deb822.Changes(file(arg))
                    arch     = f['Architecture']
                    distrib  = f['Distribution']
                    packages = [deb['name'] for deb in f['Files'] if deb['name'].endswith('.deb')]
                    logging.debug("read information from .changes: %s/%s"
                                  % (distrib, arch))
                elif arg.endswith('.deb'):
                    deb     = debfile.DebFile(arg)
                    arch    = deb.debcontrol()['Architecture']
                    distrib = deb.changelog().distributions
                    packages.append(arg)
                    logging.debug("read information from .deb: %s/%s"
                                  % (distrib, arch))

                piuparts.architectures = piuparts.get_architectures([arch])
                # we loop on different architectures of available base images if arch-independant
                for arch in piuparts.architectures:
                    cmd = ['sudo', 'piuparts', '--no-symlinks',
                           '--warn-on-others',
                           #'--skip-minimize',
                           '--keep-sources-list',
                           #'--list-installed-files',
                           '--skip-cronfiles-test',
                           # the development repository can be somewhat buggy...
                           '--no-upgrade-test',
                           '-b', piuparts.get_basetgz(distrib, arch),
                           # just violent but too many false positives otherwise
                           '-i', "/var/lib/dpkg/triggers/File",
                           '-i', "/etc/shadow",
                           '-i', "/etc/shadow-",
                           '-i', "/var/lib/dpkg/triggers/pysupport",
                           '-I', "'/usr/share/pycentral-data.*'",
                           '-I', "'/usr/local/lib/python.*'",
                          ] + packages

                    if piuparts.config.use_apt:
                        cmd.insert(3, '--apt')

                    logging.info("execute piuparts: %s" % ' '.join(cmd))
                    # run piuparts command
                    try:
                        check_call(cmd, stdout=sys.stdout)
                    except CalledProcessError, err:
                        raise LGPCommandException('an error occured in piuparts execution', err)

    except LGPException, exc:
        logging.critical(exc)
        return 1


class Piuparts(SetupInfo):
    """Helper class for running piuparts

    Specific options can be added. See lgp piuparts --help
    """
    name = "lgp-piuparts"
    options = (('use-apt',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "use_apt",
                 'short': 'A',
                 'help': "be treated as package names and installed via apt-get instead of dpkg -i"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Piuparts, self).__init__(arguments=args, options=self.options, usage=__doc__)
