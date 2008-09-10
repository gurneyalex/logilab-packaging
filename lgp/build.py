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
import logging
import os.path as osp
from subprocess import Popen, PIPE

from logilab.common.shellutils import mv
from logilab.common.fileutils import ensure_fs_mode, export

from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException)
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp.setupinfo import SetupInfo

KNOWN_DISTRIBUTIONS = ['etch', 'lenny', 'sid']

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
    logging.info("Creation of the Debian source package: %s" % origpath)
    os.system('dpkg-source -b %s' % origpath)

def build_debian(pkg_dir, dist_dir,
                 target_distribution,
                 architecture,
                 pdebuild_options='',
                 origpath=None, quiet=False):
    """ Build debian package and move them in <dist_dir>

    The debian package to build is expected to be in the current working
    directory

    Several checks are performed here to validate the debian directory structure

    :todo: drop the quiet parameter (used by apycot at the moment)

    :param:
        pkg_dir
            package directory
        dist_dir
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
    (pkg_dir, dist_dir, origpath) = [dir and osp.abspath(dir) for dir
                                     in (pkg_dir, dist_dir, origpath)]

    os.chdir(pkg_dir)

    # The convention is :
    # debian/ is for sid distrib
    # debian.$OTHER id for $OTHER distrib
    if target_distribution == 'sid':
        debiandir = 'debian'
    else:
        debiandir = 'debian.%s' % target_distribution

    # Retrieve upstream information
    try:
        pkginfo          = SetupInfo()
        upstream_name    = pkginfo.get_upstream_name()
        upstream_version = pkginfo.get_version()
        debian_name      = pkginfo.get_debian_name()
        debian_version   = pkginfo.get_debian_version(debiandir, origpath)
    except ImportError, err:
        logging.critical(err)
        sys.exit(1)

    info = (upstream_name, upstream_version, debian_name, debian_version)
    tmpdir = tempfile.mkdtemp()

    # check if destination directories exists, create it if necessary
    dist_dir = osp.join(dist_dir, target_distribution)
    try:
        os.makedirs(dist_dir)
    except OSError:
        # it's not a problem here to pass silently # when the directory
        # already exists
        pass

    try:
        # the upstream archive tarball is depending of the setup method
        tarball = pkginfo.create_orig_tarball(tmpdir, dist_dir,
                                               upstream_version,
                                               debian_name,
                                               origpath, pkg_dir, quiet)

        # create tmp build directory by extracting the .orig.tar.gz
        os.chdir(tmpdir)
        logging.debug("Extracting %s..." % tarball)
        status = os.system('tar xzf %s' % tarball)
        if status:
            raise IOError('An error occured while extracting the upstream '\
                          'tarball (return status: %s)' % status)

        # origpath is depending of the upstream convention
        origpath = tarball.rsplit('.orig.tar.gz')[0].replace('_', '-')

        # copying debiandir directory into tmp build depending of the target distribution
        # in all cases, we copy the debian directory of the sid version
        # DOC If a file should not be included, touch an empty file in the overlay directory
        if target_distribution != 'sid':
            shutil.copytree(osp.join(pkg_dir, 'debian'), osp.join(origpath, 'debian'))
        shutil.copytree(osp.join(pkg_dir, debiandir), osp.join(origpath, 'debian'))

        # build the package using vbuild or default to fakeroot
        debuilder = os.environ.get('DEBUILDER') or 'vbuild'
        if debuilder ==  'vbuild':
            make_source_package(origpath)
            dscfile = '%s_%s.dsc' % (debian_name, debian_version)
            logging.info("Building debian for distribution '%s' and arch '%s'" % (target_distribution,
                                                                                  architecture))
            cmd = 'vbuild -d %s -a %s --result %s %s'
            cmd %= (target_distribution, architecture, dist_dir, osp.join(tmpdir, dscfile))
            # TODO
            #cmd += ' --debbuildopts %s' % pdebuild_options
        else:
            cmd = debuilder
        if quiet:
            cmd += ' 1>/dev/null 2>/dev/null'
        logging.debug("[VBUILD] " + ''.join(cmd))
        status = os.system(cmd)
        if status:
            raise OSError('An error occured while building the debian package ' \
                          '(return status: %s)' % status)
    finally:
        logging.debug("please visit: %s" % tmpdir)
        #shutil.rmtree(tmpdir)
    os.chdir(pkg_dir)
    return pkginfo.get_packages()


def add_options(parser):
    parser.usage = 'lgp build [options] <args>'
    parser.add_option('--debbuildopts', default='',
                      help="options passed to pdebuild's --debbuildopts option")
    parser.add_option('--dist', dest='distdir', default=osp.expanduser('~/dist'),
                      help='where to put results')
    parser.add_option('-t', '--target-distribution', default='sid',
                      help='the distribution targetted (e.g. etch, lenny, sid). Use all for all known distributions')
    parser.add_option('-a', '--arch', default='current', help='build for the requested debian architectures only')
    parser.add_option('--orig', help='path to orig.tar.gz file')
    parser.add_option('--vcs', help='path to remote vcs source files')
    parser.add_option('-r', '--revision', help='set a specific revision to build the debian package')
    parser.add_option('-q', '--quiet', action="store_true", dest="quiet", default=False, help='run silently without confirmation')


def run(pkgdir, options, args):
    """ main function of lgp build command """
    logging.basicConfig(level=logging.DEBUG)
    try :
        distributions = get_distributions(options.target_distribution)
        architectures = get_architectures(options.arch)

        if options.vcs and options.vcs.startswith('ssh://'):
            # Manage a possible remote vcs capabilities
            # FIXME urlparse is limited to the rfc1738 scheme, too bad :-(
            # find a cleaner solution for other scheme http/ftp/file. regex ?
            # FIXME reorganize and use vcslib ?
            logging.critical(Popen(["hg", "clone", options.vcs], stderr=PIPE).communicate())

        if options.revision :
            logging.critical(Popen(["hg", "update", options.revision], stderr=PIPE).communicate())

        for arch in architectures:
            for distrib in distributions:
                packages = build_debian(pkgdir,
                                        options.distdir,
                                        distrib,
                                        arch,
                                        options.debbuildopts,
                                        options.orig)
                run_checkers(packages,
                             osp.join(options.distdir, distrib),
                             options.quiet)
    except Exception, exc:
        logging.error(exc)
        return 1


def run_checkers(packages, distdir, quiet=True):
    separator = '+' * 15 + ' %s'
    # Run usual checkers
    checkers = ('lintian', 'linda')
    for checker in checkers:
        if quiet or confirm("run %s on generated debian packages ?" % checker):
            for package in packages:
                print separator % package
                if not package.endswith('.diff.gz'):
                    cond_exec('%s -i %s/%s' % (checker, distdir, package))

    # FIXME piuparts that doesn't work automatically for all of our packages
    if not quiet and confirm("run piuparts on generated debian packages ?"):
        for package in packages:
            print separator % package
            if package.endswith('.deb'):
                cond_exec('sudo piuparts -p %s/%s' % (distdir, package))
