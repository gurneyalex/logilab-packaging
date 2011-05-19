# -*- coding: utf-8 -*-
#
# Copyright (c) 2004-2011 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

from os import linesep
import sys

from logilab.devtools.lgp import LGP
from logilab.devtools.lgp.setupinfo import SetupInfo


@LGP.register
class Project(SetupInfo):
    """Print the project name and/or release version of the project.

    Useful in external build scripts to avoid raw parsing
    """
    name = "project"
    arguments = "[--name | --release]"
    options = [('name',
                {'action': 'store_true',
                 'dest' : "name",
                 'help': "print project name",
                 'group': 'project'
                }),
               ('release',
                {'action': 'store_true',
                 'dest' : "release",
                 'help': "print project release",
                 'group': 'project'
                }),
              ]

    def run(self, args):
        if not set(args).intersection(set(['--name','--release'])):
            self.config.release = self.config.name = True
        if self.config.name:
            sys.__stdout__.write(self.get_upstream_name() + linesep)
        if self.config.release:
            sys.__stdout__.write(self.get_upstream_version() + linesep)

    def guess_environment(self):
        pass
