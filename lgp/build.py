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
""" lgp build [options]

    Provides functions to build a debian package for a python package
    You can use a setup.cfg file with the [LGP-BUILD] section
"""
__docformat__ = "restructuredtext en"

import os
import sys
import tempfile
import shutil
import logging
import pprint
import warnings
import os.path as osp
from subprocess import check_call, CalledProcessError

from debian_bundle import deb822

from logilab.common.fileutils import export
from logilab.common.shellutils import cp

from logilab.devtools.lgp import CONFIG_FILE
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

from logilab.devtools.lgp.check import Checker, check_debsign

# Set a list of checks to disable when we are in
# intermediate stage (i.e. when developing package)
INTERMEDIATE_STAGE = ['repository', ]


def run(args):
    """main function of lgp build command"""
    try :
        builder = Builder(args)

        if not builder.config.no_treatment:
            run_pre_treatments(builder)

        for arch in builder.architectures:
            for distrib in builder.distributions:
                if builder.compile(distrib=distrib, arch=arch):
                    if not builder.config.no_treatment and builder.packages:
                        run_post_treatments(builder, distrib)
                    logging.info("new files are waiting in %s. Enjoy.\n%s"
                                 % (builder.get_distrib_dir(),
                                   pprint.pformat(builder.packages)))
    except LGPException, exc:
        logging.critical(exc)
        #if hasattr(builder, "config") and builder.config.verbose:
        #    logging.debug("printing traceback...")
        #    raise
        return 1

def run_pre_treatments(builder):
    checker = Checker([])

    # Use the intermediate stage (i.e. developing package)
    if builder.config.intermediate:
        intermediate_exclude = builder.config.intermediate_exclude
        logging.info("ask for the intermediate stage (i.e. package development)")
        checker.config.exclude_checks = intermediate_exclude

    checker.start_checks()
    if checker.errors():
        logging.error('%d errors detected by pre-treatments' % checker.errors())

def run_post_treatments(builder, distrib):
    """ Run actions after package compiling """
    distdir = builder.get_distrib_dir()
    verbose = builder.config.verbose

    # Check occurence in filesystem
    for package in builder.packages:
        # Detect native package (often an error)
        if package.endswith('.dsc'):
            dsc = deb822.Dsc(file(package))
            orig = None
            for dscfile in dsc['Files']:
                if dscfile['name'].endswith('orig.tar.gz'):
                    orig = dscfile
                    break
            # There is no orig.tar.gz file in the dsc file. This is probably a native package.
            if verbose and orig is None:
                if not confirm("No orig.tar.gz file found in %s.\n"
                               "This is a native package (really) ?" % package):
                    return

    # FIXME provide a useful utility outside of lgp and use post-build-hook
    logging.info('try updating local repository in %s...' % distdir)
    command = "dpkg-scanpackages %s /dev/null | gzip -9c > %s/Packages.gz" % (distrib, distrib)
    logging.debug('run command: %s' % command)
    if cond_exec('which dpkg-scanpackages >/dev/null && cd %s && %s'
                 % (osp.dirname(distdir), command)):
        logging.debug("Packages file was not updated automatically")
    else:
        # clean other possible Packages files
        try:
            os.unlink(osp.join(distdir, 'Packages'))
            os.unlink(osp.join(distdir, 'Packages.bz2'))
        except:
            # not a problem to pass silently here
            pass

    # FIXME move code to apycot and detection of options from .changes
    """
    from logilab.devtools.lgp.utils import get_architectures
    if verbose and confirm("run piuparts on generated Debian packages ?"):
        basetgz = "%s-%s.tgz" % (distrib, get_architectures()[0])
        for package in builder.packages:
            if package.endswith('.deb'):
                logging.info('piuparts checker information about %s' % package)
                cmdline = ['sudo', 'piuparts', '--no-symlinks',
                           '--warn-on-others', '--keep-sources-list',
                           # the development repository can be somewhat buggy...
                           '--no-upgrade-test',
                           '-b', os.path.join(builder.config.basetgz, basetgz),
                           # just violent but too many false positives otherwise
                           '-I', '"/etc/shadow*"',
                           '-I', '"/usr/share/pycentral-data.*"',
                           '-I', '"/var/lib/dpkg/triggers/pysupport.*"',
                           '-I', '"/var/lib/dpkg/triggers/File"',
                           '-I', '"/usr/local/lib/python*"',
                           package]
                logging.debug("piuparts command: %s", ' '.join(cmdline))
                if cond_exec(' '.join(cmdline)):
                    logging.error("piuparts exits with error")
                else:
                    logging.info("piuparts exits normally")
    """

    # FIXME move code to debinstall
    # Try Debian signing immediately if possible
    if check_debsign(builder):
        for package in builder.packages:
            if package.endswith('.changes'):
                logging.info('try signing %s...' % package)
                if cond_exec('debsign %s' % package):
                    logging.error("the changes file has not been signed. "
                                  "Please run debsign manually")
    else:
        logging.warning("don't forget to debsign your Debian changes file")


