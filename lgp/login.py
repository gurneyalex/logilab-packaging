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
""" lgp login [options]

    Log into a chrooted distribution
"""
__docformat__ = "restructuredtext en"

import logging
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp import CONFIG_FILE, HOOKS_DIR


def run(args):
    """ Main function of lgp login command """
    try :
        login = Login(args)
        for arch in login.architectures:
            for distrib in login.distributions:
                logging.info("login into '%s' image" % distrib)
                cmd = "sudo DIST=%s ARCH=%s pbuilder login --configfile %s --hookdir %s"
                # run login command
                try:
                    cmd = cmd % (distrib, arch, CONFIG_FILE, HOOKS_DIR)
                    check_call(cmd.split(), env={'DIST': distrib, 'ARCH': arch})
                except CalledProcessError, err:
                    raise LGPCommandException('an error occured in login process', err)

    except NotImplementedError, exc:
        logging.error(exc)
        return 1
    except LGPException, exc:
        logging.critical(exc)
        return 1


class Login(SetupInfo):
    """Login checker class

    Specific options are added. See lgp login --help
    """
    name = "lgp-login"
    def __init__(self, args):
        # Retrieve upstream information
        super(Login, self).__init__(arguments=args, options=self.options, usage=__doc__)
