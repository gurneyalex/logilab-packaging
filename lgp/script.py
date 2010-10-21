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
""" lgp script [options] [<script> FILES...]

    Execute script in a chrooted distribution
    Full list of scripts is provided with no argument
"""
__docformat__ = "restructuredtext en"

import os
import sys
import logging
import glob
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp.setup import Setup
from logilab.devtools.lgp.exceptions import LGPException
from logilab.devtools.lgp import CONFIG_FILE, SCRIPTS_DIR, HOOKS_DIR


def run(args):
    """Main function of lgp script command"""
    try :
        script = Script(args)

        #  command, = glob.glob(os.path.join(SCRIPTS_DIR, script.config.command))
        if len(script.arguments)==0:
            commands = dict(script.options)['command']['choices']
            logging.info('available command(s): %s', commands)
        else:
            commands = [c for c in glob.glob(os.path.join(SCRIPTS_DIR, script.config.command))
                        if os.path.basename(c)==script.config.command]

        if not commands:
            raise LGPException("command '%s' not found. Please check commands in %s"
                               % (script.config.command, SCRIPTS_DIR))
        if len(script.arguments)==0:
            sys.exit()

        for arch in script.architectures:
            for distrib in script.distributions:
                for command in commands:
                    image = script.get_basetgz(distrib, arch)

                    cmd = script.cmd % (image, distrib, arch, script.setarch_cmd, script.sudo_cmd,
                                        script.builder_cmd, CONFIG_FILE,
                                        HOOKS_DIR, command, ' '.join(script.arguments))

                    # run script command
                    logging.info("execute script '%s' with arguments: %s",
                                 command, ' '.join(script.arguments))
                    logging.debug("run command: %s", cmd)
                    try:
                        check_call(cmd, stdout=sys.stdout, shell=True,
                                   env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image})
                    except CalledProcessError:
                        logging.error('an error occured in script process: %s', cmd)

    except NotImplementedError, exc:
        logging.error(exc)
        return 2
    except LGPException, exc:
        logging.critical(exc)
        return exc.exitcode()


class Script(Setup):
    """Helper class for running scripts

    Specific options are added. See lgp script --help
    """
    name = "lgp-script"

    options = (('command',
                {'type': 'choice',
                 'choices': [os.path.basename(x)
                             for x
                             in glob.glob(os.path.join(SCRIPTS_DIR, '*'))],
                 'dest': 'command',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "script command to run with pbuilder"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Setup, self).__init__(args, options=self.options, usage=__doc__)
        # TODO encapsulate builder logic into specific InternalBuilder class
        self._pbuilder_cmd = "/usr/sbin/pbuilder execute"
        self.cmd = "IMAGE=%s DIST=%s ARCH=%s %s %s %s --configfile %s --hookdir %s -- %s %s"
