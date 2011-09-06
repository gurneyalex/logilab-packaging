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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.

import os
import sys
import glob
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp import LGP, CONFIG_FILE, HOOKS_DIR, SCRIPTS_DIR
from logilab.devtools.lgp.setupinfo import SetupInfo

@LGP.register
class Shell(SetupInfo):
    """Run a script or interactive shell in a chrooted distribution"""

    name = "shell"
    options = SetupInfo.options + [
               ('command',
                {'type': 'choice',
                 'choices': [os.path.basename(x)
                             for x in glob.glob(os.path.join(SCRIPTS_DIR, '*'))],
                 'dest': 'command',
                 'short': 'c',
                 'metavar': '<command>',
                 'help': 'script to run in pbuilder'
                }),
               ('result',
                {'type': 'string',
                 'default' : '~/dists',
                 'dest' : "dist_dir",
                 'short': 'r',
                 'metavar': "<directory>",
                 'help': "mount compilation results directory"
                })
    ]
    arguments = "[options] [<script> [args...]]"
    cmd = "%s %s --configfile %s --hookdir %s --bindmounts %s --othermirror %s --override-config %s %s"
    pbuilder_cmd = "/usr/sbin/pbuilder %s"
    sudo_cmd = "/usr/bin/sudo -E"

    def go_into_package_dir(self, arguments):
        pass

    def _set_package_format(self):
        pass

    def _prune_pkg_dir(self):
        pass

    def other_mirror(self, resultdir):
        dirname, basename = os.path.split(self.get_distrib_dir(resultdir))
        return "'deb file://%s %s/'" % (dirname, basename)

    def run(self, args):
        if not self.config.command and len(args) == 0:
            command = "login"
            script = ""
        else:
            command = "execute"
            if not self.config.command:
                self.config.command = args[0]
                args = args[1:]
            script = os.path.join(SCRIPTS_DIR, self.config.command)

        if self.config.command and not os.path.exists(script):
            commands = dict(self.options)['command']['choices']
            self.logger.info('available command(s): %s', commands)
            sys.exit(1)

        for arch in self.get_architectures():
            for distrib in self.distributions:
                image = self.get_basetgz(distrib, arch)
                resultdir = self.get_distrib_dir(distrib)
                other_mirror = self.other_mirror(resultdir)

                cmd = self.cmd % (self.sudo_cmd, (self.pbuilder_cmd % command), CONFIG_FILE, HOOKS_DIR,
                                  resultdir, other_mirror, script, ' '.join(args))

                if command == "login":
                    msg = "run shell in %s/%s image" % (distrib, arch)
                else:
                    msg = "run script '%s' in %s/%s image with arguments: %s" % (script, distrib, arch, ' '.join(args))
                self.logger.info(msg)
                self.logger.debug("run command: %s", cmd)

                try:
                    check_call(cmd, shell=True,
                               env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image})
                except CalledProcessError, err:
                    self.logger.warn("returned non-zero exit status %s", err.returncode)


