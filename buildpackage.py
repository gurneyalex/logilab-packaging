# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
""" Provides functions to build a debian package for a python package
"""
__docformat__ = "restructuredtext en"

import os
import sys
import stat
import tempfile
import shutil
import os.path as osp
from subprocess import Popen, PIPE

from logilab.common.shellutils import mv, cp, rm
from logilab.common.fileutils import ensure_fs_mode, export

from logilab.devtools.exceptions import (ArchitectureException,
                                         DistributionException)
from logilab.devtools.lib.utils import confirm, cond_exec
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib.changelog import DebianChangeLog

KNOWN_DISTRIBUTIONS = ['etch', 'lenny', 'sid']

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
    if not osp.isdir(dest_dir):
        os.mkdir(dest_dir)

    packages = get_packages_list(info)
    binary_packages = [pkg for pkg in packages if pkg.endswith('.deb')]
    (upstream_name, upstream_version, debian_name, debian_version) = info
    if debuilder.startswith('pdebuild'):
        rm('../%s_%s.diff.gz' % (debian_name, debian_version))
        rm('../%s_%s.dsc' % (debian_name, debian_version))
        rm('../%s_%s*.changes' % (debian_name, debian_version))

        # XXX : are we sure that's not "%s_%s.orig.tar.gz" ?
        source_dist = '%s_%s.tar.gz' % (upstream_name, debian_version)
        print "looking for %s in .." % source_dist
        if osp.isfile('../%s' % source_dist):
            rm('../%s' % source_dist)

        if not debuilder.startswith('pdebuild --buildresult'):
            for package in packages:
                cp('/var/cache/pbuilder/result/%s' % package, dest_dir)
            #cp('/var/cache/pbuilder/result/%s' % source_dist, dest_dir)

        #cp('%s/%s_%s.orig.tar.gz' % (dest_dir, debian_name, upstream_version),
        #   '%s/%s-%s.tar.gz' % (dest_dir, upstream_name, upstream_version))
    elif debuilder.startswith('vbuild'):
        pass
    else: # fakeroot
        for package in binary_packages:
            mv('../%s*' % package, dest_dir)
        #mv('../%s_%s.orig.tar.gz' % (debian_name, upstream_version), dest_dir)
        #mv('../%s-%s.tar.gz' % (upstream_name, upstream_version), dest_dir)

def create_dest_dir(dirname, distname):
    if not osp.isdir(dirname):
        os.mkdir(dirname)
    target = osp.join(dirname, distname)
    if not osp.isdir(target):
        os.mkdir(target)
    return target

def create_orig_tarball(origdir, tmpdir, dest_dir,
                        upstream_version,
                        debian_name,
                        origpath, pkg_dir, quiet=False):
    if not origpath:
        os.chdir(pkg_dir)
        cmd = 'python setup.py sdist --force-manifest'
        if quiet:
            cmd += ' 1>/dev/null 2>/dev/null'
        os.system(cmd)
        tarball = osp.join('dist', '%s.tar.gz' % origdir)
        origpath = osp.join(tmpdir, '%s_%s.orig.tar.gz' % (debian_name, upstream_version))
        cp(tarball, dest_dir)
        cp(tarball, origpath)
    else:
        cp(origpath, tmpdir)
        origpath = osp.join(tmpdir, osp.split(origpath)[1])
    return origpath

def get_distributions(distrib='all'):
    """ Ensure that the target distributions exist

        :param:
            distrib: str or list
                name of a distribution
        :return:
            list of target distribution
    """
    if distrib == 'all':
        distrib = KNOWN_DISTRIBUTIONS
    else:
        if type(distrib) is str:
            distrib = distrib.split(',')
        for t in distrib:
            if t not in KNOWN_DISTRIBUTIONS:
                raise DistributionException(t)
    return distrib

def get_architectures(archi="current"):
    """ Ensure that the architectures exist

        :param:
            archi: str or list
                name of a architecture
        :return:
            list of architecture
    """
    known_archi = Popen(["dpkg-architecture", "-L"], stdout=PIPE).communicate()[0].split()
    if archi == "current":
        archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
    else:
        if archi == "all":
            return archi
        if type(archi) is str:
            archi = archi.split(',')
        for a in archi:
            if a not in known_archi:
                raise ArchitectureException(a)
    return archi

def make_source_package(origpath):
    """create a debian source package

    This function must be called inside an unpacked source
    package. The source package (dsc and diff.gz files) is created in
    the parent directory.
    
    :param:
        origpath: path to orig.tar.gz tarball
    """
    print "creation of the Debian source package"
    wd = os.getcwd()
    os.chdir('..')
    os.system('dpkg-source -b %s' % wd)
    os.chdir(wd)
        

