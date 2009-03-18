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
""" lgp clean [options]

    Clean project's directory
"""
__docformat__ = "restructuredtext en"

import logging

from logilab.devtools.lgp.build import Builder
from logilab.devtools.lgp.exceptions import LGPException


def run(args):
    """ Main function of lgp clean command """
    try :
        cleaner = Builder(args)
        cleaner.clean_repository()
    except LGPException, exc:
        logging.critical(exc)
        #if hasattr(cleaner, "config") and cleaner.config.verbose:
        #    logging.debug("printing traceback...")
        #    raise
        return 1
