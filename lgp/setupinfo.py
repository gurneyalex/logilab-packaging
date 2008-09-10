# Copyright (c) 2003 Sylvain Thenault (thenault@gmail.com)
# Copyright (c) 2003-2006 Logilab (contact@logilab.fr)
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
""" generic package information container """

import os.path
import logging
from pprint import pprint
from subprocess import Popen, PIPE

from distutils.core import run_setup

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.common.shellutils import mv, cp, rm

from logilab.devtools.lgp.changelog import DebianChangeLog

logging.basicConfig(level=logging.DEBUG)

# FIXME Ugly class for rapid prototyping, sorry !!!

class SetupInfo(object):
    """ a setup class to handle several package setup information """
    _package_format = None

    def __init__(self, *args):
        if os.path.isfile('__pkginfo__.py'):
            self._package_format = 'pkginfo'
            self._package = PackageInfo(*args)
        elif os.path.isfile('setup.py'):
            self._package_format = 'setuptools'
            self._package = run_setup('./setup.py', None, stop_after="commandline")
        elif os.path.isfile('Makefile'):
            self._package_format = 'makefile'
        logging.debug("package format: %s" % self._package_format)

    def get_debian_name(self):
        if self._package_format == 'pkginfo':
            from __pkginfo__ import distname
            return distname
        else:
            return self._package.get_name()

    def get_debian_version(self, debiandir='debian', origpath=None):
        # Debian version is the last numeric part of the package name
        # <sourcepackage>_<upstreamversion>-<debian_version>
        debian_version   = DebianChangeLog('%s/changelog' % debiandir).get_latest_revision()
        if debian_version.debian_version != '1' and origpath is None:
            raise ValueError('unable to build %s %s: --orig option is required when '\
                             'not building the first version of the debian package'
                             % (self.get_debian_name(), self.get_debian_version()))
        return debian_version


    def get_upstream_name(self):
        if self._package_format == 'pkginfo':
            # by default, we use a tarball namle following the debian name
            # see http://ftp.logilab.org/pub/devtools/
            return self.get_debian_name()
        else:
            return self._package.get_name()

    def get_version(self):
        if self._package_format == 'pkginfo':
            return self._package.version
        elif self._package_format == 'makefile':
            p1 = Popen(["make", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^VERSION"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        else:
            return self._package.get_version()

    def get_packages(self):
        pipe = os.popen('dh_listpackages')
        packages = ['%s_%s_*.deb' % (line.strip(), self.get_debian_version()) for line in pipe.readlines()]
        pipe.close()
        #packages.append('%s_%s.orig.tar.gz' % (debian_name, upstream_version))
        packages.append('%s_%s.diff.gz' % (self.get_debian_name(), self.get_debian_version()))
        packages.append('%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version()))
        packages.append('%s_%s_*.changes' % (self.get_debian_name(), self.get_debian_version()))
        return packages

    def create_orig_tarball(self, tmpdir, dist_dir,
                            upstream_version,
                            debian_name,
                            upstream_tarball, pkg_dir, quiet=False):
        """ Create an origin tarball by the way of setuptools utility
        """
        tarball = os.path.join(tmpdir, '%s_%s.orig.tar.gz' % (debian_name, upstream_version))
        if not upstream_tarball:
            os.chdir(pkg_dir)

            if self._package_format == 'pkginfo':
                cmd = 'python setup.py sdist --force-manifest -d %s' % dist_dir
            elif self._package_format == 'setuptools':
                cmd = 'python setup.py sdist -d %s' % dist_dir
            elif self._package_format == 'makefile':
                cmd = 'make dist-gzip'
                # FIXME
                # Move tarball to dist_dir

            if not quiet:
                cmd += ' 1>/dev/null 2>/dev/null'
            os.system(cmd)

            upstream_tarball = os.path.join(dist_dir, '%s-%s.tar.gz' % (debian_name, upstream_version))
        else:
            # TODO check the upstream version with the new tarball 
            logging.debug("Use '%s' as tarball" % upstream_tarball)

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

