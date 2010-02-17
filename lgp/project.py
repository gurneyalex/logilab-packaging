#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2004-2008 LOGILAB S.A. (Paris, FRANCE).
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
""" lgp project [options]

    Print project information
"""
__docformat__ = "restructuredtext en"

from os import linesep
import sys
import logging

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException


def run(args):
    """Main function of lgp project command"""
    try :
        project = Project(args)
        if not set(args).intersection(set(['--name','--release'])):
            project.config.release = project.config.name = True
        if project.config.name:
            sys.__stdout__.write(project.get_upstream_name() + linesep)
        if project.config.release:
            sys.__stdout__.write(project.get_upstream_version() + linesep)
    except LGPException, exc:
        logging.critical(exc)
        return exc.exitcode()


class Project(SetupInfo):
    """Lgp project class

    Only used to print the current name and release of the project
    """
    name = "lgp-project"
    options = (('name',
                {'action': 'store_true',
                 'dest' : "name",
                 'help': "print project name"
                }),
               ('release',
                {'action': 'store_true',
                 'dest' : "release",
                 'help': "print project release"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Project, self).__init__(arguments=args, options=self.options, usage=__doc__)
