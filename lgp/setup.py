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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
from __future__ import print_function

import os
import sys
import glob
from subprocess import check_call, CalledProcessError

from logilab.devtools.lgp import (LGP, CONFIG_FILE, HOOKS_DIR, utils)
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.check import check_keyrings


@LGP.register
class Setup(SetupInfo):
    """Set up and manage build images.

    Available commands:
        - list:        list actual images        (default)
        - create:      create new image
        - update:      update image
        - clean:       clean pbuilder caches
        - dumpconfig:  display pbuilder settings

    Note: chrooted images will be used to isolate builds (pbuilder)
    """
    name = "setup"
    options = SetupInfo.options + [
               ('command',
                {'type': 'choice',
                 'choices': ('list', 'create', 'update', 'dumpconfig', 'clean'),
                 'dest': 'command',
                 'default' : 'list',
                 'short': 'c',
                 'metavar': "<command>",
                 'help': "command to run with pbuilder"
                }),
              ]
    arguments = "-c <command> -d <distrib> -a <arch>"
    max_args = 0
    cmd = "IMAGE=%s DIST=%s ARCH=%s %s %s %s --configfile %s --hookdir %s"

    @property
    def pbuilder_cmd(self):
        return "/usr/sbin/pbuilder %s" % self.config.command

    @property
    def setarch_cmd(self):
        setarch_cmd = ""
        # workaround: http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#amd64i386
        # FIXME use `setarch` command for much more supported platforms
        if 'amd64' in self.get_architectures(['current']) and self.arch == 'i386' and os.path.exists('/usr/bin/linux32'):
            self.logger.debug('using linux32 command to build i386 image from amd64 compatible architecture')
            setarch_cmd = 'linux32'
        return setarch_cmd

    @property
    def sudo_cmd(self):
        sudo_cmd = ""
        if os.geteuid() != 0:
            self.logger.debug('lgp setup should be run as root. sudo is used internally.')
            sudo_cmd = "/usr/bin/sudo -E"
        return sudo_cmd

    def go_into_package_dir(self, arguments):
        pass

    def _set_package_format(self):
        pass

    def _prune_pkg_dir(self):
        pass

    def guess_environment(self):
        # no default value for distribution but don't try to retrieve it
        if self.config.distrib is None:
            self.config.distrib = []
        # retrieve distribution known by debootstrap
        creation = self.config.command == "create"
        self.distributions = utils.get_distributions(self.config.distrib,
                                                     self.config.basetgz,
                                                     creation=creation)
        self.logger.debug("guessing debootstrap distributions: %s"
                          % ', '.join(self.distributions))

    def print_images_list(self):
        self.logger.info("Base image directory: %s", self.config.basetgz)
        images = sorted(os.path.basename(f) for f in
                        glob.glob(os.path.join(self.config.basetgz,'*.tgz')))
        if images:
            print(*images, file=sys.__stdout__)
        else:
            self.logger.warn("No image found.")

    def run(self, args):
        if self.config.command == "list":
            self.print_images_list()
            return os.EX_OK
        if self.config.command == "create":
            check_keyrings(self)
        if self.config.command in ("create", "update"):
            self.cmd += " --override-config"
        elif self.config.command == "clean":
            self.logger.debug("cleans up directory specified by configuration BUILDPLACE and APTCACHE")
        elif self.config.command == "dumpconfig":
            sys.stdout = sys.__stdout__

        for arch in self.get_architectures():
            for distrib in self.distributions:
                self.arch = arch # see setarch_cmd()

                image = self.get_basetgz(distrib, arch, check=False)

                # don't manage symbolic file in create and update command
                if os.path.islink(image) and self.config.command in ("create", "update"):
                    self.logger.warning("skip symbolic link used for image: %s (-> %s)"
                                        % (image, os.path.realpath(image)))
                    continue

                cmd = self.cmd % (image, distrib, arch, self.setarch_cmd, self.sudo_cmd,
                                  self.pbuilder_cmd, CONFIG_FILE, HOOKS_DIR)

                self.logger.info(self.config.command + " image '%s' for '%s/%s'"
                                 % (image, distrib, arch))
                self.logger.debug("run command: %s" % cmd)
                try:
                    check_call(cmd, stdout=sys.stdout, shell=True,
                               env={'DIST': distrib, 'ARCH': arch, 'IMAGE': image})
                except CalledProcessError, err:
                    # Gotcha: pbuilder dumpconfig command always returns exit code 1.
                    # Catch and continue for this command without error
                    if self.config.command != "dumpconfig":
                        self.logger.error('an error occured in setup process: %s' % cmd)

