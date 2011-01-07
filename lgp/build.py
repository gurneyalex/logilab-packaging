# -*- coding: utf-8 -*-
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
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
""" lgp build [options] [project directory]

    Provides functions to build a debian package for a python package
    You can change options in /etc/lgp/lgprc inside the [LGP-BUILD] section
"""
__docformat__ = "restructuredtext en"

import os
import sys
import shutil
import logging
import hashlib
from glob import glob
import os.path as osp
from subprocess import check_call, CalledProcessError, Popen

from debian_bundle import deb822

from logilab.common.shellutils import cp

from logilab.devtools.lgp import CONFIG_FILE, HOOKS_DIR, BUILD_LOG_EXT
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp import utils
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

from logilab.devtools.lgp.check import check_debsign

def run(args):
    """main function of lgp build command"""
    builder = None
    try :
        builder = Builder(args)
        builder.clean_repository()

        # Stop to original pristine tarball creation if no distribution can be used
        if not len(builder.distributions):
            logging.warn("only original pristine tarball creation will be done")
            builder.config.get_orig_source = True

        # create the upstream tarball if necessary and move it to result directory
        builder.make_orig_tarball()

        while builder.distributions:
            builder.prepare_source_archive()

            # create a debian source package
            builder.make_debian_source_package()

            if builder.make_debian_binary_package():
                # do post-treatments only for a successful binary build
                if builder.packages and builder.config.post_treatments:
                    run_post_treatments(builder, builder.current_distrib)

            # forget distribution
            builder.distributions = builder.distributions[1:]

        # report files to the console
        if builder.packages:
            logging.info("recent files from build:\n* %s"
                         % '\n* '.join(sorted(set(builder.packages))))
    except KeyboardInterrupt:
        logging.warning('lgp aborted by keyboard interrupt')
    except LGPException, exc:
        if hasattr(builder, "config") and builder.config.verbose:
            import traceback
            logging.critical(traceback.format_exc())
        logging.critical(exc)
        return exc.exitcode()
    return builder.finalize()

