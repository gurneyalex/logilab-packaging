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
    You can change options in /etc/lgp/lgprc inside the [LGP-BUILD] section
"""
__docformat__ = "restructuredtext en"

import os
import sys
import shutil
import logging
import warnings
import hashlib
import os.path as osp
from subprocess import check_call, CalledProcessError, Popen

from debian_bundle import deb822

from logilab.common.shellutils import mv

from logilab.devtools.lgp import CONFIG_FILE, HOOKS_DIR
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import cond_exec, wait_jobs
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

from logilab.devtools.lgp.check import Checker, check_debsign

def run(args):
    """main function of lgp build command"""
    builder = None
    try :
        builder = Builder(args)
        builder.clean_repository()

        # create the upstream tarball if necessary and move it to result directory
        builder.make_orig_tarball()

        while builder.distributions:
            builder.prepare_source_archive()

            # create a debian source package
            builder.make_debian_source_package()

            if builder.make_debian_binary_package():
                # do post-treatment only for sucessful binary build
                if not builder.config.no_treatment and builder.packages:
                    run_post_treatments(builder, builder.current_distrib)

            # forget distribution
            builder.distributions = builder.distributions[1:]
    except KeyboardInterrupt:
        logging.warning('lgp aborted by keyboard interrupt')
    except LGPException, exc:
        if hasattr(builder, "config") and builder.config.verbose:
            import traceback
            logging.critical(traceback.format_exc())
        logging.critical(exc)
        return 1
    return builder.finalize()

def run_post_treatments(builder, distrib):
    """ Run actions after package compiling """
    distdir = builder.get_distrib_dir()
    verbose = builder.config.verbose

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
    command = "dpkg-scanpackages -m %s /dev/null 2>/dev/null | gzip -9c > %s/Packages.gz"\
              % (distrib, distrib)
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
                 'help': "URI to orig.tar.gz file"
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

        # global build status (for every build)
        self.build_status = os.EX_OK

        # list of all temporary directories
        self._tmpdirs = []

        # hotlist of the recent generated package files
        self.packages = []

        # TODO make a more readable logic in OptParser values
        if not self.config.post_treatments:
            warnings.warn("Option post-treatment is deprecated. Use no-treatment instead.", DeprecationWarning)
            self.config.no_treatment = True

    def clean_tmpdirs(self):
        if not self.config.keep_tmpdir:
            if hasattr(self, '_tmpdirs'):
                for tmpdir in self._tmpdirs:
                    try:
                        shutil.rmtree(tmpdir)
                    except OSError, exc:
                        logging.error("cannot remove '%s' (%s)"
                                      % (tmpdir, exc))
        else:
            logging.warn("keep temporary directory '%s' for further investigation"
                         % ",".join(self._tmpdirs))

    def make_debian_source_package(self):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        # change directory context
        os.chdir(self._tmpdir)

        logging.info("creation of the Debian source package files (.dsc, .diff.gz)")
        try:
            cmd = 'dpkg-source --no-copy -sp -b %s' % self.origpath
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file with command %s" % cmd
            raise LGPCommandException(msg, err)

        # move Debian source package files
        self.move_package_files(verbose=self.config.deb_src_only)

        # exit if asked by command-line
        if self.config.deb_src_only:
            self.finalize()

        # restore directory context
        os.chdir(self.config.pkg_dir)

    def _builder_command(self, build_vars):
        debuilder = os.environ.get('DEBUILDER', 'pbuilder')
        logging.debug("package builder flavour: '%s'" % debuilder)
        if debuilder == 'pbuilder':
            cmd = ['sudo', 'IMAGE=%(image)s' % build_vars,
                   'DIST=%(distrib)s' % build_vars,
                   'ARCH=%(arch)s' % build_vars,
                   debuilder, 'build',
                   '--configfile', CONFIG_FILE,
                   '--buildresult', self._tmpdir,
                   '--debbuildopts', "%(buildopts)s" % build_vars,
                   '--hookdir', HOOKS_DIR, self.dscfile]
        elif debuilder == 'debuild':
            os.chdir(self.origpath)
            cmd = ['debuild', '--no-tgz-check', '--no-lintian',
                   '--clear-hooks', '-uc', '-us']
        elif debuilder == 'fakeroot':
            os.chdir(self.origpath)
            cmd = ['fakeroot', 'debian/rules binary']
        else:
            cmd = debuilder.split()
        return cmd

    def make_debian_binary_package(self):
        """create debian binary package(s)

        virtualize/parallelize the binary package build process
        This is a rudimentary multiprocess support for parallel build by architecture
        Just waiting standard multiprocess module in python 2.6
        """
        joblist = []
        for build in self.use_build_series():
            cmd = self._builder_command(build)
            logging.info("building binary debian package for '%s/%s' "
                         "using build options '%s' ..."
                         % (build['distrib'], build['arch'], build['buildopts']))

            logging.debug("running build command: %s ..." % ' '.join(cmd))
            try:
                joblist.append(Popen(cmd,
                                     env={'DIST':  build['distrib'],
                                          'ARCH':  build['arch'],
                                          'IMAGE': build['image']},
                                     stdout=file(os.devnull, "w")))
            except Exception, err:
                #self.keep_tmpdir = True
                logging.crirical(err)
                logging.critical("build failure (%s/%s) for %s (%s)"
                                 % (build['distrib'],
                                    build['arch'],
                                    self.get_debian_name(),
                                    self.get_debian_version()))
                return False

        build_status, timedelta = wait_jobs(joblist)
        logging.info("binary builds for '%s' finished in %d seconds with global exit status %d"
                     % (build['distrib'], timedelta, build_status))

        # move Debian binary package files
        self.move_package_files()

        self.build_status += build_status
        return build_status == os.EX_OK

    def use_build_series(self):
        """create a series of binary build command

        Architecture is checked against the debian/control to detect
        architecture-independant packages

        You have the possiblity to add some dpkg-buildpackage options with the
        DEBBUILDOPTS environment variable.
        """
        def _build_options(arch=None):
            optline = list()
            optline.append('-b')
            if arch:
                optline.append('-B')
                optline.append('-a%s' % arch)
            else:
                optline.append('-A')
            if os.environ.get('DEBBUILDOPTS'):
                optline.append(os.environ.get('DEBBUILDOPTS'))
            return ' '.join(optline)

        series = []
        if self.is_architecture_independant():
            options = dict()
            options['distrib'] = self.current_distrib
            options['buildopts'] = _build_options()
            options['arch'] = self.get_architectures(['current'])[0]
            options['image'] = self.get_basetgz(options['distrib'],
                                                options['arch'])
            series.append(options)
            logging.info('this build is arch-independant. Lgp will only build on '
                         'current architecture (%s)' % options['arch'])
        else:
            for arch in self.architectures:
                options = dict()
                options['distrib'] = self.current_distrib
                options['buildopts'] = _build_options(arch)
                options['arch'] = arch
                options['image'] = self.get_basetgz(options['distrib'],
                                                    options['arch'])
                series.append(options)
        return series


    def move_package_files(self, verbose=True):
        """move package files from the temporary build area to the result directory

        we define here the self.packages variable used by post-treatment
        some tests are performed before copying to result directory
        """
        def check_file(filename):
            if os.path.isfile(filename):
                hash1 = hashlib.md5(open(fullpath).read()).hexdigest()
                hash2 = hashlib.md5(open(filename).read()).hexdigest()
                if hash1 == hash2:
                    logging.debug("overwrite same file file '%s'" % filename)
                else:
                    logging.warn("theses files shouldn't be different:\n- %s (%s)\n- %s (%s)"
                                 % (fullpath, hash1, filename, hash2))
                    os.system('diff -u %s %s' % (fullpath, filename))
                    #raise LGPException("bad md5 sums of source archives (tarball)")

        self.packages = []
        distdir = self.get_distrib_dir()
        for filename in os.listdir(self._tmpdir):
            fullpath = os.path.join(self._tmpdir, filename)
            if os.path.isfile(fullpath):
                copied_filename = os.path.join(distdir, filename)
                self.packages.append(copied_filename)
                if filename.endswith('.dsc'):
                    self.dscfile = copied_filename
                    dsc = deb822.Dsc(file(fullpath))
                    orig = None
                    for entry in dsc['Files']:
                        if entry['name'].endswith('orig.tar.gz'):
                            orig = entry
                            break
                    # there is no orig.tar.gz file in the dsc file
                    if orig is None and self.is_initial_debian_revision():
                        logging.error("no orig.tar.gz file found in %s (few chances "
                                      "to be a real native package)"
                                      % self.dscfile)
                    #check_file(copied_filename)
                    if self.config.deb_src_only:
                        logging.info("Debian source control file is: %s"
                                     % copied_filename)
                #if filename.endswith('.diff.gz'):
                #    check_file(copied_filename)
                if filename.endswith('.orig.tar.gz'):
                    # always reuse previous copied tarball as pointer
                    # thus we are sure to have a local file at the end
                    self.config.orig_tarball = copied_filename
                    #check_file(copied_filename)
                    if self.config.get_orig_source:
                        logging.info('a new original source archive (tarball) '
                                     'is available: %s' % copied_filename)
                if filename.endswith('.lgp-build'):
                    logging.info("a build logfile is available: %s" % copied_filename)
                if filename.endswith('.changes'):
                    logging.info("Debian changes file is: %s" % copied_filename)

                mv(fullpath, distdir)
                assert osp.exists(copied_filename)

        # lastly print changes file to the console
        if verbose:
            logging.info("recent generated files:\n* %s"
                         % '\n* '.join(sorted(self.packages)))

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

    def finalize(self):
        self.clean_tmpdirs()
        sys.exit(self.build_status)
