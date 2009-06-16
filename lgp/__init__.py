# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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

import sys
import os, os.path as osp
from logilab.common.optparser import OptionParser

CONFIG_FILE = '/etc/lgp/pbuilderrc'
HOOKS_DIR = '/etc/lgp/hooks'


def run(args):
    parser = OptionParser()
    parser.usage = 'lgp COMMAND [options] <pkgdir> ...'
    COMMANDS = [('prepare', 'logilab.devtools.lgp.preparedist',
                 'process to prepare distrib'),
                ('build', 'logilab.devtools.lgp.build',
                 'build debian and source packages'),
                ('tag', 'logilab.devtools.lgp.tag',
                 'tag package repository'),
                ('check', 'logilab.devtools.lgp.check',
                 'check that package is ready to be built'),
                ('setup', 'logilab.devtools.lgp.setup',
                 'prepare a chrooted distribution'),
                ('login', 'logilab.devtools.lgp.login',
                 'Log into a chrooted distribution'),
                ('clean', 'logilab.devtools.lgp.clean',
                 'clean repository'),
               ]

    if len(sys.argv) <= 1:
        return parser.usage
    elif sys.argv[1] in ("build", "check", "clean", "template", "setup",
                         "login", "tag"):
        exec 'from logilab.devtools.lgp.%s import run' % sys.argv[1]
        return run(args[1:])
    else:
        for item in COMMANDS:
            parser.add_command(*item)
        run_, options, args = parser.parse_command(sys.argv[1:])
        pkgdir = osp.abspath(args and args[0] or os.getcwd())
        return run_(pkgdir, options, args[1:])


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