def build_debian(pkg_dir, dest_dir,
                 target_distribution,
                 architecture,
                 pdebuild_options='',
                 origpath=None, quiet=False):
    """ Build debian package and move them in <dest_dir>

    The debian package to build is expected to be in the current working
    directory

    Several checks are performed here to validate the debian directory structure

    :todo: drop the quiet parameter (used by apycot at the moment)

    :param:
        pkg_dir
            package directory
        dest_dir
            destination directory
        target_distribution: str
            name of the targe debian distribution
        architecture: str
            name of the compilation architecture
        pdebuild_options
            options for the builder
        origpath
            upstream source URI
        quiet
            silent output (needed 

    :return:
        list of compiled packages or False
    """
    (pkg_dir, dest_dir, origpath) = [dir and osp.abspath(dir) for dir
                                     in (pkg_dir, dest_dir, origpath)]

    #sys.__stdout__.write("build_debian(%s, %s, %s, %s)\n" % (pkg_dir, dest_dir, pdebuild_options, origpath))
    # 0/ retrieve package information
    os.chdir(pkg_dir)
    pkginfo = PackageInfo()
    upstream_name = pkginfo.name
    upstream_version = pkginfo.version
    debian_name = pkginfo.debian_name
    debian_version = DebianChangeLog('debian/changelog').get_latest_revision()

    if debian_version.debian_version != '1' and origpath is None:
        raise ValueError('unable to build %s %s: --orig option is required when'\
        ' not building the first version of the debian package'%( debian_name,
            debian_version, ))
    
    info = (upstream_name, upstream_version, debian_name, debian_version)
    tmpdir = tempfile.mkdtemp()
    ##  workdir = osp.join(tmpdir, '%s-%s'% (debian_name, upstream_version))
    
    # 1/ ensure project directory has debian/ directory
    if not osp.isdir('debian'):
        raise ValueError('No "debian" directory')
    
    # 2/ check destination directory exists, create it if necessary, 
    dest_dir = create_dest_dir(dest_dir, target_distribution)
    # 2bis ensure debian/rules exists and is executable
    ensure_fs_mode('debian/rules', stat.S_IEXEC)

    try:
        origdir = '%s-%s' % (upstream_name, upstream_version)
        # 3/ if needed create archive projectname-version.orig.tar.gz using setup.py sdist
        origpath = create_orig_tarball(origdir, tmpdir, dest_dir,
                                       upstream_version,
                                       debian_name,
                                       origpath, pkg_dir, quiet)
        
        
        # 4/ create build directory by extracting the .orig.tar.gz and then
        #    copying debian/ directory
        os.chdir(tmpdir)
        status = os.system('tar xzf %s' % origpath)
        if status:
            raise IOError('An error occured while extracting the upstream'\
            ' tarball (return status: %s)' % status)
        # XXX : manage debian-distname 
        export(osp.join(pkg_dir, 'debian'), '%s/debian' % origdir)
        
        # 5/ build the package using fakeroot or pbuilder usually
        os.chdir(origdir)
        debuilder = os.environ.get('DEBUILDER') or 'vbuild'
        if debuilder == 'pdebuild' and pdebuild_options:
            cmd = '%s --debbuildopts %s' % (debuilder, pdebuild_options)
        elif debuilder ==  'vbuild':
            make_source_package(origpath)
            os.chdir('..')
            dscfile = '%s_%s.dsc' % (debian_name, debian_version)
            print "Building debian for distribution %s and arch %s" % (target_distribution,
                                                                       architecture)
            cmd = 'vbuild -d %s -a %s --result %s %s'
            cmd %= (target_distribution, architecture, dest_dir, dscfile,)
        else:
            cmd= debuilder
        if quiet:
            cmd += ' 1>/dev/null 2>/dev/null'
        print os.getcwd()
        print os.listdir('.')
        print cmd
        status = os.system(cmd)
        if status:
            raise OSError('An error occured while building the debian package ' \
                          '(return status: %s)' % status)

        try:
            # 6/ move the upstream tarball and debian package files to the destination directory
            mv(origpath, dest_dir)
            if move_result(dest_dir, info, debuilder):
                return False
            return get_packages_list(info)
        except Exception, exc:
            raise IOError("An exception occured while moving files (%s)" % exc)
    finally:
        os.chdir(pkg_dir)
        # print "please visit", tmpdir
        shutil.rmtree(tmpdir)


def add_options(parser):
    parser.usage = 'lgp build [options] <args>'
    parser.add_option('--debbuildopts', default='',
                      help="options passed to pdebuild's --debbuildopts option")
    parser.add_option('--dist', dest='distdir', default=osp.expanduser('~/dist'),
                      help='where to put results')
    parser.add_option('-t', '--target-distribution', default='sid',
                      help='the distribution targetted (e.g. etch, lenny, sid). Use all for all known distributions')
    parser.add_option('-a', '--arch', default='all', help='build for the requested debian architectures only', default="current")
    parser.add_option('--orig', help='path to orig.tar.gz file')
    parser.add_option('-q', '--quiet', action="store_true", dest="quiet", default=False, help='run silently without confirmation')


def run(pkgdir, options, args):
    """main"""
    try :
        distributions = get_distributions(options.target_distribution)
        architectures = get_architectures(options.arch)
        for arch in architectures:
            for distrib in distributions:
                packages = build_debian(pkgdir,
                                        options.distdir,
                                        distrib,
                                        arch,
                                        options.debbuildopts,
                                        options.orig)
                run_checkers(packages,
                             options.distdir,
                             options.quiet)
    except Exception, exc:
        print >> sys.stderr, exc
        return 1


def run_checkers(packages, distdir, quiet=True):
    separator = '+' * 72
    # Run usual checkers
    checkers = ('lintian', 'linda')
    for checker in checkers:
        print separator
        if quiet or confirm("run %s on generated debian packages ?" % checker):
            for package in packages:
                if package.endswith('.deb'): # XXX : run on .changes file ? 
                    cond_exec('%s -i %s/%s' % (checker, distdir, package))

    # FIXME piuparts that doesn't work automatically for all our packages
    print separator
    if not quiet and confirm("run piuparts on generated debian packages ?"):
        for package in packages:
            if package.endswith('.deb'):
                cond_exec('sudo piuparts -p %s/%s' % (distdir, package))

