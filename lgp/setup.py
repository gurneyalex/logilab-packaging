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

        if os.geteuid() != 0:
            logging.warn('lgp setup should be run as root')
        if setup.config.command == "create":
            setup.logger = logging
            check_keyrings(setup)
        if setup.config.command in ("create", "update"):
            setup.cmd += " --override-config"
        elif setup.config.command == "clean":
            logging.debug("cleans up directory specified by configuration BUILDPLACE and APTCACHE")
        elif setup.config.command == "dumpconfig":
            sys.stdout = sys.__stdout__

        for arch in setup.architectures:
            for distrib in setup.distributions:
                image = setup.get_basetgz(distrib, arch, check=False)

                # don't manage symbolic file in create and update command
                if os.path.islink(image) and setup.config.command in ("create", "update"):
                    logging.warning("skip symbolic link used for image: %s (-> %s)"
                                    % (image, os.path.realpath(image)))
                    continue

                cmd = setup.cmd % (image, distrib, arch, setup.setarch_cmd, setup.sudo_cmd,
                                   setup.builder_cmd, CONFIG_FILE, HOOKS_DIR)

                # run setup command
                logging.debug("run command: %s" % cmd)
                logging.info(setup.config.command + " image '%s' for '%s/%s'"
                             % (image, distrib, arch))
                try:
                    check_call(cmd, stdout=sys.stdout, shell=True,
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
        # TODO encapsulate builder logic into specific InternalBuilder class
        self._pbuilder_cmd = "/usr/sbin/pbuilder %s" % self.config.command
        self.cmd = "IMAGE=%s DIST=%s ARCH=%s %s %s %s --configfile %s --hookdir %s"

    def get_basetgz(self, *args, **kwargs):
        self.arch = args[1] # used in build_cmd property later
        return super(Setup, self).get_basetgz(*args, **kwargs)

    @property
    def builder_cmd(self):
        return self._pbuilder_cmd

    @property
    def setarch_cmd(self):
        setarch_cmd = ""
        # workaround: http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#amd64i386
        # FIXME use `setarch` command for much more supported platforms
        if 'amd64' in self.get_architectures(['current']) and self.arch == 'i386' and os.path.exists('/usr/bin/linux32'):
            logging.info('using linux32 command to build i386 image from amd64 compatible architecture')
            setarch_cmd = 'linux32'
        return setarch_cmd

    @property
    def sudo_cmd(self):
        sudo_cmd = ""
        if os.geteuid() != 0:
            logging.debug('lgp setup should be run as root. sudo is used internally.')
            sudo_cmd = "/usr/bin/sudo -E"
        return sudo_cmd
