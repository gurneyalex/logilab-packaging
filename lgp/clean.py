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
import logging

from logilab.devtools.lgp import LGP
from logilab.devtools.lgp.setupinfo import SetupInfo


@LGP.register
class Cleaner(SetupInfo):
    """Clean the project directory.
    """
    name = "clean"

    def run(self, args):
        logging.info("clean the project repository")
        self.clean_repository()

    def clean_repository(self):
        """clean the project repository"""
        if os.environ.get('FAKEROOTKEY'):
            logging.info("fakeroot: nested operation not yet supported")
            return
        try:
            self._run_command('clean')
        except Exception, err:
            logging.warn(err)
