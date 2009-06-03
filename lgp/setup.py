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
from subprocess import Popen, PIPE
try:
    from subprocess import check_call, CalledProcessError # only python2.5
except ImportError:
    from logilab.common.compat import check_call, CalledProcessError

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import cond_exec, confirm
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp.check import check_keyrings
from logilab.devtools.lgp import CONFIG_FILE


def run(args):
    """ Main function of lgp setup command """
    try :
        setup = Setup(args)

        if setup.config.command == "create":
            if not check_keyrings(setup):
                logging.warn("you haven't installed archive keyring for ubuntu distributions")
                logging.warn("you can download it from http://fr.archive.ubuntu.com/ubuntu/pool/main/u/ubuntu-keyring")
                logging.warn("then copy keyring file into /usr/share/keyrings/ directory")
                logging.debug("wget -O /usr/share/keyrings/ubuntu-archive-keyring.gpg ftp://ftp.archive.ubuntu.com/ubuntu/project/ubuntu-archive-keyring.gpg")

        for arch in setup.architectures:
            for distrib in setup.distributions:
                if setup.config.command == "create":
                    logging.info("creating '%s' image now... It will take a while." % distrib)
                    cmd = "sudo DIST=%s ARCH=%s pbuilder create --override-config --configfile %s"
                elif setup.config.command == "update":
                    logging.info("updating '%s' image now... It will take a while." % distrib)
                    cmd = "sudo DIST=%s ARCH=%s pbuilder update --override-config --configfile %s"
                elif setup.config.command == "dumpconfig":
                    logging.info("dump '%s' image configuration" % distrib)
                    cmd = "sudo DIST=%s ARCH=%s pbuilder dumpconfig --configfile %s"

                # run setup command
                try:
                    if arch == 'i386' and os.path.exists('/usr/bin/linux32'):
                        cmd = 'linux32 ' + cmd
                    cmd = cmd % (distrib, arch, CONFIG_FILE)
                    check_call(cmd.split(), env={'DIST': distrib, 'ARCH': arch})
                except CalledProcessError, err:
                    # FIXME command always returns exit code 1
                    if setup.config.command == "dumpconfig":
                        continue
                    raise LGPCommandException('an error occured in setup process', err)

    except NotImplementedError, exc:
        logging.error(exc)
        return 1
    except LGPException, exc:
        logging.critical(exc)
        return 1


class Setup(SetupInfo):
    """ Environment setup checker class

    Specific options are added. See lgp setup --help
    """
    name = "lgp-setup"

    options = (('command',
                {'type': 'choice',
                 'choices': ('create', 'update', 'dumpconfig', 'login'), # 'clean', 
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
