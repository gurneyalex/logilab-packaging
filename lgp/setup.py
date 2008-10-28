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

    Prepare a chrooted distribution
"""
__docformat__ = "restructuredtext en"

import os
import logging
from subprocess import Popen, PIPE

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import get_distributions, get_architectures
from logilab.devtools.lgp.utils import cond_exec, confirm
from logilab.devtools.lgp.exceptions import LGPException


def run(args):
    """ Main function of lgp setup command """

    try :
        setup = Setup(args)
        distributions = get_distributions(setup.config.distrib)

        for distrib in distributions:
            print Popen(["sudo", "pbuilder", setup.config.command, "--distribution", distrib,
                         "--configfile", setup.config.configfile], stdout=PIPE).communicate()[0]
    except NotImplementedError, exc:
        logging.error(exc)
    except LGPException, exc:
        logging.critical(exc)
        if setup.config.verbose:
            raise
    except Exception, exc:
        logging.critical(exc)
    return 1

class Setup(SetupInfo):
    """ Environment setup checker class

    Specific options are added. See lgp setup --help
    """
    name = "lgp-setup"

    options = (('chroot',
                {'type': 'string',
                 'default' : '/opt/buildd',
                 'dest' : "chroot_dir",
                 'metavar': "<directory>",
                 'help': "where are the compressed images"
                }),
               ('metadistrib',
                {'type': 'choice',
                 'choices': ('debian', 'ubuntu'),
                 'dest': 'metadistrib',
                 'default' : 'debian',
                 'short': 'm',
                 'metavar': "<meta-distribution>",
                 'help': "the meta-distribution targetted (debian or ubuntu). Use 'all' for both"
                }),
               ('distrib',
                {'type': 'choice',
                 'choices': get_distributions() + ('all',),
                 'dest': 'distrib',
                 'default' : 'sid',
                 'short': 'd',
                 'metavar': "<distribution>",
                 'help': "the distribution targetted (e.g. stable, unstable, sid). Use 'all' for all known distributions"
                }),
               ('command',
                {'type': 'choice',
                 'choices': ('create', 'update', 'clean', 'dumpconfig'),
                 'dest': 'command',
                 'default' : 'dumpconfig',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "Front  end  program to the pbuilder utility"
                }),
               ('configfile',
                {'type': 'string',
                 'dest': 'configfile',
                 'short': 'f',
                 'metavar' : "<configfile>",
                 'help': "configuration file to read after pbuilder configuration files have been read"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Setup, self).__init__(arguments=args, options=self.options, usage=__doc__)
        self.logger = logging.getLogger(__name__)

        if self.config.metadistrib and self.config.configfile is None:
            self.config.configfile = "/etc/lgp/pbuilder/%s" % self.config.metadistrib
            self.logger.info("Use meta-distribution config file '%s'" % self.config.configfile)
