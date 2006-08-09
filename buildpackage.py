# -*- encoding: iso-8859-15 -*-
# Copyright (c) 2003-2006 LOGILAB S.A. (Paris, FRANCE).
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

"""provides functions to uild a debian package for a python package
"""

import os
import stat
import tempfile
import shutil
from os.path import abspath, isdir, expanduser, isfile, join

from logilab.common.shellutils import mv, cp, rm
from logilab.common.fileutils import ensure_mode, export

from logilab.devtools.lib.utils import confirm, cond_exec
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib.changelog import DebianChangeLog

SEPARATOR = '+' * 72


def get_packages_list(info):
    (upstream_name, upstream_version, debian_name, debian_version) = info
    pipe = os.popen('dh_listpackages')
    packages = ['%s_%s_*.deb' % (line.strip(), debian_version) for line in pipe.readlines()]
    pipe.close()
    #packages.append('%s_%s.orig.tar.gz' % (debian_name, upstream_version))
    packages.append('%s_%s.diff.gz' % (debian_name, debian_version))
    packages.append('%s_%s.dsc' % (debian_name, debian_version))
    packages.append('%s_%s_*.changes' % (debian_name, debian_version))
    return packages

def move_result(dest_dir, info, debuilder):
    if not isdir(dest_dir):
        os.mkdir(dest_dir)
    packages = get_packages_list(info)
    binary_packages = [pkg for pkg in packages if pkg.endswith('.deb')]
    (upstream_name, upstream_version, debian_name, debian_version) = info
    if debuilder.startswith('pdebuild'):
        rm('../%s_%s.diff.gz' % (debian_name, debian_version))
        rm('../%s_%s.dsc' % (debian_name, debian_version))
        rm('../%s_%s*.changes' % (debian_name, debian_version))

        source_dist = '%s_%s.tar.gz' % (upstream_name, debian_version)
        if isfile('../%s' % source_dist):
            rm('../%s' % source_dist)

        if not debuilder.startswith('pdebuild --buildresult'):
            for package in packages:
                cp('/var/cache/pbuilder/result/%s' % package, dest_dir)
            #cp('/var/cache/pbuilder/result/%s' % source_dist, dest_dir)

        #cp('%s/%s_%s.orig.tar.gz' % (dest_dir, debian_name, upstream_version),
        #   '%s/%s-%s.tar.gz' % (dest_dir, upstream_name, upstream_version))

    else: # fakeroot
        for package in binary_packages:
            mv('../%s*' % package, dest_dir)
        #mv('../%s_%s.orig.tar.gz' % (debian_name, upstream_version), dest_dir)
        #mv('../%s-%s.tar.gz' % (upstream_name, upstream_version), dest_dir)
            

def build_debian(pkg_dir, dest_dir, pdebuild_options='', origpath=None):
    """build debian package and move them in <dest_dir>
    
    the debian package to build is expected to be in the current working
    directory
    """ 
    # 0/ retrieve package information
    os.chdir(pkg_dir)
    pkginfo = PackageInfo()
    upstream_name = pkginfo.name
    upstream_version = pkginfo.version
    debian_name = pkginfo.debian_name
    debian_version = DebianChangeLog('debian/changelog').get_latest_revision()
    info = (upstream_name, upstream_version, debian_name, debian_version)

    ## 1/ ensure project directory has debian/ and debian/rules
    os.chdir(pkg_dir)
    if not isdir('debian'):
        print 'No "debian" directory'
        return 1
    ensure_mode('debian/rules', stat.S_IEXEC)

    ## 2/ copy project directory to workdir named projectname-version/
    tmpdir = tempfile.mkdtemp()
    workdir = join(tmpdir, '%s-%s'% (debian_name, upstream_version))
    try:
        try:
            export(pkg_dir, workdir)
            export('debian', '%s/debian' % workdir)

            ## 3/ if needed create archive projectname-version.orig.tar.gz
            if origpath:
                cp(origpath, tmpdir)
            else:
                origpath = join(tmpdir, '%s_%s.orig.tar.gz' % (debian_name, upstream_version))
                os.system('cd %s && tar czf %s %s' % (tmpdir, origpath, '%s-%s'% (debian_name, upstream_version)))
                
            ## 4/ make
            os.chdir(workdir)
            debuilder = os.environ.get('DEBUILDER') or 'pdebuild'
            status = os.system('%s %s' % (debuilder, pdebuild_options))
            if status:
                print 'An error occured while building the debian package ' \
                          '(return status: %s)' % status
                return 1

            # move result
            if not isdir(dest_dir):
                os.mkdir(dest_dir)
            cp(origpath, dest_dir)
            if move_result(dest_dir, info, debuilder):
                return 1
            return 0
        except Exception, exc:
            print "An exception occured while moving files (%s)" % exc
            return 1
    finally:
        os.chdir(pkg_dir)
        # print "please visit", tmpdir
        shutil.rmtree(tmpdir)


def add_options(parser):
    parser.usage = 'lgp build [options] <args>'
    parser.add_option('--debbuildopts', default='', help='options passed to pdebuild')
    parser.add_option('--dist', dest='distdir', default=expanduser('~/dist'),
                      help='where to put results')
    parser.add_option('--orig', help='path to orig.tar.gz file')


def run(pkgdir, options, args):
    """main"""
    if build_debian(pkgdir, options.distdir, options.debbuildopts,
                    options.orig):
        return 1
    # lintian
    print SEPARATOR
    if confirm("lancement de lintian sur les paquets générés ?"):
        cond_exec('lintian -i %s/*.deb' % options.distdir)

    # linda
    print SEPARATOR
    if confirm("lancement de linda sur les paquets générés ?"):
        cond_exec('linda -i %s/*.deb' % options.distdir)

    # piuparts
    print SEPARATOR
    if confirm("lancement de piuparts sur les paquets générés ?"):
        cond_exec('sudo piuparts -p %s/*.deb' % options.distdir)
