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
import glob
import tempfile
import shutil
import logging
import os.path as osp
#from subprocess import Popen, PIPE
try:
    from subprocess import check_call, CalledProcessError # only python2.5
except ImportError:
    from logilab.common.compat import check_call, CalledProcessError

from debian_bundle import deb822

from logilab.common.fileutils import export
from logilab.common.shellutils import cp

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import get_distributions, get_architectures
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException


def run(args):
    """main function of lgp build command"""
    try :
        builder = Builder(args)
        distributions = get_distributions(builder.config.distrib)
        if builder.config.distrib == "all":
            logging.info("retrieved distribution(s) with 'all': %s" %
                         str(distributions))
        architectures = get_architectures(builder.config.archi)

        #if builder.config.revision :
        #    logging.critical(Popen(["hg", "update", builder.config.revision], stderr=PIPE).communicate())

        for arch in architectures:
            for distrib in distributions:
                packages = builder.compile(distrib=distrib, arch=arch)
                logging.info("new files are waiting in %s. Enjoy."
                             % builder.get_distrib_dir())
                logging.info("Debian changes file is: %s"
                             % builder.get_changes_file())
                if builder.config.post_treatments:
                    run_post_treatments(packages, builder.get_distrib_dir(), distrib,
                                        builder.config.verbose)
    except LGPException, exc:
        logging.critical(exc)
        #if hasattr(builder, "config") and builder.config.verbose:
        #    logging.debug("printing traceback...")
        #    raise
        return 1

