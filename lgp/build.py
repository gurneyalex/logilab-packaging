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
import stat
import glob
import tempfile
import shutil
import logging
import os.path as osp
from subprocess import Popen, PIPE, check_call, CalledProcessError
from debian_bundle import deb822

from logilab.common.shellutils import mv
from logilab.common.fileutils import ensure_fs_mode, export

from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import get_distributions, get_architectures
from logilab.devtools.lgp.utils import confirm, cond_exec


def run(args):
    """ Main function of lgp build command """
    builder = Builder(args)
    # FIXME when production version is ready
    #try :
    distributions = get_distributions(builder.config.distrib)
    architectures = get_architectures(builder.config.archi)

    #if builder.config.revision :
    #    logging.critical(Popen(["hg", "update", builder.config.revision], stderr=PIPE).communicate())

    for arch in architectures:
        for distrib in distributions:
            packages = builder.compile(distrib=distrib, arch=arch)
            builder.logger.info("New compiled packages (%s) are waiting in %s. Enjoy." %
                                (",".join(packages), builder.get_distrib_dir()))
            if builder.config.post_treatments:
                run_post_treatments(packages, builder.get_distrib_dir(), distrib,
                                    builder.config.verbose)
    #except Exception, exc:
    #    logging.critical(exc)
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

    # Try Debian signing immediately if possible
    if 'DEBSIGN_KEYID' in os.environ and not verbose or confirm("debsign your packages ?"):
        for package in packages:
            if package.endswith('.changes'):
                print separator % package
                cond_exec('debsign %s' % osp.join(distdir, package))

    # Run usual checkers
    checkers = ('lintian',)
    for checker in checkers:
        if not verbose or confirm("run %s on generated debian packages ?" % checker):
            for package in packages:
                if package.endswith('.changes'):
                    print separator % package
                    cond_exec('%s -i %s/%s' % (checker, distdir, package))

    # FIXME piuparts that doesn't work automatically for all of our packages
    # FIXME manage correctly options.verbose and options.keep_tmp by piuparts
    if verbose and confirm("run piuparts on generated debian packages ?"):
        for package in packages:
            print separator % package
            if package.endswith('.deb'):
                cond_exec('sudo piuparts -v -d %s -p %s/%s' % (distrib, distdir, package))

class Builder(SetupInfo):
    """ Debian builder class

    Specific options are added. See lgp build --help
    """
    name = "lgp-build"
    options = (('dist',
                {'type': 'string',
                 #'default' : osp.expanduser('~/dist'),
                 'dest' : "dist_dir",
                 'metavar': "<directory>",
                 'help': "where to put compilation results"
                }),
               ('distrib',
                {'type': 'choice',
                 'choices': get_distributions(),
                 'dest': 'distrib',
                 #'default' : 'sid',
                 'metavar' : "<distribution>",
                 'help': "the distribution targetted (e.g. stable, unstable, sid). Use 'all' for all known distributions"
                }),
               ('arch',
                {'type': 'string',
                 'dest': 'archi',
                 #'default' : 'current',
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
        self.logger = logging.getLogger(__name__)

        # FIXME logilab.common.configuration doesn't like default values :-(
        # FIXME Duplicated code between commands
        # Be sure to have absolute path here
        if self.config.orig_tarball is not None:
            self.config.orig_tarball = osp.abspath(osp.expanduser(self.config.orig_tarball))
        if self.config.dist_dir is None:
            self.config.dist_dir = osp.expanduser("~/dist")
        else:
            self.config.dist_dir = osp.abspath(self.config.dist_dir)
        if self.config.archi is None:
            self.config.archi = 'current'
        if self.config.distrib is None:
            self.config.distrib = 'sid'

        # check if distribution directory exists, create it if necessary
        try:
            os.makedirs(self.get_distrib_dir())
        except OSError:
            # it's not a problem here to pass silently # when the directory
            # already exists
            pass

    def compile(self, distrib, arch):
        tmpdir = tempfile.mkdtemp()

        self.clean_repository()
        tarball = self.create_orig_tarball(tmpdir)

        # create tmp build directory by extracting the .orig.tar.gz
        os.chdir(tmpdir)
        self.logger.debug("Extracting %s..." % tarball)
        status = os.system('tar xzf %s' % tarball)
        if status:
            raise IOError('An error occured while extracting the upstream '\
                          'tarball (return status: %s)' % status)

        # origpath is depending of the upstream convention
        origpath = tarball.rsplit('.orig.tar.gz')[0].replace('_', '-')

        # copying debian_dir directory into tmp build depending of the target distribution
        # in all cases, we copy the debian directory of the sid version
        # DOC If a file should not be included, touch an empty file in the overlay directory
        export(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian'))
        if self.get_debian_dir() != 'debian/':
            self.logger.debug("Overriding files...")
            export(osp.join(self.config.pkg_dir, self.get_debian_dir()), osp.join(origpath, 'debian/'),
                   verbose=self.config.verbose)

        # build the package using vbuild or default to fakeroot
        debuilder = os.environ.get('DEBUILDER', 'vbuild')
        self.logger.debug("Use builder: '%s'" % debuilder)
        if debuilder ==  'vbuild':
            self.make_source_package(origpath)
            dscfile = '%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version())
            if osp.isfile(dscfile):
                self.logger.info("Building dsc file: %s" % dscfile)
            else:
                self.logger.critical("Cannot build valid dsc file '%s'" % dscfile)
                sys.exit(1)
            self.logger.info("Building debian package for distribution '%s' and arch '%s'"
                             % (distrib, arch))
            cmd = 'vbuild -d %s -a %s --result %s %s'
            cmd %= (distrib, arch, self.get_distrib_dir(), osp.join(tmpdir, dscfile))
            # TODO
            #cmd += ' --debbuildopts %s' % pdebuild_options
        else:
            cmd = debuilder
        stdout, stderr = None, None
        if not self.config.verbose:
            stdout = open(os.devnull,"w")
            stderr = open(os.devnull,"w")
        try:
            check_call(cmd.split(), stdout=stdout, stderr=stderr)
        except (OSError, CalledProcessError), err:
            self.logger.critical(err)
            sys.exit(cmd)

        # clean tmpdir
        if not self.config.keep_tmpdir:
            shutil.rmtree(tmpdir)
        return self.get_packages()

    def get_distrib_dir(self):
        """ get the dynamic target release directory """
        return osp.join(self.config.dist_dir, self.config.distrib)

    def make_source_package(self, origpath):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        self.logger.info("Creation of the debian source package in '%s'" % origpath)
        cmd = 'dpkg-source -b %s' % origpath
        if not self.config.verbose:
            cmd += ' 1>/dev/null 2>/dev/null'
        os.system(cmd)
