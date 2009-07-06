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
import time
import tempfile
import shutil
import glob
import logging
import pprint
import warnings
import os.path as osp
from subprocess import check_call, CalledProcessError, PIPE

from debian_bundle import deb822

from logilab.common.fileutils import export

from logilab.devtools.lgp import CONFIG_FILE
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

from logilab.devtools.lgp.check import Checker, check_debsign


def run(args):
    """main function of lgp build command"""
    try :
        builder = Builder(args)

        # Too bloated to be used here. Use pre-hook if available
        #if not builder.config.no_treatment:
        #    run_pre_treatments(builder)

        for arch in builder.architectures:
            for distrib in builder.distributions:
                if builder.compile(distrib=distrib, arch=arch):
                    if not builder.config.no_treatment and builder.packages:
                        run_post_treatments(builder, distrib)
    except LGPException, exc:
        logging.critical(exc)
        #if hasattr(builder, "config") and builder.config.verbose:
        #    logging.debug("printing traceback...")
        #    raise
        return 1

def run_pre_treatments(builder):
    # TODO add lgp hook possibility
    pass

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

    # FIXME move code to apycot and detection of options from .changes
    from logilab.devtools.lgp.utils import get_architectures
    if verbose: # and confirm("run piuparts on generated Debian packages ?"):
        basetgz = "%s-%s.tgz" % (distrib, get_architectures()[0])
        for package in builder.packages:
            if package.endswith('.deb'):
                #logging.info('piuparts checker information about %s' % package)
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
                logging.debug('piuparts test has been disabled but you can run it manually with:')
                logging.debug("piuparts command: %s", ' '.join(cmdline))
                #if cond_exec(' '.join(cmdline)):
                #    logging.error("piuparts exits with error")
                #else:
                #    logging.info("piuparts exits normally")

    # FIXME move code to debinstall
    # Try Debian signing immediately if possible
    if check_debsign(builder):
        for package in builder.packages:
            if package.endswith('.changes'):
                logging.info('signing %s...' % package)
                if cond_exec('debsign %s' % package, force=not verbose):
                    logging.error("the changes file has not been signed. "
                                  "Please run debsign manually")
    else:
        logging.warning("don't forget to debsign your Debian changes file")

    # FIXME provide a useful utility outside of lgp and use post-build-hook
    logging.info('updating Debian local repository in %s...' % distdir)
    command = "dpkg-scanpackages %s /dev/null 2>/dev/null | gzip -9c > %s/Packages.gz" % (distrib, distrib)
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
               ('suffix',
                {'type': 'string',
                 'dest': 'suffix',
                 'metavar' : "<suffix>",
                 'help': "suffix to append to the Debian package. Tip: prepend by '~' for pre-release and '+' for post-release"
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

        logging.info("building debian package for distribution '%s' and arch '%s' ..."
                     % (distrib, arch))

        # rewrite distrib to manage the 'all' case in run()
        self.current_distrib = distrib

        self._tmpdir = tempfile.mkdtemp()

        # create the upstream tarball if necessary and copy to the temporary
        # directory following the Debian practices
        upstream_tarball, tarball, origpath = self.make_orig_tarball()

        # support of the multi-distribution
        self.manage_multi_distribution(distrib, origpath)

        # create a debian source package
        dscfile = self.make_debian_source_package(origpath)

        # build the package using one the available builders
        try:
            self._compile(distrib, arch, dscfile, origpath)
        finally:
            # copy some of created files like the build log
            self.copy_package_files()
        return True

    def clean_tmpdir(self):
        if not self.config.keep_tmpdir:
            shutil.rmtree(self._tmpdir)
        else:
            logging.warn("keep temporary directory '%s' for further investigation"
                         % self._tmpdir)

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

        logging.debug("start creation of the debian source package in '%s'"
                      % origpath)
        try:
            cmd = 'dpkg-source -b %s' % origpath
            # FIXME use one copy of the upstream tarball
            #if self.config.orig_tarball:
            #    cmd += ' %s' % self.config.orig_tarball
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file with command %s" % cmd
            raise LGPCommandException(msg, err)

        # retrieve real filename (depending of Debian revision suffix)
        dscfile = glob.glob('*.dsc')[0]

        # exit if asked by command-line
        if self.config.deb_src_only:
            self.copy_package_files()
            sys.exit()

        # restore directory context
        os.chdir(self.config.pkg_dir)

        return dscfile

    def manage_multi_distribution(self, distrib, origpath):
        """manage debian files depending of the current distrib from options

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the default version (unstable)
        If a file should not be included, touch an empty file in the overlay
        directory.

        The distribution value will always be rewritten in final changelog.
        """
        try:
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian/'))
        except IOError, err:
            raise LGPException(err)

        debian_dir = self.get_debian_dir()
        if debian_dir != "debian":
            logging.info("overriding files from '%s' directory..." % debian_dir)
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, debian_dir), osp.join(origpath, 'debian/'),
                   verbose=self.config.verbose)

        # substitute distribution string in file only if line not starting by
        # spaces (simple heuristic to prevent other changes in content)
        cmd = ['sed', '-i', '/^[[:alpha:]]/s/\([[:alpha:]]\+\);/%s;/'
               % distrib, osp.join(origpath, 'debian', 'changelog')]
        try:
            check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("bad substitution for distribution field", err)

        # substitute version string in appending timestamp and suffix
        # suffix should not be empty
        if self.config.suffix:
            timestamp = int(time.time())
            cmd = ['sed', '-i', '1s/(\(.*\))/(%s:\\1%s)/' % (timestamp, self.config.suffix),
                   osp.join(origpath, 'debian', 'changelog')]
            try:
                check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
            except CalledProcessError, err:
                raise LGPCommandException("bad substitution for version field", err)

    def _compile(self, distrib, arch, dscfile, origpath):
        """virtualize the package build process"""
        debuilder = os.environ.get('DEBUILDER', 'pbuilder')
        logging.debug("select package builder: '%s'" % debuilder)
        dscfile = osp.join(self._tmpdir, dscfile)
        assert osp.exists(dscfile)

        if debuilder == 'pbuilder':
            cmd = "sudo DIST=%s ARCH=%s pbuilder build --configfile %s --buildresult %s"
            cmd %= distrib, arch, CONFIG_FILE, self._tmpdir
            if self.config.hooks:
                from logilab.devtools.lgp import HOOKS_DIR
                cmd += " --hookdir %s" % HOOKS_DIR
            cmd += " %s" % dscfile
        elif debuilder == 'debuild':
            os.chdir(origpath)
            cmd = 'debuild --no-tgz-check --no-lintian --clear-hooks -uc -us'
        elif debuilder == 'fakeroot':
            os.chdir(origpath)
            cmd = 'fakeroot debian/rules binary'
        else:
            cmd = debuilder

        logging.info("running build command: %s ..." % cmd)
        try:
            check_call(cmd.split(), env={'DIST': distrib, 'ARCH': arch}, stdout=PIPE)
        except CalledProcessError, err:
            # keep arborescence for further debug
            self.config.keep_tmpdir = True
            raise LGPCommandException("failure in package build", err)

    def copy_package_files(self):
        """copy package files from the temporary build area to the result directory

        we define here the self.packages variable used by post-treatment
        """
        self.packages = []
        distdir = self.get_distrib_dir()
        for filename in os.listdir(self._tmpdir):
            fullpath = os.path.join(self._tmpdir, filename)
            if os.path.isfile(fullpath):
                logging.debug("copy %s to %s" % (fullpath, distdir))
                shutil.copy(fullpath, distdir)
                copied_filename = os.path.join(distdir(), filename)
                assert osp.exists(copied_filename)
                self.packages.append(copied_filename)
                if filename.endswith('.lgp-build'):
                    logging.info("a build logfile is available: %s" % copied_filename)
                if self.config.deb_src_only and filename.endswith('.dsc'):
                    logging.info("Debian source control file is: %s"
                                 % copied_filename)
                if self.config.get_orig_source and filename.endswith('.tar.gz'):
                    logging.info('a new original source archive (tarball) is available: %s'
                                 % copied_filename)
                if filename.endswith('.changes'):
                    logging.info("Debian changes file is: %s" % copied_filename)

        # clean tmpdir
        self.clean_tmpdir()

        # lastly print changes file to the console
        logging.debug("complete list of files:\n%s" % pprint.pformat(self.packages))

    def get_distrib_dir(self):
        """get the dynamic target release directory"""
        distrib_dir = os.path.join(os.path.expanduser(self.config.dist_dir),
                                   self.current_distrib)
        # check if distribution directory exists, create it if necessary
        try:
            os.makedirs(distrib_dir)
        except OSError:
            # it's not a problem here to pass silently # when the directory
            # already exists
            pass
        return distrib_dir
