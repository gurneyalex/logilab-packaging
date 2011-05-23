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
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp import LGP, CONFIG_FILE, HOOKS_DIR
from logilab.devtools.lgp.setupinfo import SetupInfo


@LGP.register
class Login(SetupInfo):
    """Log into a build image.
    """
    name = "login"
    options = SetupInfo.options + [
               ('result',
                {'type': 'string',
                 'default' : '~/dists',
                 'dest' : "dist_dir",
                 'short': 'r',
                 'metavar': "<directory>",
                 'help': "mount compilation results directory"
               })
              ]
    cmd = ("IMAGE=%s DIST=%s ARCH=%s %s %s --configfile %s "
           "--hookdir %s --bindmounts %s --othermirror %s "
           "--override-config")
    pbuilder_cmd = "/usr/sbin/pbuilder %s" % name
    sudo_cmd = "/usr/bin/sudo -E"

    def go_into_package_dir(self, arguments):
        pass

    def _set_package_format(self):
        pass

    def _prune_pkg_dir(self):
        pass

    @property
    def other_mirror(self):
        dirname, basename = os.path.split(self.get_distrib_dir())
        return "'deb file://%s %s/'" % (dirname, basename)

    def guess_environment(self):
        # if no default value for distribution, try to retrieve it from changelog
        if self.config.distrib is None or 'changelog' in self.config.distrib:
            self.config.distrib = 'changelog'
        super(Login, self).guess_environment()

    def run(self, args):
        for arch in self.get_architectures():
            for distrib in self.distributions:
                image = self.get_basetgz(distrib, arch)

                cmd = self.cmd % (image, distrib, arch, self.sudo_cmd,
                                  self.pbuilder_cmd, CONFIG_FILE, HOOKS_DIR,
                                  self.get_distrib_dir(), self.other_mirror)

                logging.info("login into '%s/%s' image" % (distrib, arch))
                logging.debug("run command: %s", cmd)
                try:
                    check_call(cmd, shell=True,
                               env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image,
                                    'DISPLAY': os.environ.get('DISPLAY', ""),
                                    'OTHERMIRROR': self.other_mirror})
                except CalledProcessError, err:
                    logging.warn("returned non-zero exit status %s",
                                 err.returncode)

