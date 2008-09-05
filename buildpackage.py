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
        logging.debug("looking for %s in .." % source_dist)
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

def create_orig_tarball(origdir, tmpdir, dest_dir,
                        upstream_version,
                        debian_name,
                        origpath, pkg_dir, quiet=False):
    """ Create an origin tarball by the way of setuptools utility
    """
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

        # Another method : use scm capabilities
        # tarball = '%s_%s.orig.tar.gz' % (debian_name, upstream_version)
        # origpath = osp.join(tmpdir, tarball)
        # logging.critical(Popen(["hg", "archive", "-X", "debian", "-t", "tgz", "-p", origdir, origpath], stderr=PIPE).communicate())
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
    logging.info("Creation of the Debian source package")
    os.system('dpkg-source -b %s' % origpath)

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

    os.chdir(pkg_dir)

    # Retrieve upstream information
    # - use setuptools format and improve __pkginfo__ ?
    # - use a generic Makefile iand environment variable (unix standard) ?
    # - use a transitional format (.ini, .doap) ?
    # - use a generic tool aka 'lgp info' (rebirth) ?
    #
    # Dispute: quel format utiliser pour les informations upstream ? Nous
    # devons partir du postulat que nous ne maitrîsons pas obligatoirement le
    # format utilisé par les développeurs
    #
    # Avantages et inconvénients de __pkginfo__ pose plusieurs problèmes
    # (+) pourrait faciliter la création de pseudo-standard eggs (non encore finalisés dans stdlib)
    #     Utile seulement dans le cas de code python
    # (+) Le MANIFEST.in permet la (dé)sélection de fichiers indépendamment du scm
    # (+) ...
    # (-) La machinerie setuptools doit être embarquée et tout paquet est dépendant de python :-\
    # (-) Le format __pkginfo__.py est propre à Logilab est difficilement utilisable par d'autres
    #     Plusieurs fichiers sont ajoutés comme : announce.txt, setup.py, DEPENDS, ...
    # (-) ...
    try:
        pkginfo          = PackageInfo()
        upstream_name    = pkginfo.name
        upstream_version = pkginfo.version
        debian_name      = pkginfo.debian_name
    except ImportError, err:
        logging.critical(err)
        sys.exit(1)

    # The convention is :
    # debian/ is for sid distrib
    # debian.$OTHER id for $OTHER distrib 
    if target_distribution == 'sid':
        debiandir = 'debian'
    else:
        debiandir = 'debian.%s' % target_distribution

    # Debian version is the last numeric part of the package name
    # <sourcepackage>_<upstreamversion>-<debian_version>
    debian_version   = DebianChangeLog('%s/changelog' % debiandir).get_latest_revision()
    if debian_version.debian_version != '1' and origpath is None:
        raise ValueError('unable to build %s %s: --orig option is required when '\
                         'not building the first version of the debian package'
                         % (debian_name, debian_version))

    info = (upstream_name, upstream_version, debian_name, debian_version)
    tmpdir = tempfile.mkdtemp()

    # FIXME Merge code with check_debian_setup() in checkpackage.py
    # TODO add possible debhelper tests here ?
    #if not osp.isdir(pkg_dir+ '/debian'):
    #    logging.fatal("Missing directory: 'debian/'")
    #    sys.exit(1)
    #if not osp.isfile('README') and not osp.isfile('README.txt'):
    #    logging.fatal("Missing file: 'README[.txt]'")
    #    sys.exit(1)
    #if not osp.isfile(pkg_dir + '/debian/rules'):
    #    logging.fatal("Missing file: 'debian/rules'")
    #    sys.exit(1)
    #if not osp.isfile(pkg_dir + '/debian/copyright'):
    #    logging.fatal("Missing file: 'debian/copyright'")
    #    sys.exit(1)
    #ensure_fs_mode('debian/rules', stat.S_IEXEC)

    # check if destination directories exists, create it if necessary
    dest_dir = osp.join(dest_dir, target_distribution)
    try:
        os.makedirs(dest_dir)
    except OSError:
        # it's not a problem here to pass silently # when the directory
        # already exists
        pass

    try:
        origdir = '%s-%s' % (upstream_name, upstream_version)
        # if needed create archive projectname-version.orig.tar.gz using setup.py sdist into tmpdir
        origpath = create_orig_tarball(origdir, tmpdir, dest_dir,
                                       upstream_version,
                                       debian_name,
                                       origpath, pkg_dir, quiet)

        # create tmp build directory by extracting the .orig.tar.gz
        os.chdir(tmpdir)
        status = os.system('tar xzf %s' % origpath)
        if status:
            raise IOError('An error occured while extracting the upstream '\
                          'tarball (return status: %s)' % status)

        # copying debiandir directory into tmp build depending of the target distribution
        # in all cases, we copy the debian directory of the sid version
        #export(osp.join(pkg_dir, debiandir), '%s/debian' % origdir, verbose=quiet)
        # FIXME why not copytree ?
        if target_distribution != 'sid':
            shutil.copytree(osp.join(pkg_dir, 'debian/'), osp.join(origdir, 'debian'))
        shutil.copytree(osp.join(pkg_dir, debiandir), osp.join(origdir, 'debian'))
        # DOC If a file should not be included, touch an empty file in the overlay directory

        # build the package using vbuild or default to fakeroot
        debuilder = os.environ.get('DEBUILDER') or 'vbuild'
        if debuilder ==  'vbuild':
            make_source_package(osp.join(tmpdir, origdir))
            dscfile = '%s_%s.dsc' % (debian_name, debian_version)
            logging.info("Building debian for distribution '%s' and arch '%s'" % (target_distribution,
                                                                                  architecture))
            cmd = 'vbuild -d %s -a %s --result %s %s'
            cmd %= (target_distribution, architecture, dest_dir, osp.join(tmpdir, dscfile))
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
        os.chdir(pkg_dir)

        # --------------------------------------------------
        #for archi in architecture:
        #    for distrib in target_distribution:
        #        build(FILE_DSC, distrib, archi, origdir)


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
        logging.debug("please visit: %s" % tmpdir)
        #shutil.rmtree(tmpdir)


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
