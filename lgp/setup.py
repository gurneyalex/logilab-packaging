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
from logilab.devtools.lgp.utils import get_distributions, get_architectures
from logilab.devtools.lgp.utils import cond_exec, confirm
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp import CONFIG_FILE


def run(args):
    """ Main function of lgp setup command """

    try :
        setup = Setup(args)

        if setup.config.command == "create":
            if not os.path.isfile(CONFIG_FILE):
                print("* You need to install the %s file to begin" % CONFIG_FILE)
                sys.exit(1)
            if not confirm('* Have you already set your pbuilder variables in %s ?' %
                           CONFIG_FILE):
                print '  Please configure to continue.'
                sys.exit(0)

            while not os.path.isfile('/usr/share/keyrings/debian-archive-keyring.gpg'):
                if not confirm("* Have you installed the debian-archive-keyring package ?"):
                    print '  Please install it to continue.'
                    sys.exit(0)

            while not os.path.isfile('/usr/share/keyrings/ubuntu-archive-keyring.gpg'):
                print("* You need to install this keyring file if you want to build for ubuntu distributions.\n\n"
                      "  You can download it from http://fr.archive.ubuntu.com/ubuntu/pool/main/u/ubuntu-keyring\n"
                      "  or: wget -O /usr/share/keyrings/ubuntu-archive-keyring.gpg \\\n"
                      "      ftp://ftp.archive.ubuntu.com/ubuntu/project/ubuntu-archive-keyring.gpg")
                if confirm("  Skip the ubuntu keyring installation ?"):
                    break

            distributions = setup.choice_distribution("* You have to select pbuilder images to create:")
            print("* Creating images now... It will take a while.")
            for distrib in distributions:
                cmd = "sudo DIST=%s pbuilder create --override-config --configfile %s"\
                      % (distrib, CONFIG_FILE)
                try:
                    check_call(cmd.split(), env={'DIST': distrib})
                except CalledProcessError, err:
                    raise LGPCommandException('impossible to create the pbuilder image', err)

        if setup.config.command == "update":
            distributions = setup.choice_distribution("* You have to select pbuilder images to update:")
            print("* Updating images now... It will take a while.")
            for distrib in distributions:
                cmd = "sudo DIST=%s pbuilder update --override-config --configfile %s"\
                      % (distrib, CONFIG_FILE)
                try:
                    check_call(cmd.split(), env={'DIST': distrib})
                except CalledProcessError, err:
                    raise LGPCommandException('impossible to update the pbuilder image', err)

        if setup.config.command == "login":
            if not setup.config.distrib or setup.config.distrib=='all':
                raise LGPException('you need to specify a valid distribution to log in')
            else:
                distribution = get_distributions(setup.config.distrib)[0]
            cmd = "sudo DIST=%s pbuilder login --configfile %s" \
                  % (distribution, CONFIG_FILE)
            try:
                check_call(cmd.split(), env={'DIST': distribution})
            except CalledProcessError, err:
                raise LGPCommandException('impossible to enter into pbuilder image', err)

        if setup.config.command == "dumpconfig":
            if not setup.config.distrib or setup.config.distrib=='all':
                raise LGPException('you need to specify a valid distribution to dump configuration values')
            else:
                distribution = get_distributions(setup.config.distrib)[0]
            cmd = "sudo DIST=%s pbuilder dumpconfig --configfile %s" \
                  % (distribution, CONFIG_FILE)
            try:
                check_call(cmd.split())
            except CalledProcessError, err:
                # FIXME command always returns exit code 1
                #raise LGPCommandException('impossible to dump configuration values', err)
                pass

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

    options = (('distrib',
                {'type': 'choice',
                 'choices': get_distributions(),
                 'dest': 'distrib',
                 'short': 'd',
                 'default': 'unstable',
                 'metavar': "<distribution>",
                 'help': "particular distribution to set up (by default create %s)"
                         % ",".join(get_distributions())
                }),
               ('command',
                {'type': 'choice',
                 'choices': ('create', 'update', 'dumpconfig', 'login'), # 'clean', 'dumpconfig'),
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
        self.logger = logging.getLogger(__name__)

    def choice_distribution(self, str):
        if self.config.distrib:
            distributions = get_distributions(self.config.distrib)
        else:
            print("%s\n " % str),
            print(', '.join(get_distributions('target')))
            distributions = raw_input("\n  distributions (separated by space) ? ")
            distributions = [d for d in distributions.split() if d in get_distributions('known')]
            while not confirm("  \n  %s\n  Is this correct ?" % distributions):
                distributions = raw_input("\n  distributions (separated by space) ? ")
                distributions = [d for d in distributions.split() if d in get_distributions('known')]
        return distributions