def run_post_treatments(packages, distdir, distrib, verbose=False):
    """ Run actions after package compiling """
    separator = '+' * 15 + ' %s'

    # Detect native package
    for package in packages:
        if package.endswith('.dsc'):
            package = glob.glob(osp.join(distdir, package))[0]
            dsc = deb822.Dsc(file(package))
            orig = None
            for dscfile in dsc['Files']:
                if dscfile['name'].endswith('orig.tar.gz'):
                    orig = dscfile
                    break
            # There is no orig.tar.gz file in the dsc file. This is probably a native package.
            if orig is None:
                if not confirm("No orig.tar.gz file found in %s.\n"
                               "Really a native package (suspect) ?" % package):
                    return

    # Run usual checkers
    checkers = {'debc': '', 'lintian': '-vi',}
    for checker, opts in checkers.iteritems():
        if not verbose or confirm("run %s on generated Debian changes files ?" % checker):
            for package in packages:
                if package.endswith('.changes'):
                    print separator % package
                    cond_exec('%s %s %s/%s' % (checker, opts, distdir, package))

    if verbose and confirm("run piuparts on generated Debian packages ?"):
        basetgz = "%s-%s.tgz" % (distrib, get_architectures()[0])
        for package in packages:
            print separator % package
            if package.endswith('.deb'):
                cmdline = ['sudo', 'piuparts', '--no-symlinks',
                           '--warn-on-others', '--keep-sources-list',
                           '-b', '/opt/buildd/%s' % basetgz,
                           # just violent but too many false positives otherwise
                           '-I', '/usr/share/pycentral-data.*',
                           '-I', '/var/lib/dpkg/triggers/pysupport.*',
                           osp.join(distdir, package)]
                logging.debug("piuparts command: %s", ' '.join(cmdline))
                if cond_exec(' '.join(cmdline)):
                    logging.error("piuparts exits with error")
                else:
                    logging.info("piuparts exits normally")

    # Try Debian signing immediately if possible
    if 'DEBSIGN_KEYID' in os.environ:
        if not verbose or confirm("debsign your packages ?"):
            for package in packages:
                if package.endswith('.changes'):
                    print separator % package
                    cond_exec('debsign %s' % osp.join(distdir, package))

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
    """ Debian builder class

    Specific options are added. See lgp build --help
    """
    name = "lgp-build"
    options = (('result',
                {'type': 'string',
                 'default' : osp.expanduser('~/dists'),
                 'dest' : "dist_dir",
                 'short': 'r',
                 'metavar': "<directory>",
                 'help': "where to put compilation results"
                }),
               ('distrib',
                {'type': 'choice',
                 'choices': get_distributions() + ('all',),
                 'dest': 'distrib',
                 'default' : 'unstable',
                 'short': 'd',
                 'metavar': "<distribution>",
                 'help': "the distribution targetted (e.g. stable, unstable). Use 'all' for all known distributions"
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
                 'default': False,
                 'dest' : "keep_tmpdir",
                 'help': "keep the temporary build directory"
                }),
               ('post-treatments',
                {'action': 'store_false',
                 'default': True,
                 'dest' : "post_treatments",
                 'help': "compile packages with post treatments"
                }),
               ('deb-src',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "deb_src",
                 # TODO #4667: generate debian source package
                 'help': "obtain a debian source package (not implemented)"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Builder, self).__init__(arguments=args, options=self.options, usage=__doc__)
        #print self.generate_config(); sys.exit()

        if self.config.orig_tarball is not None:
            self.config.orig_tarball = osp.abspath(osp.expanduser(self.config.orig_tarball))
        if self.config.dist_dir is not None:
            self.config.dist_dir = osp.abspath(self.config.dist_dir)

        # Redirect subprocesses stdout output only in case of verbose mode
        # We always allow subprocesses to print on the stderr (more convenient)
        if not self.config.verbose:
            sys.stdout = open(os.devnull,"w")
            #sys.stderr = open(os.devnull,"w")

        # check if distribution directory exists, create it if necessary
        try:
            os.makedirs(self.get_distrib_dir())
        except OSError:
            # it's not a problem here to pass silently # when the directory
            # already exists
            pass

    def compile(self, distrib, arch):
        # rewrite distrib to manage the 'all' case in run()
        self.config.distrib = distrib

        self._tmpdir = tmpdir = tempfile.mkdtemp()

        self.clean_repository()
        tarball = self.create_orig_tarball(tmpdir)

        # create tmp build directory by extracting the .orig.tar.gz
        os.chdir(tmpdir)
        logging.debug("extracting %s..." % tarball)
        try:
            check_call(('tar xzf %s' % tarball).split(), stdout=sys.stdout,
                                                         stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException('an error occured while extracting the '
                                      'upstream tarball', err)

        # origpath is depending of the upstream convention
        tarball = os.path.basename(tarball)
        tarball = tarball.rsplit('.orig.tar.gz')[0].replace('_', '-')
        origpath = os.path.join(tmpdir, tarball)

        # support of the multi-distribution
        self.manage_multi_distribution(origpath)

        # build the package using vbuild or default to fakeroot
        debuilder = os.environ.get('DEBUILDER', 'vbuild')
        logging.debug("use builder: '%s'" % debuilder)
        if debuilder.endswith('vbuild'):
            dscfile = self.make_debian_source_package(origpath)
            logging.info("building debian package for distribution '%s' and arch '%s'"
                             % (distrib, arch))
            cmd = '%s -d %s -a %s --result %s %s'
            cmd %= (debuilder, distrib, arch, self.get_distrib_dir(),
                    osp.join(tmpdir, dscfile))
            # TODO
            #cmd += ' --debbuildopts %s' % pdebuild_options
        else:
            cmd = debuilder

        try:
            check_call(cmd.split(), stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("failed autobuilding of package", err)

        # double check vbuild results
        for pack in self.get_packages():
            fullpath = os.path.join(self.get_distrib_dir(), pack)
            if not glob.glob(fullpath):
                raise LGPException('vbuild ran, but %s not found' % fullpath)

        # clean tmpdir
        self.clean_tmpdir()

        return self.get_packages()

    def clean_tmpdir(self):
        if not self.config.keep_tmpdir:
            shutil.rmtree(self._tmpdir)

    def get_distrib_dir(self):
        """ get the dynamic target release directory """
        return osp.join(self.config.dist_dir, self.config.distrib)

    def make_debian_source_package(self, origpath):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        dscfile = '%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version())
        filelist = ((dscfile,
                     "add '%s' as debian source package control file (.dsc)"
                    ),
                    ('%s_%s.diff.gz' % (self.get_debian_name(), self.get_debian_version()),
                     "add '%s' as debian specific diff (.diff.gz)")
                   )

        logging.debug("start creation of the debian source package '%s'"
                      % osp.join(osp.dirname(origpath), dscfile))
        try:
            cmd = 'dpkg-source -b %s' % origpath
            returncode = check_call(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file '%s' with command %s" % (dscfile, cmd)
            raise LGPCommandException(msg, err)

        if self.config.deb_src:
            for filename,msg in filelist:
                logging.debug("copy '%s' to '%s'" % (filename, self.config.dist_dir))
                cp(filename, self.config.dist_dir)
                logging.info(msg % osp.join(self.config.dist_dir, filename))
            self.clean_tmpdir()
            sys.exit(returncode)
        return dscfile

    def manage_multi_distribution(self, origpath):
        """manage debian files depending of the distrib option

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the unstable version
        If a file should not be included, touch an empty file in the overlay
        directory"""
        export(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian'))
        debiandir = self.get_debian_dir()
        if debiandir != 'debian/':
            logging.debug("overriding files...")
            export(osp.join(self.config.pkg_dir, debiandir), osp.join(origpath, 'debian/'),
                   verbose=self.config.verbose)

        cmd = ['sed', '-i',
               's/\(unstable\|DISTRIBUTION\); urgency/%s; urgency/' %
               self.config.distrib,
               '%s' % os.path.join(origpath, 'debian/changelog')]
        try:
            check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("bad substitution for distribution field", err)
