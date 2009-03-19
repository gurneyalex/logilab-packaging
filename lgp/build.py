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
import warnings
import os.path as osp
try:
    from subprocess import check_call, CalledProcessError # only python2.5
except ImportError:
    from logilab.common.compat import check_call, CalledProcessError

try:
    from debian_bundle import deb822
except ImportError:
    import deb822

from logilab.common.fileutils import export
from logilab.common.shellutils import cp

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import get_distributions, get_architectures
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
        distributions = get_distributions(builder.config.distrib,
                                          builder.config.basetgz)
        logging.info("running for distribution(s): %s" % ', '.join(distributions))
        architectures = get_architectures(builder.config.archi)

        if not builder.config.no_treatment:
            run_pre_treatments(builder)

        for arch in architectures:
            for distrib in distributions:
                packages = builder.compile(distrib=distrib, arch=arch)
                if not builder.config.no_treatment:
                    run_post_treatments(builder, packages, distrib)
                logging.info("new files are waiting in %s. Enjoy."
                             % builder.get_distrib_dir())
                logging.info("Debian changes file is: %s"
                             % builder.get_changes_file())
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

def run_post_treatments(builder, packages, distrib):
    """ Run actions after package compiling """
    distdir = builder.get_distrib_dir()
    verbose = builder.config.verbose

    # Check occurence in filesystem
    for package in packages:
        package = osp.join(distdir, package)
        if not osp.isfile(package):
            raise LGPException('File %s is missing due to a failed build'
                               % package)
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

    # Run some utility in verbose mode
    if verbose:
        for package in packages:
            if package.endswith('.diff.gz'):
                logging.info('Debian specific diff statistics (%s)' % package)
                cond_exec('diffstat %s' % os.path.join(distdir, package))

    # Run usual checkers
    checkers = {'debc': '', 'lintian': '-vi'}
    for checker, opts in checkers.iteritems():
        if not verbose or confirm("run %s on generated Debian changes files ?" % checker):
            for package in packages:
                if package.endswith('.changes'):
                    logging.info('%s checker information about %s' % (checker, package))
                    cond_exec('%s %s %s' % (checker, opts, os.path.join(distdir, package)))

    if verbose and confirm("run piuparts on generated Debian packages ?"):
        basetgz = "%s-%s.tgz" % (distrib, get_architectures()[0])
        for package in packages:
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
                           osp.join(distdir, package)]
                logging.debug("piuparts command: %s", ' '.join(cmdline))
                if cond_exec(' '.join(cmdline)):
                    logging.error("piuparts exits with error")
                else:
                    logging.info("piuparts exits normally")

    # Try Debian signing immediately if possible
    if check_debsign(builder):
        for package in packages:
            if package.endswith('.changes'):
                logging.info('try signing %s...' % package)
                if cond_exec('debsign %s' % osp.join(distdir, package)):
                    logging.error("the changes file has not been signed. "
                                  "Please run debsign manually")
    else:
        logging.warning("don't forget to debsign your Debian changes file")

    # Add tag when build is successful
    # FIXME tag format is not standardized yet
    # Comments on card "Architecture standard d'un paquet"
    #if verbose and confirm("Add upstream tag %s on %s ?" \
    #                       % (builder.get_upstream_version(),
    #                          builder.get_upstream_name())):
    #    from logilab.devtools.vcslib import get_vcs_agent
    #    vcs_agent = vcs_agent or get_vcs_agent('.')
    #    os.system(vcs_agent.tag(package_dir, release_tag))


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
               ('arch',
                {'type': 'string',
                 'dest': 'archi',
                 'default' : 'current',
                 'short': 'a',
                 'metavar' : "<architecture>",
                 'help': "build for the requested debian architectures only"
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
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Builder, self).__init__(arguments=args, options=self.options, usage=__doc__)

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

        # rewrite distrib to manage the 'all' case in run()
        self.current_distrib = distrib

        self._tmpdir = tempfile.mkdtemp()

        # create the upstream tarball and copy to the temporary directory
        upstream_tarball, tarball = self.create_orig_tarball()

        # origpath is depending of the upstream convention
        tarball = os.path.basename(tarball)
        tarball = tarball.rsplit('.orig.tar.gz')[0].replace('_', '-')
        origpath = os.path.join(self._tmpdir, tarball)

        # support of the multi-distribution
        self.manage_multi_distribution(origpath)

        # create a debian source package
        dscfile = self.make_debian_source_package(origpath)

        # build the package using vbuild or default to fakeroot
        if not self.config.deb_src_only:
           self._compile(distrib, arch, dscfile)

        # clean tmpdir
        os.chdir(self.config.pkg_dir)
        self.clean_tmpdir()

        return self.get_packages()

    def clean_tmpdir(self):
        if not self.config.keep_tmpdir:
            shutil.rmtree(self._tmpdir)

    def make_debian_source_package(self, origpath):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        dscfile = '%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version())
        filelist = ('%s_%s.diff.gz' % (self.get_debian_name(), self.get_debian_version()),
                    dscfile)

        logging.debug("start creation of the debian source package '%s'"
                      % osp.join(osp.dirname(origpath), dscfile))
        try:
            cmd = 'dpkg-source -b %s' % origpath
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
        return dscfile

    def manage_multi_distribution(self, origpath):
        """manage debian files depending of the distrib option

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the unstable version
        If a file should not be included, touch an empty file in the overlay
        directory"""
        try:
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian/'))
        except IOError, err:
            raise LGPException(str(err))

        if self.get_debian_dir() != "debian":
            logging.debug("overriding files...")
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, self.get_debian_dir()), osp.join(origpath, 'debian/'),
                   verbose=self.config.verbose)

        distrib = self.current_distrib
        # experimental should be linked to unstable and not rewritten
        if self.current_distrib == 'experimental':
            distrib = 'unstable'

        cmd = ['sed', '-i',
               's/\(unstable\|DISTRIBUTION\); urgency/%s; urgency/' %
               distrib, '%s' % os.path.join(origpath, 'debian/changelog')]
        try:
            check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("bad substitution for distribution field", err)

    def _compile(self, distrib, arch, dscfile):
        debuilder = os.environ.get('DEBUILDER', 'vbuild')
        logging.debug("use builder: '%s'" % debuilder)
        if debuilder.endswith('vbuild'):
            logging.info("building debian package for distribution '%s' and arch '%s'"
                         % (distrib, arch))
            cmd = '%s -d %s -a %s --result %s %s'
            cmd %= (debuilder, distrib, arch, self.get_distrib_dir(),
                    osp.join(self._tmpdir, dscfile))
            # TODO
            #cmd += ' --debbuildopts %s' % pdebuild_options
        else:
            cmd = debuilder

        try:
            check_call(cmd.split(), stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("failed autobuilding of package", err)

