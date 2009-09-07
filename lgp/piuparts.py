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
import logging
import glob
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp import CONFIG_FILE, SCRIPTS_DIR


def run(args):
    """Main function of lgp piuparts command"""
    try :
        piuparts = Piuparts(args)

        command, = glob.glob(os.path.join(SCRIPTS_DIR, piuparts.config.command))
        for arch in piuparts.architectures:
            for distrib in piuparts.distributions:
                logging.info("execute piuparts '%s' with parameters: %s"
                             % (piuparts.config.command, ' '.join(piuparts.arguments)))
                cmd = "sudo IMAGE=%s DIST=%s ARCH=%s pbuilder execute --configfile %s %s -- %s "
                image = piuparts.get_basetgz(distrib, arch, check=False)
                cmd = cmd % (image, distrib, arch, CONFIG_FILE, command, piuparts.arguments)

                # run piuparts command
                try:
                    check_call(cmd.split(), env={'DIST': distrib, 'ARCH': arch,
                                                 'IMAGE': image})
                except CalledProcessError, err:
                    raise LGPCommandException('an error occured in piuparts execution', err)

    except NotImplementedError, exc:
        logging.error(exc)
        return 1
    except LGPException, exc:
        logging.critical(exc)
        return 1


class Piuparts(SetupInfo):
    """Helper class for running piupartss

    Specific options are added. See lgp piuparts --help
    """
    name = "lgp-piuparts"

    options = (('command',
                {'type': 'choice',
                 'dest': 'command',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "piuparts command to run with pbuilder"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Piuparts, self).__init__(arguments=args, options=self.options, usage=__doc__)
