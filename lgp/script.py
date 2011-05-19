# -*- coding: utf-8 -*-
#
# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

import os
import sys
import logging
import glob
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp import LGP, CONFIG_FILE, SCRIPTS_DIR, HOOKS_DIR
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException


@LGP.register
class Script(SetupInfo):
    """Execute script in a chrooted distribution.

    Full list of scripts is provided with no argument
    """
    name = "script"
    options = [('command',
                {'type': 'choice',
                 'choices': [os.path.basename(x)
                             for x
                             in glob.glob(os.path.join(SCRIPTS_DIR, '*'))],
                 'dest': 'command',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "script command to run with pbuilder"
                }),
              ]
    arguments = "[options] [<script> FILES...]"
    #min_args = 1
    cmd = "IMAGE=%s DIST=%s ARCH=%s %s %s %s --configfile %s --hookdir %s -- %s %s"
    pbuilder_cmd = "/usr/sbin/pbuilder execute"
    sudo_cmd = "/usr/bin/sudo -E"

    def go_into_package_dir(self, arguments):
        pass

    def _set_package_format(self):
        pass

    def run(self, args):

        #  command, = glob.glob(os.path.join(SCRIPTS_DIR, self.config.command))
        if len(self.arguments)==0:
            commands = dict(self.options)['command']['choices']
            logging.info('available command(s): %s', commands)
        else:
            commands = [c for c in glob.glob(os.path.join(SCRIPTS_DIR, self.config.command))
                        if os.path.basename(c)==self.config.command]

        if not commands:
            raise LGPException("command '%s' not found. Please check commands in %s"
                               % (self.config.command, SCRIPTS_DIR))
        if len(self.arguments)==0:
            sys.exit()

        for arch in self.architectures:
            for distrib in self.distributions:
                for command in commands:
                    image = self.get_basetgz(distrib, arch)

                    cmd = self.cmd % (image, distrib, arch, self.setarch_cmd, self.sudo_cmd,
                                      self.pbuilder_cmd, CONFIG_FILE, HOOKS_DIR, command,
                                      ' '.join(self.arguments))

                    logging.info("execute script '%s' with arguments: %s",
                                 command, ' '.join(self.arguments))
                    logging.debug("run command: %s", cmd)
                    try:
                        check_call(cmd, stdout=sys.stdout, shell=True,
                                   env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image})
                    except CalledProcessError, err:
                        raise LGPCommandException('an error occured in %s process' %
                                                  self.name, err)

