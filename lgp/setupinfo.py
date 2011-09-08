# -*- coding: utf-8 -*-
#
# Copyright (c) 2008-2011 Logilab (contact@logilab.fr)
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
"""generic package information container
"""

import errno
import sys
import os
import stat
import os.path as osp
import logging
import time
import tempfile
from string import Template
from distutils.core import run_setup
#from pkg_resources import FileMetadata
from subprocess import Popen, PIPE
from subprocess import check_call, CalledProcessError

from logilab.common import clcommands
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp
from logilab.common.fileutils import export
from logilab.common.decorators import cached

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lgp import LOG_FORMAT, utils
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

COMMANDS = {
        "sdist" : {
            "file": '$setup dist-gzip -e DIST_DIR=$dist_dir',
            "Distribution": 'python setup.py -q sdist -d $dist_dir',
            "PackageInfo": 'python setup.py -q sdist -d $dist_dir',
            "debian": "uscan --noconf --download-current-version --destdir $dist_dir",
        },
        "clean" : {
            "file": '$setup clean',
            "Distribution": 'python setup.py clean --all',
            "PackageInfo": 'python setup.py clean --all',
            "debian": "fakeroot debian/rules clean",
        },
        "version" : {
            "file": '$setup version',
            "Distribution": 'python setup.py --version',
            "PackageInfo": 'python setup.py --version',
            "debian": utils._parse_deb_version,
        },
        "project" : {
            "file": '$setup project',
            "Distribution": 'python setup.py --name',
            "PackageInfo": 'python setup.py --name',
            "debian": utils._parse_deb_project,
        },
}

