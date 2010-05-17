# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
""" lgp setup [options]

    Prepare the chrooted distribution
"""
__docformat__ = "restructuredtext en"

import os
import sys
import logging
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException
from logilab.devtools.lgp.check import check_keyrings
from logilab.devtools.lgp import CONFIG_FILE, HOOKS_DIR


def run(args):
    """ Main function of lgp setup command """
    try :
        setup = Setup(args)
        if os.geteuid()!=0:
            logging.debug('lgp setup should be run as root. sudo is used internally.')
            sudo_cmd = "sudo "
        else:
            sudo_cmd = ""

        if setup.config.command == "create":
            setup.logger = logging
            check_keyrings(setup)

        for arch in setup.architectures:
            for distrib in setup.distributions:
                if setup.config.command == "create":
                    cmd = sudo_cmd + "IMAGE=%s DIST=%s ARCH=%s pbuilder create --override-config --configfile %s"
                elif setup.config.command == "update":
                    cmd = sudo_cmd + "IMAGE=%s DIST=%s ARCH=%s pbuilder update --override-config --configfile %s"
                elif setup.config.command == "clean":
                    logging.debug("cleans up directory specified by configuration BUILDPLACE and APTCACHE")
                    cmd = sudo_cmd + "IMAGE=%s DIST=%s ARCH=%s pbuilder clean --configfile %s"
                elif setup.config.command == "dumpconfig":
                    cmd = sudo_cmd + "IMAGE=%s DIST=%s ARCH=%s pbuilder dumpconfig --configfile %s"
                    sys.stdout = sys.__stdout__

                image = setup.get_basetgz(distrib, arch, check=False)
                # workaround: http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#amd64i386
                if 'amd64' in setup.get_architectures(['current']) and arch == 'i386' and os.path.exists('/usr/bin/linux32'):
                    cmd = 'linux32 ' + cmd
                cmd = cmd + ' --hookdir %s'
                cmd = cmd % (image, distrib, arch, CONFIG_FILE, HOOKS_DIR)

                # run setup command
                logging.info(setup.config.command + " image '%s' for '%s/%s'"
                             % (image, distrib, arch))
                try:
                    check_call(cmd.split(), stdout=sys.stdout,
                               env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image})
                except CalledProcessError, err:
                    # pbuilder dumpconfig command always returns exit code 1.
                    # Fix to normal exit status
                    if setup.config.command == "dumpconfig":
                        continue
                    logging.error('an error occured in setup process: %s' % cmd)

    except NotImplementedError, exc:
        logging.error(exc)
        return 2
    except LGPException, exc:
        logging.critical(exc)
        return exc.exitcode()


class Setup(SetupInfo):
    """ Environment setup checker class

    Specific options are added. See lgp setup --help
    """
    name = "lgp-setup"

    options = (('command',
                {'type': 'choice',
                 'choices': ('create', 'update', 'dumpconfig', 'clean',),
                 'dest': 'command',
                 'default' : 'dumpconfig',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "command to run with pbuilder"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Setup, self).__init__(arguments=args, options=self.options, usage=__doc__)
