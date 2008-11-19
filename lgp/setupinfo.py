# Copyright (c) 2008 Logilab (contact@logilab.fr)
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
""" generic package information container

    FIXME Ugly class for rapid prototyping, sorry !!!
"""

import sys
import os.path
import os
import glob
import logging
import commands
from subprocess import Popen, PIPE
from distutils.core import run_setup

from logilab.common.configuration import Configuration
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lgp.exceptions import LGPException

COMMANDS = {
        "sdist" : {
            "pkginfo": 'python setup.py sdist --force-manifest -d %s',
            "setuptools": 'python setup.py sdist -d %s',
            "makefile": 'make -f setup.mk dist-gzip -e DIST_DIR=%s',
        },
        "clean" : {
            "pkginfo": 'fakeroot debian/rules clean',
            "setuptools": 'fakeroot debian/rules clean',
            "makefile": 'make -f setup.mk clean',
        },
}

class SetupInfo(Configuration):
    """ a setup class to handle several package setup information """
    _package_format = None

    def __init__(self, arguments, options=None, **args):
        self.options = (
               ('verbose',
                {'action': 'store_true',
                 'default': False,
                 'short': 'v',
                 'dest' : "verbose",
                 'help': "run silently without confirmation"
                }),
               ('pkg_dir',
                {'type': 'string',
                 #'default' : os.getcwd(),
                 'dest': "pkg_dir",
                 'short': 'p',
                 'metavar' : "<project directory>",
                 'help': "set a specific project directory"
                }),
               ('revision',
                {'type': 'string',
                 'default' : None,
                 'dest': "revision",
                 'short': 'r',
                 'metavar' : "<scm revision>",
                 'help': "set a specific revision or tag to build the debian package"
                }),
               )
        if options:
            for opt in options:
                self.options += opt
        super(SetupInfo, self).__init__(options=self.options, **args)

        # Instanciate the default logger configuration
        logging.basicConfig(level=logging.INFO, filename="/dev/null")
        console = logging.StreamHandler()
        console.setFormatter(ColorFormatter('%(levelname)1.1s:%(name)s: %(message)s'))
        logging.getLogger().addHandler(console)
        self.logger = logging.getLogger()

        # TODO
        #self.load_file_configuration('etc/lgp/rc')

        # Manage arguments (project path essentialy)
        self.arguments = self.load_command_line_configuration(arguments)

        # Go to package directory
        if self.config.pkg_dir is None:
            self.config.pkg_dir = os.path.abspath(self.arguments and self.arguments[0] or os.getcwd())
        os.chdir(self.config.pkg_dir)

        # Load the optional config file 
        self.load_file_configuration('setup.cfg')

        if os.path.isfile('setup.mk'):
            self._package_format = 'makefile'
        elif os.path.isfile('__pkginfo__.py'):
            self._package_format = 'pkginfo'
            self._package = PackageInfo(directory=self.config.pkg_dir)
        elif os.path.isfile('setup.py'):
            self._package_format = 'setuptools'
            self._package = run_setup('./setup.py', None, stop_after="init")
        else:
            raise Exception('no valid setup file (setup.py or setup.mk)')
        if self.config.verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
        self.logger.debug("package format: %s" % self._package_format)

    def get_debian_name(self):
        """ obtain the debian package name

        The information is found in debian/control withe the 'Source:' field
        """
        for line in open('%s/%s/control' % (self.config.pkg_dir,
                                            self.get_debian_dir())):
            line = line.split(' ', 1)
            if line[0] == "Source:":
                return line[1].rstrip()

    def get_debian_dir(self):
        """ get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian/' is for unstable distribution
        - 'debian.$OTHER/' id for $OTHER distribution and if it exists
        """
        if self.config.distrib != 'unstable':
            debiandir = 'debian.%s/' % self.config.distrib
            if os.path.isdir(os.path.join(self.config.pkg_dir, debiandir)):
                return debiandir
        return 'debian/'

    def get_debian_version(self):
        """ get the debian version depending of the last changelog entry

            Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        cwd = os.getcwd()
        os.chdir(self.config.pkg_dir)
        try:
            status, output = commands.getstatusoutput('dpkg-parsechangelog')
            if status != 0:
                msg = 'dpkg-parsechangelog exited with status %s' % status
                raise LGPException(msg)
            for line in output.split('\n'):
                line = line.strip()
                if line and line.startswith('Version:'):
                    return line.split(' ', 1)[1].strip()
            raise LGPException('Debian version not found')
        finally:
            os.chdir(cwd)

    def get_upstream_name(self):
        if self._package_format == 'makefile':
            p1 = Popen(["make", "-f", "setup.mk", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^NAME"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        elif hasattr(self._package, 'get_name'):
            return self._package.get_name()
        elif self._package_format == 'pkginfo':
            try:
                from __pkginfo__ import distname
            except ImportError:
                from __pkginfo__ import modname
                distname = modname
            return distname

    def get_upstream_version(self):
        if self._package_format == 'pkginfo':
            from __pkginfo__ import version
            return version
        elif self._package_format == 'makefile':
            p1 = Popen(["make", "-f", "setup.mk", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^VERSION"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        else:
            return self._package.get_version()

    def get_changes_file(self):
        changes = '%s_%s_*.changes' % (self.get_debian_name(), self.get_debian_version())
        changes = glob.glob(os.path.join(self.get_distrib_dir(), changes))
        return changes[0]

    def get_packages(self):
        # FIXME
        # Move the Detect native package code here in order to list packages
        # cleanly
        os.chdir(self.config.pkg_dir)
        pipe = os.popen('dh_listpackages')
        packages = ['%s_%s_*.deb' % (line.strip(), self.get_debian_version()) for line in pipe.readlines()]
        pipe.close()
        #packages.append('%s_%s.orig.tar.gz' % (debian_name, upstream_version))
        #packages.append('%s_%s.diff.gz' % (self.get_debian_name(), self.get_debian_version()))
        #packages.append('%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version()))
        packages.append('%s_%s_*.changes' % (self.get_debian_name(), self.get_debian_version()))
        return packages

    def clean_repository(self):
        if self._package_format in COMMANDS["clean"]:
            cmd = COMMANDS["clean"][self._package_format]
            if not self.config.verbose:
                cmd += ' 1>/dev/null 2>/dev/null'
            self.logger.debug("Cleaning repository...")
            os.system(cmd)
        else:
            self.logger.error("no way to clean the repository...")

    def create_orig_tarball(self, tmpdir):
        """ Create an origin tarball 
        """
        tarball = os.path.join(tmpdir, '%s_%s.orig.tar.gz' %
                    (self.get_upstream_name(), self.get_upstream_version()))
        if self.config.orig_tarball is None:
            debian_version = self.get_debian_version()
            if debian_version[-2:] != '-1':
                raise LGPException('unable to build %s %s: --orig-tarball option is required when '\
                                   'not building the first version of the debian package.\n' \
                                   'If you haven\'t the original tarball version, ' \
                                   'please do an apt-get source of the source package.'
                                    % (self.get_debian_name(), debian_version))
            if self._package_format in COMMANDS["sdist"]:
                cmd = COMMANDS["sdist"][self._package_format] % self.config.dist_dir
            else:
                raise LGPException("no way to create the source distribution")

            if not self.config.verbose:
                cmd += ' 1>/dev/null 2>/dev/null'
            os.system(cmd)

            upstream_tarball = os.path.join(self.config.dist_dir, '%s-%s.tar.gz' %
                (self.get_upstream_name(), self.get_upstream_version()))
            self.logger.debug("Build new source archive '%s'" % upstream_tarball)
        else:
            upstream_tarball = self.config.orig_tarball

        # TODO check the upstream version with the new tarball 
        if not os.path.isfile(upstream_tarball):
            raise LGPException("source distribution wasn't properly built")
        self.logger.info("Use '%s' as original source archive (tarball)" % upstream_tarball)
        self.logger.debug("Copy '%s' to '%s'" % (upstream_tarball, tarball))
        cp(upstream_tarball, tarball)

        return tarball
