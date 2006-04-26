# Copyright (c) 2003-2004 LOGILAB S.A. (Paris, FRANCE).
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
"""USAGE: buildeb [destdir]

Build a debian package for a python or zope package and put result in <destdir>.
If omitted, result will be in the current directory

Should be launched from the root of the upstream package, containing
the debian directory.

The package should be conform to the standard source tree specification.
"""

__revision__ = '$Id: buildeb.py,v 1.17 2005-07-26 09:41:12 syt Exp $'

import os
import sys
import commands
import stat
from os.path import abspath, exists

from logilab.common.shellutils import mv, cp, rm
from logilab.common.fileutils import ensure_mode

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.debhdlrs import get_package_handler

BUILD_COMMAND = 'fakeroot make -f debian/rules binary'

def get_debian_version():
    """return the current debian version for a package
    (i.e. last debian changelog entry)
    """
    return commands.getoutput(
        "(dpkg-parsechangelog | sed -n 's/^Version: \(.*:\|\)//p') 2>/dev/null")
    
def build_debian(dest_dir='.', pkg_dir='.', command=None, system=os.system):
    """build debian package and move them is <dest_dir>
    
    the debian package to build is expected to be in the current working
    directory
    """
    orig_dir = os.getcwd()
    os.chdir(pkg_dir)
    dest_dir = abspath(dest_dir)
    if not exists('debian'):
        raise Exception('No "debian" directory')
    # ensure the "rules" file is executable
    ensure_mode('debian/rules', stat.S_IEXEC)
    # retreive package information
    pkginfo = PackageInfo()
    pkghandler = get_package_handler(pkginfo)
    upstream_name = pkginfo.name
    upstream_version = pkginfo.version
    debian_name = pkginfo.debian_name
    debian_version = get_debian_version()
    #
    pipe = os.popen('dh_listpackages')
    packages = ['%s_%s_*.deb' % (f.strip(), debian_version) for f in pipe.readlines()]
    packages.append('%s_%s.orig.tar.gz' % (debian_name, upstream_version))
    packages.append('%s_%s.diff.gz' % (debian_name, debian_version))
    packages.append('%s_%s.dsc' % (debian_name, debian_version))
    packages.append('%s_%s_*.changes' % (debian_name, debian_version))
    pipe.close()
    # initialise the build directory
    build_dir = pkghandler.prepare_debian(1)
    # build debian packages
    os.chdir(build_dir)
    debuilder = command or os.environ.get('DEBUILDER') or BUILD_COMMAND
    status = system(debuilder)
    # remove the build directory
    os.chdir(orig_dir)
    rm(build_dir)
    # check builder status
    if status:
        raise Exception('An error occured while building the debian package '
                        '(return status: %s)' % status)
    # move all builded files in a common directory
    # the place of those files depends of the command used to build the package
    if debuilder.startswith('pdebuild'):
        rm('../%s_%s.diff.gz' % (debian_name, debian_version))
        rm('../%s_%s.dsc' % (debian_name, debian_version))
        rm('../%s_%s*.changes' % (debian_name, debian_version))
        if not debuilder.startswith('pdebuild --buildresult'):
            for package in packages:
                cp('/var/cache/pbuilder/result/%s' % package, dest_dir)
        cp('%s/%s_%s.orig.tar.gz' % (dest_dir, debian_name, upstream_version),
           '%s/%s-%s.tar.gz' % (dest_dir, upstream_name, upstream_version))
    else: # fakeroot
        mv('../*%s*%s*.deb' % (debian_name, debian_version), dest_dir)
        mv('../%s_%s.orig.tar.gz' % (debian_name, upstream_version), dest_dir)
        mv('../%s-%s.tar.gz' % (upstream_name, upstream_version), dest_dir)


def run(args):
    """main"""
    if '-h' in args or '--help' in args:
        print __doc__
        return 0
    try:
        build_debian(*args)
        return 0
    except TypeError:
        import traceback
        traceback.print_exc()
        print __doc__
        return 1
    
if __name__ == '__main__':
    run(sys.argv[1:])
