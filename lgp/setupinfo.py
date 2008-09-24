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
import logging
from subprocess import Popen, PIPE
from distutils.core import run_setup

from logilab.common.configuration import Configuration
from logilab.common.shellutils import cp

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lgp.changelog import DebianChangeLog


COMMANDS = {
        "sdist" : {
            "pkginfo": 'python setup.py sdist --force-manifest -d %s',
            "setuptools": 'python setup.py sdist -d %s',
            "makefile": 'make dist-gzip',
        },
}

class SetupInfo(Configuration):
    """ a setup class to handle several package setup information """
    _package_format = None

    def __init__(self, arguments, options, **args):
        self.options = (
               ('verbose',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "verbose",
                 'help': "run silently without confirmation"
                }),
               ('pkg_dir',
                {'type': 'string',
                 #'default' : os.getcwd(),
                 'dest': "pkg_dir",
                 'metavar' : "<project directory>",
                 'help': "set a specific project directory"
                }),
               ('revision',
                {'type': 'string',
                 'default' : None,
                 'dest': "revision",
                 'metavar' : "<scm revision>",
                 'help': "set a specific revision or tag to build the debian package"
                }),
               )
        for opt in options:
            self.options += opt
        super(SetupInfo, self).__init__(options=self.options, **args)
        self.logger = logging.getLogger('lgp')

        arguments = self.load_command_line_configuration(arguments)

        # Go to package directory
        if self.config.pkg_dir is None:
            self.config.pkg_dir = os.path.abspath(arguments and arguments[0] or os.getcwd())
        os.chdir(self.config.pkg_dir)

        # Load the optional config file 
        self.load_file_configuration('setup.cfg')

        if os.path.isfile('__pkginfo__.py'):
            self._package_format = 'pkginfo'
            self._package = PackageInfo(None, self.config.pkg_dir)
        elif os.path.isfile('setup.py'):
            self._package_format = 'setuptools'
            self._package = run_setup('./setup.py', None, stop_after="init")
        elif os.path.isfile('Makefile'):
            self._package_format = 'makefile'
        else:
            raise Exception('no valid setup file')
        if self.config.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        logging.debug("package format: %s" % self._package_format)

    def get_debian_name(self):
        """ obtain the debian package name

        The information is found in debian/control withe the 'Source:' field
        """
        for line in open('%s/%s/control' % (self.config.pkg_dir,
                                            self.get_debian_dir())):
            line = line.split()
            if line[0] == "Source:":
                return line[1]

    def get_debian_dir(self):
        """ get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian/' is for sid distribution
        - 'debian.$OTHER' id for $OTHER distribution and if it exists
        """
        if self.config.distrib != 'sid':
            debiandir = 'debian.%s/' % self.config.distrib
            if os.path.isdir(debiandir):
                return debiandir
        return 'debian/'

    def get_debian_version(self):
        """ get the debian version depending of the last changelog entry

            Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        debian_version = DebianChangeLog('%s/%s/changelog' % 
                (self.config.pkg_dir, self.get_debian_dir())).get_latest_revision()
        if debian_version.debian_version != '1' and self.config.orig_tarball is None:
            raise ValueError('unable to build %s %s: --orig-tarball option is required when '\
                             'not building the first version of the debian package'
                             % (self.get_debian_name(), debian_version))
        return debian_version

    def get_upstream_name(self):
        if hasattr(self._package, 'get_name'):
            return self._package.get_name()
        elif self._package_format == 'pkginfo':
            try:
                from __pkginfo__ import distname
            except ImportError:
                from __pkginfo__ import name
                distname = name
            return distname

    def get_upstream_version(self):
        if self._package_format == 'pkginfo':
            from __pkginfo__ import version
            return version
        elif self._package_format == 'makefile':
            p1 = Popen(["make", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^VERSION"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        else:
            return self._package.get_version()

    def get_packages(self):
        os.chdir(self.config.pkg_dir)
        pipe = os.popen('dh_listpackages')
        packages = ['%s_%s_*.deb' % (line.strip(), self.get_debian_version()) for line in pipe.readlines()]
        pipe.close()
        #packages.append('%s_%s.orig.tar.gz' % (debian_name, upstream_version))
        packages.append('%s_%s.diff.gz' % (self.get_debian_name(), self.get_debian_version()))
        packages.append('%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version()))
        packages.append('%s_%s_*.changes' % (self.get_debian_name(), self.get_debian_version()))
        return packages

    def create_orig_tarball(self, tmpdir):
        """ Create an origin tarball 
        """
        tarball = os.path.join(tmpdir, '%s_%s.orig.tar.gz' %
                    (self.get_upstream_name(), self.get_upstream_version()))
        if self.config.orig_tarball is None:
            if self._package_format in COMMANDS["sdist"]:
                cmd = COMMANDS["sdist"][self._package_format] % self.config.dist_dir
            else:
                logging.critical("No way to create a source distribution")
                sys.exit(1)

            if not self.config.verbose:
                cmd += ' 1>/dev/null 2>/dev/null'
            os.system(cmd)

            upstream_tarball = os.path.join(self.config.dist_dir, '%s-%s.tar.gz' %
                (self.get_upstream_name(), self.get_upstream_version()))
        else:
            upstream_tarball = self.config.orig_tarball
            # TODO check the upstream version with the new tarball 
            logging.info("Use '%s' as source distribution" % upstream_tarball)

        logging.debug("Copy '%s' to '%s'" % (upstream_tarball, tarball))
        cp(upstream_tarball, tarball)

        return tarball

    #def move_result(self, dist_dir, info, debuilder):
    #    packages = get_packages_list(info)
    #    binary_packages = [pkg for pkg in packages if pkg.endswith('.deb')]
    #    (upstream_name, upstream_version, debian_name, debian_version) = info
    #    if debuilder.startswith('vbuild'):
    #        pass
    #    else: # fakeroot
    #        for package in binary_packages:
    #            mv('../%s*' % package, dist_dir)
    #        #mv('../%s_%s.orig.tar.gz' % (debian_name, upstream_version), dist_dir)
    #        #mv('../%s-%s.tar.gz' % (upstream_name, upstream_version), dist_dir)

