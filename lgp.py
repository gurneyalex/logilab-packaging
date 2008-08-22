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

def run(args):
    parser = OptionParser()
    parser.usage = 'lgp COMMAND [options] <pkgdir> ...'
    COMMANDS = [('prepare', 'logilab.devtools.preparedist',
                 'process to prepare distrib'),
                ('build', 'logilab.devtools.buildpackage',
                 'build debian and source packages'),
                ('tag', 'logilab.devtools.tagpackage',
                 'tag package repository'),
                ('check', 'logilab.devtools.checkpackage',
                 'check that package is ready to be built'),
                ('info', 'logilab.devtools.info',
                 'extract info from __pkginfo__'),
                ('import', 'logilab.devtools.importpackage',
                 'import source from a scm resource'),
                ]

    for item in COMMANDS:
        parser.add_command(*item)
    run_, options, args = parser.parse_command(sys.argv[1:])
    pkgdir = osp.abspath(args and args[0] or os.getcwd())
    return run_(pkgdir, options, args[1:])

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))