class Builder(SetupInfo):
    """Lgp builder class

    Specific options are added. See lgp build --help
    """
    name = "lgp-build"
    options = (('result',
                {'type': 'string',
                 'default' : '~/dists',
                 'dest' : "dist_dir",
                 'short': 'r',
                 'metavar': "<directory>",
                 'help': "where to put compilation results"
                }),
               ('orig-tarball',
                {'type': 'string',
                 'default' : None,
                 'dest': 'orig_tarball',
                 'metavar' : "<tarball>",
                 'help': "path to orig.tar.gz file"
                }),
               ('keep-tmpdir',
                {'action': 'store_true',
                 #'default': False,
                 'dest' : "keep_tmpdir",
                 'help': "keep the temporary build directory"
                }),
               ('post-treatments',
                {'action': 'store_false',
                 #'default': True,
                 'dest' : "post_treatments",
                 'help': "compile packages with post-treatments (deprecated)"
                }),
               ('no-treatment',
                {'action': 'store_true',
                 #'default': False,
                 'dest' : "no_treatment",
                 'help': "compile packages with no auxiliary treatment"
                }),
               ('deb-src',
                {'action': 'store_true',
                 #'default': False,
                 'dest' : "deb_src_only",
                 'help': "obtain a debian source package without build"
                }),
               ('get-orig-source',
                {'action': 'store_true',
                 #'default': False,
                 'dest' : "get_orig_source",
                 'help': "create a reasonable upstream tarball"
                }),
               ('intermediate',
                {'action': 'store_true',
                 #'default': False,
                 'dest' : "intermediate",
                 'short': 'i',
                 'help': "use an intermediate mode when developing a package",
                }),
               ('intermediate-exclude',
                {'type': 'csv',
                 #'hide': True,
                 'dest' : "intermediate_exclude",
                 'default' : INTERMEDIATE_STAGE,
                 'metavar' : "<comma separated names of checks to skip>",
                }),
               ('hooks',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "hooks",
                 'help': "run hooks"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Builder, self).__init__(arguments=args, options=self.options, usage=__doc__)

        # Add packages metadata
        self.packages = []

        # TODO make a more readable logic in OptParser values
        if not self.config.post_treatments:
            warnings.warn("Option post-treatment is deprecated. Use no-treatment instead.", DeprecationWarning)
            self.config.no_treatment = True

        # Redirect subprocesses stdout output only in case of verbose mode
        # We always allow subprocesses to print on the stderr (more convenient)
        if not self.config.verbose:
            sys.stdout = open(os.devnull,"w")
            #sys.stderr = open(os.devnull,"w")


    def compile(self, distrib, arch):
        self.clean_repository()

        logging.info("building debian package for distribution '%s' and arch '%s'"
                     % (distrib, arch))

        # rewrite distrib to manage the 'all' case in run()
        self.current_distrib = distrib

        self._tmpdir = tempfile.mkdtemp()

        # create the upstream tarball if necessary and copy to the temporary
        # directory following the Debian practices
        upstream_tarball, tarball, origpath = self.make_orig_tarball()

        # support of the multi-distribution
        self.manage_multi_distribution(origpath)

        # Intermediate facility for debugging (really useful ?)
        if self.config.intermediate:
            os.chdir(origpath)
            try:
                cmd = 'debuild --no-tgz-check --no-lintian --clear-hooks -uc -us'
                check_call(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
            except CalledProcessError, err:
                msg = "error with your package"
                raise LGPCommandException(msg, err)
            import glob
            self.packages = glob.glob('../%s_%s_*.changes'
                                      % (self.get_upstream_name(),
                                         self.get_debian_version()))
            return

        # create a debian source package
        dscfile = self.make_debian_source_package(origpath)

        # build the package using vbuild or default to fakeroot
        self._compile(distrib, arch, dscfile)
        self.copy_package_files()

        # clean tmpdir
        self.clean_tmpdir()
        return True

    def clean_tmpdir(self):
        if not self.config.keep_tmpdir:
            shutil.rmtree(self._tmpdir)
        else:
            logging.info("keep temporary directory '%s'" % self._tmpdir)

    def make_debian_source_package(self, origpath):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        # change directory context
        os.chdir(self._tmpdir)

        fileparts = (self.get_debian_name(), self.get_debian_version())
        dscfile = '%s_%s.dsc' % fileparts
        filelist = ('%s_%s.diff.gz' % fileparts, dscfile)

        logging.debug("start creation of the debian source package '%s'"
                      % osp.join(osp.dirname(origpath), dscfile))
        try:
            cmd = 'dpkg-source -b %s' % origpath
            # FIXME use one copy of the upstream tarball
            #if self.config.orig_tarball:
            #    cmd += ' %s' % self.config.orig_tarball
            check_call(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file '%s' with command %s" % (dscfile, cmd)
            raise LGPCommandException(msg, err)

        if self.config.deb_src_only:
            for filename in filelist:
                logging.debug("copy '%s' to '%s'" % (filename, self.get_distrib_dir()))
                cp(filename, self.get_distrib_dir())
            logging.info("Debian source control file is: %s"
                         % osp.join(self.get_distrib_dir(), dscfile))

        # exit if asked by command-line
        if self.config.deb_src_only:
            # clean tmpdir
            self.clean_tmpdir()
            sys.exit()

        # restore directory context
        os.chdir(self.config.pkg_dir)

        return dscfile

    def manage_multi_distribution(self, origpath):
        """manage debian files depending of the distrib option

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the unstable version
        If a file should not be included, touch an empty file in the overlay
        directory.

        The distribution value will always be rewritten in final changelog.
        """
        try:
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian/'))
        except IOError, err:
            raise LGPException(err)

        if self.get_debian_dir() != "debian":
            logging.info("overriding files from '%s' directory..." % self.get_debian_dir())
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, self.get_debian_dir()), osp.join(origpath, 'debian/'),
                   verbose=self.config.verbose)

        distrib = self.current_distrib

        #logging.debug("rewrite distribution name to '%s'" % distrib)
        # dch will update the changelog timestamp as well
        #cmd = ['dch', '--force-distribution', '--distribution', '%s' % distrib, '']

        # substitute distribution string in file only if line not starting by
        # spaces (simple heuristic to prevent other changes in content)
        cmd = ['sed', '-i', '/^[[:alpha:]]/s/\([[:alpha:]]\+\);/%s;/' % distrib,
               osp.join(origpath, 'debian', 'changelog')]
        try:
            check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("bad substitution for distribution field", err)

    def _compile(self, distrib, arch, dscfile):
        """virtualize the package build process"""
        debuilder = os.environ.get('DEBUILDER', 'internal')
        logging.debug("select package builder: '%s'" % debuilder)
        dscfile = osp.join(self._tmpdir, dscfile)
        assert osp.exists(dscfile)

        if debuilder == 'internal':
            cmd = "sudo DIST=%s ARCH=%s pbuilder build --configfile %s --buildresult %s"
            cmd %= distrib, arch, CONFIG_FILE, self._tmpdir
            if self.config.hooks:
                from logilab.devtools.lgp import HOOKS_DIR
                cmd += " --hookdir %s" % HOOKS_DIR
            cmd += " %s" % dscfile
        elif debuilder.endswith('vbuild'):
            cmd = '%s -d %s -a %s --result %s %s'
            cmd %= (debuilder, distrib, arch, self.get_distrib_dir(), dscfile)
        else:
            cmd = debuilder

        logging.info("run build command: %s" % cmd)
        try:
            check_call(cmd.split(), env={'DIST': distrib, 'ARCH': arch}, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("failed autobuilding of package", err)

    def copy_package_files(self):
        """copy package files from the temporary build area to the result directory

        we define here the self.packages variable used by post-treatment
        """
        self.packages = []
        for filename in os.listdir(self._tmpdir):
            fullpath = os.path.join(self._tmpdir, filename)
            if os.path.isfile(fullpath):
                shutil.copy(fullpath, self.get_distrib_dir())
                self.packages.append(os.path.join(self.get_distrib_dir(), filename))