def run_post_treatments(builder, distrib):
    """ Run actions after package compiling """
    distdir = builder.get_distrib_dir()
    old = os.getcwd()
    try:
        try:
            os.chdir(osp.dirname(distdir))
            # dpkg-scanpackages i386 /dev/null | gzip -9c > 386/Packages.gz
            # dpkg-scanpackages amd64 /dev/null | gzip -9c > amd64/Packages.gz
            # dpkg-scansources source /dev/null | gzip -9c > source/Sources.gz
            cmd = "dpkg-scanpackages -m %s /dev/null 2>/dev/null | gzip -9c > %s/Packages.gz"
            os.system(cmd % (distrib, distrib))
        except Exception, err:
            logging.warning("cannot update Debian trivial repository for '%s'" % distdir)
        else:
            logging.debug("Debian trivial repository in '%s' updated." % distdir)
    finally:
        os.chdir(old)


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
                 'help': "suffix to append to the Debian package. (default: current timestamp)\n"
                         "Tip: prepend by '~' for pre-release and '+' for post-release"
                }),
               ('keep-tmpdir',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "keep_tmpdir",
                 'help': "keep the temporary build directory"
                }),
               # should be a store_true action here
               ('post-treatments',
                {'type': 'string',
                 'default': '',
                 'dest' : "post_treatments",
                 'help': "run embedded post-treatments: add trivial repository"
                }),
               ('deb-src',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "deb_src_only",
                 'help': "obtain a debian source package without build"
                }),
               ('get-orig-source',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "get_orig_source",
                 'help': "create a reasonable upstream tarball"
                }),
               # should be a store_true action here
               ('hooks',
                {'type': 'string',
                 'default': '',
                 'dest' : "hooks",
                 'help': "run pbuilder hooks in '%s'" % HOOKS_DIR
                }),
               # should be a store_true action here
               ('sign',
                {'type': 'string',
                 'default': 'no',
                 'short': 's',
                 'dest' : "sign",
                 'help': "try to sign Debian package(s) just built"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Builder, self).__init__(arguments=args, options=self.options, usage=__doc__)
        if self.package_format == 'debian' and not osp.isdir('debian'):
            raise LGPException("You are not in a valid project root directory. Lgp expects debian directory from here.")

        # global build status
        self.build_status = os.EX_OK

        # list of all temporary directories
        self._tmpdirs = []

        # hotlist of the recent generated package files
        self.packages = []

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
            contents = [(t, os.listdir(t)) for t in self._tmpdirs]
            for t, c in contents:
                logging.warn("temporary directory not deleted: %s (%s)"
                             % (t, ", ".join(c)))

    def make_debian_source_package(self):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        See:

        - http://www.debian.org/doc/maint-guide/ch-build.en.html#s-option-sa

        :param:
            origpath: path to orig.tar.gz tarball
        """
        # change directory to build source package
        os.chdir(self._tmpdir)
        arguments = ""
        format = utils.guess_debian_source_format()
        logging.info("Debian source package format: %s" % format)
        if format == "1.0":
            arguments+='--no-copy'
        try:
            cmd = 'dpkg-source %s -b %s' % (arguments, self.origpath)
            logging.debug("running dpkg-source command: %s ..." % cmd)
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file with command %s" % cmd
            raise LGPCommandException(msg, err)

        # define dscfile ressource
        self.dscfile = glob(os.path.join(self._tmpdir, '*.dsc')).pop()
        assert osp.isfile(self.dscfile)
        msg = "create Debian source package files (.dsc, .diff.gz): %s"
        logging.info(msg % osp.basename(self.dscfile))

        # move Debian source package files and exit if asked by command-line
        if self.config.deb_src_only:
            self.move_package_files([self.dscfile], verbose=self.config.deb_src_only)
            self.finalize()

        # restore directory context
        os.chdir(self.config.pkg_dir)

    def _builder_command(self, build_vars):
        # TODO Manage DEB_BUILD_OPTIONS
        # http://www.debian.org/doc/debian-policy/ch-source.html
        debuilder = os.environ.get('DEBUILDER', 'pbuilder')
        logging.debug("package builder flavour: '%s'" % debuilder)
        if debuilder == 'pbuilder':
            assert osp.isfile(self.dscfile)
            # TODO encapsulate builder logic into specific InternalBuilder class
            cmd = ['sudo', 'IMAGE=%(image)s' % build_vars,
                   'DIST=%(distrib)s' % build_vars,
                   'ARCH=%(arch)s' % build_vars,
                   debuilder, 'build',
                   '--configfile', CONFIG_FILE,
                   '--buildresult', self._tmpdir]
            if self.config.verbose == 3: # i.e. -vvv in command line
                cmd.append('--debug')
            if build_vars["buildopts"]:
                cmd.extend(['--debbuildopts', "%(buildopts)s" % build_vars])
            if self.config.hooks != "no":
                cmd.extend(['--hookdir', HOOKS_DIR])
            cmd.append(self.dscfile)
        elif debuilder == 'debuild':
            os.chdir(self.origpath)
            cmd = ['debuild', '--no-tgz-check', '--no-lintian',
                   '--clear-hooks', '-uc', '-us']
        elif debuilder == 'fakeroot':
            os.chdir(self.origpath)
            cmd = ['fakeroot', 'debian/rules', 'binary']
        else:
            cmd = debuilder.split()
        return cmd

    def make_debian_binary_package(self):
        """create debian binary package(s)

        virtualize/parallelize the binary package build process
        This is a rudimentary multiprocess support for parallel build by architecture

        Display build log when verbose mode is greater or equal to 2 (-vv*)

        :todo: use multiprocessing module here (python 2.6)
        """
        stdout = {False: file(os.devnull, "w"), True: sys.stdout}
        stdout = stdout[self.config.verbose >= 2] # i.e. -vv* in command line
        joblist = []
        tmplist = []
        for build in self.use_build_series():
            # change directory context at each binary build
            tmplist.append(self.create_build_context())

            cmd = self._builder_command(build)
            # TODO manage handy --othermirror to use local mirror
            #cmd.append(['--othermirror', "deb file:///home/juj/dists %s/" % build['distrib']])
            logging.info("building binary debian package for '%s/%s' "
                         "using DEBBUILDOPTS options: '%s' ..."
                         % (build['distrib'], build['arch'],
                            build['buildopts'] or '(none)'))

            logging.debug("running build command: %s ..." % ' '.join(cmd))
            try:
                joblist.append(Popen(cmd,
                                     env={'DIST':  build['distrib'],
                                          'ARCH':  build['arch'],
                                          'IMAGE': build['image']},
                                     stdout=stdout))
            except Exception, err:
                logging.critical(err)
                logging.critical("build failure (%s/%s) for %s (%s)"
                                 % (build['distrib'],
                                    build['arch'],
                                    self.get_debian_name(),
                                    self.get_debian_version()))
                return False

        # only print dots in verbose mode (verbose: 1)
        build_status, timedelta = utils.wait_jobs(joblist, self.config.verbose == 1)
        if build_status:
            logging.critical("binary build(s) failed for '%s' with exit status %d"
                             % (build['distrib'], build_status))
        else:
            logging.info("binary build(s) for '%s' finished in %d seconds."
                         % (build['distrib'], timedelta))

        # move Debian binary package(s) files
        for tmp in tmplist:
            changes = glob(osp.join(tmp, '*.changes'))
            buildlog = glob(osp.join(tmp, '*' + BUILD_LOG_EXT))
            self.move_package_files(changes + buildlog)

        self.build_status += build_status
        return build_status == os.EX_OK

    def use_build_series(self):
        """create a series of binary build command

        Architecture is checked against the debian/control to detect
        architecture-independent packages

        You have the possiblity to add some dpkg-buildpackage options with the
        DEBBUILDOPTS environment variable.
        """
        assert self.current_distrib

        def _build_options(arch=None, rank=0):
            optline = list()
            #optline.append('-b')
            #if self.config.sign and check_debsign(self):
            #    optline.append('-pgpg')
            if arch:
                if rank:
                    optline.append('-B')
                optline.append('-a%s' % arch)
            if os.environ.get('DEBBUILDOPTS'):
                optline.append(os.environ.get('DEBBUILDOPTS'))
            return ' '.join(optline)

        series = []
        if utils.is_architecture_independent():
            options = dict()
            options['distrib'] = self.current_distrib
            options['buildopts'] = _build_options()
            options['arch'] = self.get_architectures(['current'])[0]
            options['image'] = self.get_basetgz(options['distrib'],
                                                options['arch'])
            series.append(options)
            logging.info('this build is arch-independent. Lgp will only build on '
                         'current architecture (%s)' % options['arch'])
        else:
            for rank, arch in enumerate(self.architectures):
                options = dict()
                options['distrib'] = self.current_distrib
                options['buildopts'] = _build_options(arch, rank)
                options['arch'] = arch
                options['image'] = self.get_basetgz(options['distrib'],
                                                    options['arch'])
                series.append(options)
        return series

    def move_package_files(self, filelist, verbose=True):
        """move package files from the temporary build area to the result directory

        we define here the self.packages variable used by post-treatment
        some tests are performed before copying to result directory

        :see: dcmd command
        :todo: add more checks: sizes, checksums, etc... (ex: _check_file)
        :todo: support other source package formats
        :todo: define API and/or integrate software (dput, curl, scp) ?
        """
        assert isinstance(filelist, list), "must be a list to be able to extend"

        def _sign_file(filename):
            if self.config.sign and self.config.sign.lower() == "yes":
                check_debsign(self)
                try:
                    check_call(["debsign", filename], stdout=sys.stdout)
                except CalledProcessError, err:
                    logging.error("lgp cannot debsign '%s' automatically" % filename)
                    logging.error("You have to run manually: debsign %s"
                                  % copied_filename)

        def _check_file(filename):
            if os.path.isfile(filename):
                hash1 = hashlib.md5(open(fullpath).read()).hexdigest()
                hash2 = hashlib.md5(open(filename).read()).hexdigest()
                if hash1 == hash2:
                    logging.debug("overwrite same file file '%s'" % filename)
                else:
                    logging.warn("theses files shouldn't be different:\n- %s (%s)\n- %s (%s)"
                                 % (fullpath, hash1, filename, hash2))
                    os.system('diff -u %s %s' % (fullpath, filename))
                    raise LGPException("bad md5 sums of source archives (tarball)")

        def _check_pristine():
            """basic check about presence of pristine tarball in source package

            Format: 1.0
            A source package in this format consists either of a .orig.tar.gz
            associated to a .diff.gz or a single .tar.gz (in that case the pack-
            age is said to be native).

            A source package contains at least an original tarball
            (.orig.tar.ext where ext can be gz, bz2 and lzma)
            """
            ext = tuple([".tar" + e for e in ('.gz', '.bz2', '.lzma')])
            pristine = diff = None
            for entry in filelist:
                if not diff and entry.endswith('.diff.gz'):
                    diff = entry
                if not pristine and entry.endswith(tuple(ext)):
                    pristine = entry
            if pristine is None and self.is_initial_debian_revision():
                logging.error("no pristine tarball found for initial Debian revision (searched: %s)"
                              % (entry, ext))
            orig = pristine.rsplit('.', 2)[0].endswith(".orig")
            if not diff and not orig:
                msg = ("native package detected. Read `man dpkg-source` "
                       "carefully if not sure")
                logging.warn(msg)

        while filelist:
            fullpath = filelist.pop()
            path, filename = osp.split(fullpath)
            assert os.path.isfile(fullpath), "%s not found!" % fullpath
            copied_filename = os.path.join(self.get_distrib_dir(),
                                           osp.basename(filename))

            if filename.endswith(('.changes', '.dsc')):
                contents = deb822.Deb822(file(fullpath))
                filelist.extend([osp.join(path, f.split()[-1])
                                 for f in contents['Files'].split('\n')
                                 if f])
            #logging.debug('copying: %s -> %s ... \npending: %s' % (filename, copied_filename, filelist))

            if filename.endswith('.dsc'):
                #_check_file(copied_filename)
                _check_pristine()
                if self.config.deb_src_only:
                    logging.info("Debian source control file: %s"
                                 % copied_filename)
                    _sign_file(fullpath)
            if filename.endswith('.orig.tar.gz'):
                if self.config.get_orig_source:
                    logging.info('a new original source archive (tarball) '
                                 'is available: %s' % copied_filename)
            if filename.endswith(BUILD_LOG_EXT):
                logging.info("a build logfile is available: %s" % copied_filename)
            if filename.endswith('.changes'):
                logging.info("Debian changes file: %s" % copied_filename)
                #_check_file(copied_filename)
                _sign_file(fullpath)
            #if filename.endswith('.diff.gz'):
            #    _check_file(copied_filename)

            cp(fullpath, copied_filename)
            assert osp.exists(copied_filename)
            self.packages.append(copied_filename)

    def get_distrib_dir(self):
        """get the dynamic target release directory"""
        distrib_dir = os.path.normpath(os.path.expanduser(self.config.dist_dir))
        # special case when current directory is used to put result files ("-r .")
        if distrib_dir not in ['.', '..']:
            distrib_dir = os.path.join(distrib_dir, self.current_distrib)
        # check if distribution directory exists, create it if necessary
        os.umask(0002)
        try:
            os.makedirs(distrib_dir, 0755)
        except OSError:
            # it's not a problem here to pass silently # when the directory
            # already exists
            pass
        return distrib_dir