class SetupInfo(clcommands.Command):
    """ a setup class to handle several package setup information """
    arguments = "[project directory]"
    # theses options can be imported separately (not always used)
    options = [('distrib',
                {'type': 'csv',
                 'dest': 'distrib',
                 'short': 'd',
                 'metavar': "<distribution>",
                 'help': "list of Debian distributions (from images created by setup). "
                 "Use 'all' for running all detected images or 'changelog' "
                 "for the value found in debian/changelog",
                 'group': 'Default',
                }),
               ('arch',
                {'type': 'csv',
                 'dest': 'archi',
                 'short': 'a',
                 'metavar' : "<architecture>",
                 'help': ("build for the requested debian architectures only "
                          "(automatic detection otherwise)"),
                 'group': 'Default',
                }),
               ('basetgz',
                {'type': 'string',
                 'hide': True,
                 'default': '/var/cache/lgp/buildd',
                 'dest': "basetgz",
                 'metavar' : "<pbuilder basetgz location>",
                 'help': "specifies the location of base.tgz used by pbuilder",
                 'group': 'Pbuilder',
                }),
              ]

    def __init__(self, logger=None, config=None):
        self.isatty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        options = [('dump-config',
                    {'action': 'store_true',
                     'hide': True,
                     'dest': "dump_config",
                     'help': "dump lgp configuration (debugging purpose)",
                     'group': 'Debug'
                    }),
                   # Internal lgp structures
                   ('setup-file',
                    {'type': 'string',
                     'dest': 'setup_file',
                     'default': '',
                     'metavar': "<setup file name>",
                     'help': "use an alternate setup file with Lgp expected targets",
                     'group': 'Expert',
                    }),
                   # Logging facilities
                   ('verbose',
                    {'action': 'count',
                     'dest' : "verbose",
                     'short': 'v',
                     'help': "run in verbose mode",
                     'group': 'Logging',
                    }),
                   ('no-color',
                    {'action': 'store_true',
                     'default': False,
                     'dest': "no_color",
                     'help': "print log messages without color",
                     'group': 'Logging',
                    }),
                   ('quiet',
                    {'action': 'count',
                     'dest' : "quiet",
                     'short': 'q',
                     'help': "disable info message log level",
                     'group': 'Logging',
                    }),
                  ]
        # merge parent options without modifying the class attribute
        self.options = self.options + options
        logger = logging.getLogger(self.name)
        super(SetupInfo, self).__init__(logger)
        self.config.pkg_dir = None
        self.config._package = None
        if config:
            self.config._update(vars(config), mode="careful")

    def main_run(self, arguments, rcfile):
        # Load the global settings for lgp
        if osp.isfile(rcfile):
            self.load_file_configuration(rcfile)

        # Manage arguments (project path essentialy)
        arguments = self.load_command_line_configuration(arguments)

        if self.config.dump_config:
            self.generate_config()
            return os.EX_OK

        # Set verbose level and output streams
        if self.config.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        elif self.config.quiet:
            logging.getLogger().setLevel(logging.WARN)
        else:
            # Redirect subprocesses stdout output only in case of verbose mode
            # We always allow subprocesses to print on the stderr (more convenient)
            sys.stdout = open(os.devnull,"w")
            #sys.stderr = open(os.devnull,"w")
        if self.isatty and not getattr(self.config, "no_color", None):
            # FIXME when using logging.conf
            handlers = logging.getLogger().handlers
            assert len(handlers)==1, "Lgp cannot manage several handlers..."
            console = logging.getLogger().handlers[0]
            console.setFormatter(ColorFormatter(LOG_FORMAT))

        self.check_args(arguments)
        self.go_into_package_dir(arguments)
        self._set_package_format()
        self.guess_environment()
        # Some package formats expect a clean state with no troubling file
        # (ex: distutils)...
        self._prune_pkg_dir()
        self.run(arguments)
        return os.EX_OK

    def check_args(self, args):
        super(SetupInfo, self).check_args(args)
        # just a warning issuing for possibly confused configuration
        if self.config.archi and 'all' in self.config.archi:
            self.logger.warn('the "all" keyword can be confusing about the '
                             'targeted architectures. Consider using the "any" keyword '
                             'to force the build on all architectures or let lgp finds '
                             'the value in debian/control by itself in doubt.')
            self.logger.warn('lgp replaces the "all" architecture value by "current" in the build')

    def go_into_package_dir(self, arguments):
        """go into package directory

        .. note::
            current directory wil be saved in `old_current_directory`
        """
        self.old_current_directory = os.getcwd() # use for relative filename in parameters
        if arguments:
            if os.path.exists(arguments[0]):
                self.config.pkg_dir = osp.abspath(arguments[0])
            else:
                raise LGPException("project directory doesn't exist: %s" % arguments[0])
            if os.path.isfile(self.config.pkg_dir):
                self.config.pkg_dir = os.path.dirname(self.config.pkg_dir)
            os.chdir(self.config.pkg_dir)
            self.logger.debug('change the current working directory to: %s' % self.config.pkg_dir)
        else:
            self.config.pkg_dir = self.old_current_directory

    def guess_environment(self):
        # define mandatory attributes for lgp commands
        self.distributions = utils.get_distributions(self.config.distrib,
                                                     self.config.basetgz)
        self.logger.debug("guessing distribution(s): %s"
                          % ', '.join(self.distributions))

    def _set_package_format(self):
        """set the package format to be able to run COMMANDS

        setup_file must not be redefine since we can call this
        method several times
        """
        setup_file = self.config.setup_file = self._normpath(self.config.setup_file)
        if setup_file:
            self.logger.info('use specific setup file: %s', setup_file)

        if osp.isfile('__pkginfo__.py') and not setup_file:
            # Logilab's specific format
            # FIXME Format is buggy if setup_file was set to 'setup.py'
            from logilab.devtools.lib import TextReporter
            self.config._package = PackageInfo(reporter=TextReporter(file(os.devnull, "w+")),
                                               directory=self.config.pkg_dir)
            assert osp.isfile('setup.py'), "setup.py is still mandatory"
        # other script can be used if compatible with the expected targets in COMMANDS
        elif osp.isfile(setup_file):
            if osp.basename(setup_file) == 'setup.py':
                # case for python project (distutils, setuptools)
                self.config._package = run_setup(setup_file, None, stop_after="init")
            else:
                # generic case: the setup file should only honor targets as:
                # sdist, project, version, clean (see COMMANDS)
                self.config._package = file(setup_file)
                if not os.stat(setup_file).st_mode & stat.S_IEXEC:
                    raise LGPException('setup file %s has no execute permission'
                                       % setup_file)
        else:
            class debian(object): pass
            self.config._package = debian()
        self.logger.debug("use setup package class format: %s" % self.package_format)

    def _prune_pkg_dir(self):
        if self.package_format in ('PackageInfo', 'Distribution'):
            if os.path.exists('MANIFEST'):
                # remove MANIFEST file at the beginning to avoid reusing it
                # distutils can use '--force-manifest' but setuptools doens't have this option.
                os.unlink('MANIFEST')
            spurious = "%s-%s" % (self.get_upstream_name(), self.get_upstream_version())
            if os.path.isdir(spurious):
                import shutil
                self.logger.warn("remove spurious temporary directory '%s' built by distutils" % spurious)
                shutil.rmtree(spurious)

    @property
    def package_format(self):
        return self.config._package.__class__.__name__

    def _run_command(self, cmd, **args):
        """run an internal declared command as new subprocess"""
        if isinstance(cmd, list):
            cmdline = ' '.join(cmd)
        else:
            cmd = COMMANDS[cmd][self.package_format]
            if callable(cmd):
                try:
                    return cmd()
                except IOError, err:
                    raise LGPException(err)
            cmdline = Template(cmd)
            cmdline = cmdline.substitute(setup=self.config.setup_file, **args)
        self.logger.debug('run subprocess command: %s' % cmdline)
        if args:
            self.logger.debug('command substitutions: %s' % args)
        process = Popen(cmdline.split(), stdout=PIPE)
        pipe = process.communicate()[0].strip()
        if process.returncode > 0:
            process.cmd = cmdline.split()
            raise LGPCommandException("lgp aborted by the '%s' command child process"
                                      % cmdline, process)
        return pipe

    def get_debian_dir(self, distrib):
        """get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian' is for distribution found in debian/changelog
        - 'debian.$OTHER' directory for $OTHER distribution if need

        Extra possibility:
        - 'debian/$OTHER' subdirectory for $OTHER distribution if need
        """
        # TODO Check the X-Vcs-* to fetch remote Debian configuration files
        debiandir = 'debian' # default debian config location
        override_dir = osp.join(debiandir, distrib)

        # Use new directory scheme with separate Debian repository in head
        # developper can create an overlay for the debian directory
        old_override_dir = '%s.%s' % (debiandir, distrib)
        if osp.isdir(osp.join(self.config.pkg_dir, old_override_dir)):
            #self.logger.warn("new distribution overlay system available: you "
            #                 "can use '%s' subdirectory instead of '%s' and "
            #                 "merge the files"
            #                 % (override_dir, old_override_dir))
            debiandir = old_override_dir

        if osp.isdir(osp.join(self.config.pkg_dir, override_dir)):
            debiandir = override_dir
        return debiandir

    def get_architectures(self, archi=None, basetgz=None):
        return utils.get_architectures(archi or self.config.archi, basetgz or self.config.basetgz)

    get_debian_name = staticmethod(utils.get_debian_name)

    @cached
    def get_debian_version(self):
        """get upstream and debian versions depending of the last changelog entry found in Debian changelog
        """
        changelog = osp.join('debian', 'changelog')
        debian_version = utils._parse_deb_version(changelog)
        self.logger.debug('retrieve debian version from %s: %s' %
                          (changelog, debian_version))
        return debian_version

    def is_initial_debian_revision(self):
        # http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
        try:
            debian_revision = self.get_debian_version().rsplit('-', 1)[1]
            if debian_revision == '0':
                self.logger.error("Debian version part (the part after the -) "
                                  "should start with one, not with zero")
        except IndexError:
            self.logger.warn("The absence of a debian_revision is equivalent to "
                             "a debian_revision of 0.")
            debian_revision = "0"
        return debian_revision in ['0', '1'] # or debian_revision.startswith(('0+', '1+')):

    @cached
    def get_upstream_name(self):
        return self._run_command('project')

    @cached
    def get_upstream_version(self):
        version = self._run_command('version')
        if '-' in version and self.package_format == 'debian':
            version = version.split('-')[0]
        return version

    def get_versions(self):
        versions = self.get_debian_version().rsplit('-', 1)
        return versions

    def _check_version_mismatch(self):
        upstream_version = self.get_upstream_version()
        #debian_upstream_version = self.get_versions()[0]
        debian_upstream_version = self.get_debian_version().rsplit('-', 1)[0]
        assert debian_upstream_version == self.get_versions()[0], "get_versions() failed"
        if upstream_version != debian_upstream_version:
            msg = "version mismatch: upstream says '%s' and debian/changelog says '%s'"
            msg %= (upstream_version, debian_upstream_version)
            raise LGPException(msg)

    def prepare_source_archive(self, tmpdir, current_distrib):
        """prepare and extract the upstream tarball

        FIXME replace by TarFile Object
        """
        # Mandatory to be compatible with format 1.0
        self.logger.debug("copy pristine tarball to prepare Debian source package diff")
        cp(self.config.orig_tarball, tmpdir)
        # TODO obtain current format version
        # os.path.exists(osp.join(self.origpath, "debian/source/format")

        self.logger.debug("extracting original source archive for %s distribution in %s"
                          % (current_distrib or "default", tmpdir))
        try:
            cmd = 'tar --atime-preserve --preserve-permissions --preserve-order -xzf %s -C %s'\
                  % (self.config.orig_tarball, tmpdir)
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            raise LGPCommandException('an error occured while extracting the '
                                      'upstream tarball', err)

        # Find the right orig path in tarball
        # It can be different of the standard <upstream-name>-<upstream-version>
        # if pristine tarball was retrieve remotely (vcs frontend for example)
        self.origpath = [d for d in os.listdir(tmpdir)
                         if osp.isdir(osp.join(tmpdir,d))][0]

        format = "%s-%s" % (self.get_upstream_name(), self.get_upstream_version())
        if self.origpath != format:
            self.logger.warn("source directory of original source archive (pristine tarball) "
                             "has not the expected format (%s): %s" % (format, self.origpath))

        # directory containing the debianized source tree
        # (i.e. with a debian sub-directory and maybe changes to the original files)
        # origpath is depending of the upstream convention
        self.origpath = osp.join(tmpdir, self.origpath)

        # support of the multi-distribution
        return self.manage_current_distribution(current_distrib)

    def manage_current_distribution(self, distrib):
        """manage debian files depending of the current distrib from options

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the default version (unstable)
        If a file should not be included, touch an empty file in the overlay
        directory.

        This is specific to Logilab (debian directory is in project directory)
        """
        try:
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, 'debian'), osp.join(self.origpath, 'debian/'),
                   verbose=self.config.verbose == 2)
        except IOError, err:
            raise LGPException(err)

        debian_dir = self.get_debian_dir(distrib)
        if debian_dir != "debian":
            self.logger.info("overriding files from '%s' directory..." % debian_dir)
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, debian_dir), osp.join(self.origpath, 'debian/'),
                   verbose=self.config.verbose)

        from debian.changelog import Changelog
        debchangelog = osp.join(self.origpath, 'debian', 'changelog')
        changelog = Changelog(open(debchangelog))
        # substitute distribution string in changelog
        if distrib:
            changelog.distributions = distrib
        # append suffix string (or timestamp if suffix is empty) to debian revision
        if self.config.suffix is not None:
            suffix = self.config.suffix or '+%s' % int(time.time())
            self.logger.debug("suffix '%s' added to package version" % suffix)
            changelog.version = str(changelog.version) + suffix
        changelog.write_to_open_file(open(debchangelog, 'w'))

        return self.origpath

    def get_basetgz(self, distrib, arch, check=True):
        basetgz = osp.join(self.config.basetgz, "%s-%s.tgz" % (distrib, arch))
        if check and not osp.exists(basetgz):
            raise LGPException("lgp image '%s' not found. Please create it with lgp setup" % basetgz)
        return basetgz

    def create_tmp_context(self, suffix=""):
        """create new build temporary context

        Each context (directory for now) will be cleaned at the end of the build
        process by the destroy_tmp_context method"""
        self._tmpdir = tempfile.mkdtemp(suffix)
        self.logger.debug('changing build context... (%s)' % self._tmpdir )
        self._tmpdirs.append(self._tmpdir)
        return self._tmpdir

    def destroy_tmp_context(self):
        """clean all temporary build context and returns exit code"""
        self.clean_tmpdirs()
        return self.build_status

    def _normpath(self, path):
        """helper method to normalize filepath arguments before
        changing current directory (will return absolute paths)

        XXX could be coded directly by option checker (optparse)
        """
        if path:
            assert self.old_current_directory
            path = osp.abspath(osp.join(self.old_current_directory,
                                        osp.expanduser(path)))
            if not osp.exists(path):
                msg = "file given in command line cannot be found:\n\t%s"
                raise LGPException(msg % path)
        return path

    def get_distrib_dir(self, distrib):
        """get the dynamic target release directory"""
        distrib_dir = os.path.normpath(os.path.expanduser(self.config.dist_dir))
        # special case when current directory is used to put result files ("-r .")
        if distrib_dir not in ['.', '..']:
            distrib_dir = os.path.join(distrib_dir, distrib)
        # check if distribution directory exists, create it if necessary
        os.umask(0002)
        try:
            os.makedirs(distrib_dir, 0755)
        except OSError, exc:
            # It's not a problem here to pass silently if the directory
            # is really existing but fails otherwise
            if not os.path.isdir(distrib_dir):
                msg = "not mountable location in chroot: %s"
                self.logger.warn(msg, distrib_dir)
            if exc.errno != errno.EEXIST:
                raise
        return distrib_dir

