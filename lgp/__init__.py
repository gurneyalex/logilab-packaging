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
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

import sys
import logging

import logilab.common.clcommands as cli

from logilab.devtools.__pkginfo__ import description, version
from logilab.devtools.lgp.exceptions import LGPException


LGP_CONFIG_FILE = '/etc/lgp/lgprc'
LGP_SUITES      = '/usr/share/debootstrap/scripts/'
CONFIG_FILE     = '/etc/lgp/pbuilderrc'
HOOKS_DIR       = '/var/lib/logilab-packaging/hooks'
SCRIPTS_DIR     = '/var/lib/logilab-packaging/scripts'
LOG_FORMAT = '%(levelname)1.1s:%(name)s: %(message)s'


class LGPCommandLine(cli.CommandLine):

    def run(self, args):
        """main command line access point (from clcommands):
        * instanciate logger
        * handle global options (-h/--help, --version, --rc-file)
        * check command
        * change to project directory (XXX)
        * run command

        :returns: unix error code
        """
        try:
            super(LGPCommandLine, self).run(args)
        except LGPException, exc:
            logging.critical(exc)
            sys.exit(exc.exitcode())


LGP = LGPCommandLine('lgp', doc=description, rcfile=LGP_CONFIG_FILE,
                     version=version, logthreshold=logging.INFO)


__all__ = ['LGP', 'clean', 'build', 'check', 'tag', 'setup', 'shell']
