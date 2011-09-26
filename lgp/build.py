# -*- coding: utf-8 -*-
#
# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.

import os
import sys
import shutil
import hashlib
import errno
from glob import glob
import os.path as osp
from subprocess import check_call, CalledProcessError, Popen

from debian import deb822

from logilab.common.shellutils import cp

from logilab.devtools.lgp import LGP, CONFIG_FILE, HOOKS_DIR, utils
from logilab.devtools.lgp.exceptions import (LGPException, LGPCommandException)
from logilab.devtools.lgp.utils import tempdir

from logilab.devtools.lgp.check import check_debsign
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.clean import Cleaner


@LGP.register
class Builder(SetupInfo):
    """Build a debian package.

    You can change options in /etc/lgp/lgprc inside the [BUILD] section
    """
    name = "build"
    options = SetupInfo.options + [
               ('result',
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
                 'help': "URI to orig.tar.gz file",
                 'group': 'Pristine'
                }),
               ('suffix',
                {'type': 'string',
                 'dest': 'suffix',
                 'metavar' : "<suffix>",
                 'help': "suffix to append to the Debian package version. (default: current timestamp)\n"
                         "Tip: prepend by '~' for pre-release and '+' for post-release",
                 'group': 'Debian'
                }),
               ('keep-tmpdir',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "keep_tmpdir",
                 'help': "keep the temporary build directory",
                 'group': 'Debug'
                }),
               ('deb-src',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "deb_src_only",
                 'help': "obtain a debian source package without build",
                 'group': 'Debian'
                }),
               ('hooks',
                {'type': 'string',
                 'default': '', # check if new HOOKS_DIR
                 'dest' : "hooks",
                 'help': "run pbuilder hooks in '%s'" % HOOKS_DIR,
                 'group': 'Pbuilder'
                }),
               # use yes/no types here to configure globally
               ('sign',
                {'type': 'yn',
                 'default': False,
                 'short': 's',
                 'dest' : "sign",
                 'metavar' : '<yes|no>',
                 'help': "try to sign Debian package(s) just built",
                 'group': 'Debian'
                }),
               ('post-treatments',
                {'type': 'yn',
                 'default': False,
                 'dest' : "post_treatments",
                 'help': "run embedded post-treatments: add trivial repository",
                 'group': 'Debian'
                }),
              ]

    # global build status
    build_status = os.EX_OK

    # list of all temporary directories
    _tmpdirs = []

    # hotlist of the recent generated package files
    packages = []

    def _prune_pkg_dir(self):
        super(Builder, self)._prune_pkg_dir()
        if self.package_format == 'debian' and not osp.isdir('debian'):
            msg = ("You are not in a valid project root directory. "
                   "Lgp expects a Debian directory here.")
            raise LGPException(msg)

    def clean_tmpdirs(self):
        if not self.config.keep_tmpdir:
            if hasattr(self, '_tmpdirs'):
                for tmpdir in self._tmpdirs:
                    try:
                        shutil.rmtree(tmpdir)
                    except OSError, exc:
                        self.logger.error("cannot remove '%s' (%s)"
                                          % (tmpdir, exc))
        else:
            contents = [(t, os.listdir(t)) for t in self._tmpdirs]
            for t, c in contents:
                self.logger.warn("temporary directory not deleted: %s (%s)"
                                 % (t, ", ".join(c)))

    def run(self, args):
        Cleaner(config=self.config).run(args)
        # create the upstream tarball if necessary and move it to result directory
        with tempdir(self.config.keep_tmpdir) as tmpdir:
            self.make_orig_tarball(tmpdir)

            try:
                for distrib in  self.distributions:
                    with tempdir(self.config.keep_tmpdir) as dsc_tmpdir:
                        # create a debian source package
                        dscfile = self.make_debian_source_package(distrib, dsc_tmpdir)
                        if self.make_debian_binary_package(distrib, dscfile):
                            # do post-treatments only for a successful binary build
                            if self.packages and self.config.post_treatments:
                                self.run_post_treatments(distrib)
                # report files to the console
                if self.packages:
                    self.logger.info("recent files from build:\n* %s"
                                     % '\n* '.join(sorted(set(self.packages))))
            except LGPException, exc:
                # XXX refactor ? if getattr(self.config, "verbose"):
                if hasattr(self, "config") and self.config.verbose:
                    import traceback
                    self.logger.critical(traceback.format_exc())
                raise exc
            finally:
                self.destroy_tmp_context()
            return self.build_status

    def make_orig_tarball(self, tmpdir="."):
        """make upstream pristine tarballs (Debian way)

        Create the tarball from working directory for the initial revision.
        For later ones call uscan to download the source tarball by looking at
        debian/watch (if the tarball wasn't passed on the command line).

        Finally copy pristine tarball with expected Debian filename convention.

        This method is responsible for setting config.orig_tarball to its right
        location.

        .. see::
            http://www.debian.org/doc/debian-policy/ch-source.html
        """
        self._check_version_mismatch()
        if self.config.orig_tarball and self.is_initial_debian_revision():
            self.logger.error("you are passing a pristine tarball in command "
                              "line for an initial Debian revision")

        fileparts = (self.get_upstream_name(), self.get_upstream_version())
        # note: tarball format can be guaranteed by uscan's repack option
        tarball = '%s_%s.orig.tar.gz' % fileparts
        upstream_tarball = '%s-%s.tar.gz' % fileparts

        # run uscan to download the source tarball by looking at debian/watch
        if self.config.orig_tarball is None and not self.is_initial_debian_revision():
            self.logger.info('running uscan to download the source tarball by '
                             'looking at debian/watch')
            try:
                check_call(["uscan", "--noconf", "--download-current-version",
                            "--rename", "--destdir", tmpdir])
            except CalledProcessError, err:
                debian_name     = self.get_debian_name()
                debian_revision = self.get_debian_version().rsplit('-', 1)[1]
                self.logger.error("Debian source archive (pristine tarball) is required when you "
                                  "don't build the first revision of a debian package "
                                  "(use '--orig-tarball' option)")
                self.logger.info("If you haven't the original tarball version, you could run: "
                                 "'apt-get source --tar-only %s'" % debian_name)
                msg = ('unable to build upstream tarball of %s package for '
                       'Debian revision "%s"' % (debian_name, debian_revision))
                raise LGPCommandException(msg, err)
            else:
                self.config.orig_tarball = tarball

        # create new pristine tarball from working directory if initial revision
        if self.config.orig_tarball is None and self.is_initial_debian_revision():
            self.logger.info("create pristine tarball from working directory")
            try:
                self._run_command("sdist", dist_dir=tmpdir)
            except CalledProcessError, err:
                self.logger.error("creation of the source archive failed")
                self.logger.error("check if the version '%s' is really tagged in "
                                  "your repository" % self.get_upstream_version())
                raise LGPCommandException("source distribution wasn't properly built", err)
            else:
                self.config.orig_tarball = osp.join(tmpdir, upstream_tarball)

        if not os.path.basename(self.config.orig_tarball).startswith(self.get_upstream_name()):
            msg = "pristine tarball filename doesn't start with upstream name '%s'. really suspect..."
            self.logger.error(msg % self.get_upstream_name())

        # copy pristine tarball with the expected Debian filename convention
        tarball = osp.abspath(osp.join(tmpdir, tarball))
        try:
            if not osp.exists(tarball):
                shutil.copy(self.config.orig_tarball, tarball)
        except EnvironmentError, err:
            self.logger.critical("pristine tarball can't be copied from given location: %s"
                                 % self.config.orig_tarball)
            raise LGPException(err)
        else:
            self.config.orig_tarball = tarball
        return self.config.orig_tarball

    def make_debian_source_package(self, current_distrib, tmpdir='.'):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        See:

        - http://www.debian.org/doc/maint-guide/ch-build.en.html#s-option-sa

        :param:
            origpath: path to orig.tar.gz tarball
        """
        self.prepare_source_archive(tmpdir, current_distrib)

        arguments = ""
        format = utils.guess_debian_source_format()
        os.chdir(tmpdir)
        if format == "1.0":
            arguments+='--no-copy'
        self.logger.info("Debian source package (format: %s) for '%s'" % (format, current_distrib))
        # change directory to build source package
        try:
            cmd = 'dpkg-source %s -b %s' % (arguments, self.origpath)
            self.logger.debug("running dpkg-source command: %s ..." % cmd)
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            msg = "cannot build valid dsc file with command %s" % cmd
            raise LGPCommandException(msg, err)
        dscfile = osp.abspath(glob('*.dsc').pop())
        assert osp.isfile(dscfile)
        msg = "create Debian source package files (.dsc, .diff.gz): %s"
        self.logger.info(msg % osp.basename(dscfile))
        # move Debian source package files and exit if asked by command-line
        if self.config.deb_src_only:
            resultdir = self.get_distrib_dir(current_distrib)
            self.move_package_files([self.dscfile], resultdir, verbose=self.config.deb_src_only)
            return self.destroy_tmp_context()
        # restore directory context
        os.chdir(self.config.pkg_dir)
        return dscfile

    def _builder_command(self, build_vars, dscfile):
        # TODO Manage DEB_BUILD_OPTIONS
        # http://www.debian.org/doc/debian-policy/ch-source.html
        debuilder = os.environ.get('DEBUILDER', 'pbuilder')
        self.logger.debug("package builder flavour: '%s'" % debuilder)
        if debuilder == 'pbuilder':
            assert osp.isfile(dscfile)
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
            cmd.append(dscfile)
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

    def make_debian_binary_package(self, distrib, dscfile):
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
        resultdir = self.get_distrib_dir(distrib)

        for build in self.use_build_series(distrib):
            # change directory context at each binary build
            tmplist.append(self.create_tmp_context())

            cmd = self._builder_command(build, dscfile)
            # TODO manage handy --othermirror to use local mirror
            #cmd.append(['--othermirror', "deb file:///home/juj/dists %s/" % build['distrib']])
            self.logger.info("building binary debian package for '%s/%s' "
                             "using DEBBUILDOPTS options: '%s' ..."
                             % (build['distrib'], build['arch'],
                                build['buildopts'] or '(none)'))

            self.logger.debug("running build command: %s ..." % ' '.join(cmd))
            try:
                joblist.append(Popen(cmd,
                                     env={'DIST':  build['distrib'],
                                          'ARCH':  build['arch'],
                                          'IMAGE': build['image']},
                                     stdout=stdout))
            except Exception, err:
                self.logger.critical(err)
                self.logger.critical("build failure (%s/%s) for %s (%s)"
                                     % (build['distrib'],
                                        build['arch'],
                                        self.get_debian_name(),
                                        self.get_debian_version()))
                return False

        # only print dots in verbose mode (verbose: 1)
        build_status, timedelta = utils.wait_jobs(joblist, self.config.verbose == 1)
        if build_status:
            self.logger.critical("binary build(s) failed for '%s' with exit status %d"
                                 % (build['distrib'], build_status))
        else:
            self.logger.info("binary build(s) for '%s' finished in %d seconds."
                             % (build['distrib'], timedelta))

        # move Debian binary package(s) files
        for tmp in tmplist:
            changes = glob(osp.join(tmp, '*.changes'))
            buildlog = glob(osp.join(tmp, '*.log'))
            self.move_package_files(changes + buildlog, resultdir)

        self.build_status += build_status
        return build_status == os.EX_OK

    def use_build_series(self, distrib):
        """create a series of binary build command

        Architecture is checked against the debian/control to detect
        architecture-independent packages

        You have the possiblity to add some dpkg-buildpackage options with the
        DEBBUILDOPTS environment variable.
        """
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
            # XXX not supported by lenny's dpkg (added in 1.15.6)
            #optline.append('--changes-option=-DDistribution=%s' % distrib)
            return ' '.join(optline)

        series = []
        if utils.is_architecture_independent():
            options = dict()
            options['distrib'] = distrib
            options['buildopts'] = _build_options()
            options['arch'] = (self.config.archi or self.get_architectures(['current']))[0]
            options['image'] = self.get_basetgz(options['distrib'],
                                                options['arch'])
            series.append(options)
            self.logger.info('this build is arch-independent. Lgp will only build on '
                             'architecture %s' % options['arch'])
        else:
            for rank, arch in enumerate(self.get_architectures()):
                options = dict()
                options['distrib'] = distrib
                options['buildopts'] = _build_options(arch, rank)
                options['arch'] = arch
                options['image'] = self.get_basetgz(options['distrib'],
                                                    options['arch'])
                series.append(options)
        return series

    def move_package_files(self, filelist, resultdir, verbose=True):
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
            if self.config.sign:
                check_debsign(self)
                try:
                    check_call(["debsign", filename], stdout=sys.stdout)
                except CalledProcessError, err:
                    self.logger.error("lgp cannot debsign '%s' automatically" % filename)
                    self.logger.error("You have to run manually: debsign %s"
                                      % copied_filename)

        def _check_file(filename):
            if os.path.isfile(filename):
                hash1 = hashlib.md5(open(fullpath).read()).hexdigest()
                hash2 = hashlib.md5(open(filename).read()).hexdigest()
                if hash1 == hash2:
                    self.logger.debug("overwrite same file file '%s'" % filename)
                else:
                    self.logger.warn("theses files shouldn't be different:\n- %s (%s)\n- %s (%s)"
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
            (.orig.tar.ext where ext can be gz, bz2 and xz)
            """
            ext = tuple([".tar" + e for e in ('.gz', '.bz2', '.xz')])
            pristine = diff = None
            for entry in filelist:
                if not diff and entry.endswith('.diff.gz'):
                    diff = entry
                if not pristine and entry.endswith(ext):
                    pristine = entry
            if pristine is None and self.is_initial_debian_revision():
                self.logger.error("no pristine tarball found for initial Debian revision (searched: %s)"
                                  % (entry, ext))
            orig = pristine.rsplit('.', 2)[0].endswith(".orig")
            if not diff and not orig:
                msg = ("native package detected. Read `man dpkg-source` "
                       "carefully if not sure")
                self.logger.warn(msg)

        while filelist:
            fullpath = filelist.pop()
            path, filename = osp.split(fullpath)
            assert os.path.isfile(fullpath), "%s not found!" % fullpath
            copied_filename = os.path.join(resultdir, osp.basename(filename))

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
                    self.logger.info("Debian source control file: %s"
                                     % copied_filename)
                    _sign_file(fullpath)
            if filename.endswith('.log'):
                self.logger.info("a build logfile is available: %s" % copied_filename)
            if filename.endswith('.changes'):
                self.logger.info("Debian changes file: %s" % copied_filename)
                #_check_file(copied_filename)
                _sign_file(fullpath)
            #if filename.endswith('.diff.gz'):
            #    _check_file(copied_filename)

            cp(fullpath, copied_filename)
            assert osp.exists(copied_filename)
            self.packages.append(copied_filename)

    def guess_environment(self):
        # normalize pathnames given in parameters
        self.config.orig_tarball = self._normpath(self.config.orig_tarball)

        if self.config.orig_tarball:
            self.logger.info('use original source archive (tarball): %s',
                             self.config.orig_tarball)

        # if no default value for distribution, use list from existing images
        if self.config.distrib is None:
            self.config.distrib = 'all'
        super(Builder, self).guess_environment()

    def run_post_treatments(self, distrib):
        """ Run actions after package compiling """
        # dpkg-scanpackages i386 /dev/null | gzip -9c > 386/Packages.gz
        # dpkg-scanpackages amd64 /dev/null | gzip -9c > amd64/Packages.gz
        # dpkg-scansources source /dev/null | gzip -9c > source/Sources.gz
        resultdir = self.get_distrib_dir(distrib)
        packages_file = osp.join(resultdir, "Packages.gz")
        try:
            cmd = "cd %s && dpkg-scanpackages -m %s /dev/null 2>/dev/null | gzip -9c > %s"
            os.system(cmd % (osp.dirname(resultdir), distrib,
                             packages_file))
        except Exception, err:
            self.logger.warning("cannot update Debian trivial repository for '%s'"
                                % resultdir)
        else:
            self.logger.debug("Debian trivial repository in '%s' updated."
                              % packages_file)
