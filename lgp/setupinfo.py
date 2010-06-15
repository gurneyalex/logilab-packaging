# Copyright (c) 2008 Logilab (contact@logilab.fr)
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
""" generic package information container

"""

import sys
import os
import stat
import os.path as osp
import logging
import time
import urllib
import tempfile
from string import Template
from distutils.core import run_setup
#from pkg_resources import FileMetadata
from subprocess import Popen, PIPE
from subprocess import check_call, CalledProcessError

from logilab.common.configuration import Configuration
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp
from logilab.common.fileutils import export

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lgp import LGP_CONFIG_FILE
from logilab.devtools.lgp import utils
from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException,
                                             LGPException,
                                             LGPCommandException,
                                             SetupException)

LOG_FORMAT='%(levelname)1.1s:%(name)s: %(message)s'
COMMANDS = {
        "sdist" : {
            "file": './$setup dist-gzip -e DIST_DIR=$dist_dir',
            "Distribution": 'python setup.py -q sdist -d $dist_dir',
            "PackageInfo": 'python setup.py -q sdist -d $dist_dir',
            "debian": "fakeroot debian/rules get-orig-source",
        },
        "clean" : {
            "file": './$setup clean',
            "Distribution": 'python setup.py clean --all',
            "PackageInfo": 'python setup.py clean --all',
            "debian": "fakeroot debian/rules clean",
        },
        "version" : {
            "file": './$setup version',
            "Distribution": 'python setup.py --version',
            "PackageInfo": 'python setup.py --version',
            "debian": utils._parse_deb_version,
        },
        "project" : {
            "file": './$setup project',
            "Distribution": 'python setup.py --name',
            "PackageInfo": 'python setup.py --name',
            "debian": utils._parse_deb_project,
        },
}

class SetupInfo(Configuration):
    """ a setup class to handle several package setup information """

    def __init__(self, arguments, options=None, **args):
        isatty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        self.options = (
               ('version',
                {'help': "output version information and exit",
                }),
               ('verbose',
                {'action': 'count',
                 'dest' : "verbose",
                 'short': 'v',
                 'help': "run in verbose mode",
                }),
               ('distrib',
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
                 'help': "build for the requested debian architectures only (automatic detection otherwise)",
                 'group': 'Default',
                }),
               ('pkg_dir',
                {'type': 'string',
                 'hide': True,
                 'dest': "pkg_dir",
                 'short': 'p',
                 'metavar' : "<root of the debian project directory>",
                }),
               ('no-color',
                {'action': 'store_true',
                 'default': not isatty,
                 'dest': "no_color",
                 'help': "print log messages without color",
                }),
               ('dump-config',
                {'action': 'store_true',
                 'dest': "dump_config",
                 'help': "dump lgp configuration (debugging purpose)"
                }),
               ('basetgz',
                {'type': 'string',
                 'hide': True,
                 'default': '/var/cache/lgp/buildd',
                 'dest': "basetgz",
                 'metavar' : "<pbuilder basetgz location>",
                 'help': "specifies the location of base.tgz used by pbuilder",
                 'group': 'Default',
                }),
               ('setup-file',
                {'type': 'string',
                 'dest': 'setup_file',
                 'hide': True,
                 'default' : 'setup.mk',
                 'metavar': "<setup file names>",
                 'help': "use an alternate setup file with Lgp expected arguments (see documentation)"
                }),
               )
        if options:
            for opt in options:
                self.options += opt
        super(SetupInfo, self).__init__(options=self.options, **args)

        # Load the global settings for lgp
        if osp.isfile(LGP_CONFIG_FILE):
            self.load_file_configuration(LGP_CONFIG_FILE)

        # Manage arguments (project path essentialy)
        self.arguments = self.load_command_line_configuration(arguments)

        # Version information
        if self.config.version:
            from logilab.devtools.__pkginfo__ import version, distname, copyright, web
            print "lgp (%s) %s\n%s" % (distname, version, copyright)
            print "Please visit: %s " % web
            sys.exit()

        if self.config.dump_config:
            self.generate_config()
            sys.exit()

        # Instanciate the default logger configuration
        if not logging.getLogger().handlers:
            logging.getLogger().name = sys.argv[1]
            console = logging.StreamHandler()
            if self.config.no_color or not isatty:
                console.setFormatter(logging.Formatter(LOG_FORMAT))
            else:
                console.setFormatter(ColorFormatter(LOG_FORMAT))
            logging.getLogger().addHandler(console)
            logging.getLogger().setLevel(logging.INFO)

            if self.config.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            else:
                # Redirect subprocesses stdout output only in case of verbose mode
                # We always allow subprocesses to print on the stderr (more convenient)
                sys.stdout = open(os.devnull,"w")
                #sys.stderr = open(os.devnull,"w")

        # Go to package directory
        if self.config.pkg_dir is None:
            if self.arguments and os.path.exists(self.arguments[0]):
                self.config.pkg_dir = osp.abspath(self.arguments[0])
            else:
                self.config.pkg_dir = os.getcwd()
        try:
            if os.path.isfile(self.config.pkg_dir):
                self.config.pkg_dir = os.path.dirname(self.config.pkg_dir)
            # Keep working relative pathnames provided in line arguments
            if hasattr(self.config, "orig_tarball") and self.config.orig_tarball:
                self.config.orig_tarball = osp.abspath(osp.expanduser(self.config.orig_tarball))
            os.chdir(self.config.pkg_dir)
            logging.debug('change the current working directory to: %s' % self.config.pkg_dir)
        except OSError, err:
            raise LGPException(err)

        # no default value for distribution. Try to retrieve it in changelog
        if self.config.distrib is None or 'changelog' in self.config.distrib:
            self.config.distrib = utils.guess_debian_distribution()

        # just a warning issuing for possibly confused configuration
        if self.config.archi and 'all' in self.config.archi:
            logging.warn('the "all" keyword can be confusing about the '
                         'targeted architectures. Consider using the "any" keyword '
                         'to force the build on all architectures or let lgp finds '
                         'the value in debian/changelog by itself in doubt.')
            logging.warn('lgp replaces "all" with "current" architecture value for this command')

        # Define mandatory attributes for lgp commands
        self.architectures = utils.get_architectures(self.config.archi,
                                                     self.config.basetgz)
        self.distributions = utils.get_distributions(self.config.distrib,
                                                     self.config.basetgz)
        logging.debug("guessing distribution(s): %s" % ','.join(self.distributions))
        logging.debug("guessing architecture(s): %s" % ','.join(self.architectures))

        # Guess the package format
        if osp.isfile('__pkginfo__.py') and not osp.isfile(self.config.setup_file):
            # Logilab's specific format
            from logilab.devtools.lib import TextReporter
            self._package = PackageInfo(reporter=TextReporter(file(os.devnull, "w+")),
                                        directory=self.config.pkg_dir)
        # other script can be used if compatible with the expected targets in COMMANDS
        elif osp.isfile(self.config.setup_file):
            if self.config.setup_file == 'setup.py':
                # case for python project (distutils, setuptools)
                self._package = run_setup('./setup.py', None, stop_after="init")
            else:
                # generic case: the setup file should only honor targets as:
                # sdist, project, version, clean (see COMMANDS)
                self._package = file(self.config.setup_file)
                if not os.stat(self.config.setup_file).st_mode & stat.S_IEXEC:
                    raise LGPException('setup file %s has no execute permission'
                                       % self.config.setup_file)
        else:
            class debian(object): pass
            self._package = debian()
        logging.debug("use setup package class format: %s" % self.package_format)

        if self.package_format in ('PackageInfo', 'Distribution'):
            if os.path.exists('MANIFEST'):
                # remove MANIFEST file at the beginning to avoid reusing it
                # distutils can use '--force-manifest' but setuptools doens't have this option.
                os.unlink('MANIFEST')
            spurious = "%s-%s" % (self.get_upstream_name(), self.get_upstream_version())
            if os.path.isdir(spurious):
                import shutil
                logging.warn("remove spurious temporarly directory '%s' built by distutils" % spurious)
                shutil.rmtree(spurious)

    @property
    def current_distrib(self):
        # workaround: we set current distrib immediately to be able to copy
        # pristine tarball in a valid location
        try:
            return self.distributions[0]
        except IndexError:
            return ""

    @property
    def package_format(self):
        return self._package.__class__.__name__

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
        logging.debug('run subprocess command: %s' % cmdline)
        if args:
            logging.debug('command substitutions: %s' % args)
        process = Popen(cmdline.split(), stdout=PIPE)
        pipe = process.communicate()[0].strip()
        if process.returncode > 0:
            process.cmd = cmdline.split()
            raise LGPCommandException("lgp aborted by the '%s' command child process"
                                      % cmdline, process)
        return pipe

    def get_debian_dir(self):
        """get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian' is for distribution found in debian/changelog
        - 'debian.$OTHER' directory for $OTHER distribution if need

        Extra possibility:
        - 'debian/$OTHER' subdirectory for $OTHER distribution if need
        """
        # TODO Check the X-Vcs-* to fetch remote Debian configuration files
        debiandir = 'debian' # default debian config location

        if self.current_distrib:
            override_dir = osp.join(debiandir, self.current_distrib)

            # Use new directory scheme with separate Debian repository in head
            # developper can create an overlay for the debian directory
            old_override_dir = '%s.%s' % (debiandir, self.current_distrib)
            if osp.isdir(osp.join(self.config.pkg_dir, old_override_dir)):
                #logging.warn("new distribution overlay system available: you "
                #             "can use '%s' subdirectory instead of '%s' and "
                #             "merge the files"
                #             % (override_dir, old_override_dir))
                debiandir = old_override_dir

            if osp.isdir(osp.join(self.config.pkg_dir, override_dir)):
                debiandir = override_dir

        return debiandir

    get_architectures = staticmethod(utils.get_architectures)
    get_debian_name = staticmethod(utils.get_debian_name)

    @utils.cached
    def get_debian_version(self):
        """get upstream and debian versions depending of the last changelog entry found in Debian changelog
        """
        cwd = os.getcwd()
        os.chdir(self.config.pkg_dir)
        try:
            changelog = osp.join('debian', 'changelog')
            debian_version = utils._parse_deb_version(changelog)
            logging.debug('retrieve debian version from %s: %s' %
                          (changelog, debian_version))
            return debian_version
        finally:
            os.chdir(cwd)

    def is_initial_debian_revision(self):
        # http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
        initial = True
        try:
            debian_revision = self.get_debian_version().rsplit('-', 1)[1]
        except IndexError:
            logging.warn("The absence of a debian_revision is equivalent to a debian_revision of 0.")
            debian_revision = "0"

        if debian_revision == '0':
            logging.info("It is conventional to restart the debian_revision"
                         " at 1 each time the upstream_version is increased.")
        if debian_revision not in ['0', '1']:
            return False
        return True

    @utils.cached
    def get_upstream_name(self):
        return self._run_command('project')

    @utils.cached
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

    def clean_repository(self):
        """clean the project repository"""
        logging.debug("clean the project repository")
        self._run_command('clean')

    def make_orig_tarball(self):
        """make upstream pristine tarballs (Debian way)

        Start by calling the optional get-orig-source from debian/rules
        If not possible, failback to a local creation

        A call to move_package_files() will reset instance variable
        config.orig_tarball to its new name for later reuse

        See:
        http://www.debian.org/doc/debian-policy/ch-source.html
        http://wiki.debian.org/SandroTosi/Svn_get-orig-source
        http://hg.logilab.org/<upstream_name>/archive/<upstream_version>.tar.gz
        """
        self._check_version_mismatch()

        # change directory context at pristine tarball generation
        self.create_build_context()

        fileparts = (self.get_upstream_name(), self.get_upstream_version())
        tarball = '%s_%s.orig.tar.gz' % fileparts
        upstream_tarball = '%s-%s.tar.gz' % fileparts

        # run optional debian/rules get-orig-source target to retrieve pristine tarball
        if self.config.orig_tarball is None and not self.is_initial_debian_revision():
            logging.info('trying to retrieve pristine tarball remotely...')
            try:
                cmd = ["fakeroot", "debian/rules", "get-orig-source"]
                check_call(cmd, stderr=file(os.devnull, "w"))
                assert osp.isfile(tarball)
                self.config.orig_tarball = osp.abspath(tarball)
            except CalledProcessError, err:
                logging.warn("run '%s' without success" % ' '.join(cmd))

        if self.config.orig_tarball is None:
            # Make a coherence check about the pristine tarball
            if not self.is_initial_debian_revision():
                debian_revision = self.get_debian_version().rsplit('-', 1)[1]
                logging.error("Debian source archive (pristine tarball) is required when you "
                              "don't build the first revision of a debian package "
                              "(use '--orig-tarball' option)")
                logging.info("If you haven't the original tarball version, you could run: "
                             "'apt-get source --tar-only %s'"
                             % self.get_debian_name())
                raise LGPException('unable to build upstream tarball of %s package '
                                   'for Debian revision "%s"'
                                   % (self.get_debian_name(), debian_revision))
            logging.info("creation of a new Debian source archive (pristine tarball) from working directory")
            try:
                self._run_command("sdist", dist_dir=self._tmpdir)
            except CalledProcessError, err:
                logging.error("creation of the source archive failed")
                logging.error("check if the version '%s' is really tagged in"\
                                  " your repository" % self.get_upstream_version())
                raise LGPCommandException("source distribution wasn't properly built", err)
            self.config.orig_tarball = osp.join(self._tmpdir, upstream_tarball)
        else:
            logging.info("reuse archive '%s' as original source archive (pristine tarball)"
                         % self.config.orig_tarball)

        if not os.path.basename(self.config.orig_tarball).startswith(self.get_upstream_name()):
            msg = "pristine tarball filename doesn't start with upstream name '%s'. really suspect..."
            logging.error(msg % self.get_upstream_name())

        tarball = osp.join(self._tmpdir, tarball)
        try:
            urllib.urlretrieve(self.config.orig_tarball, tarball) # auto-renaming here
            self.config.orig_tarball = tarball
        except IOError, err:
            logging.critical("the provided original source archive (tarball) "
                             "can't be retrieved from given location: %s"
                             % self.config.orig_tarball)
            raise LGPException(err)
        assert osp.isfile(tarball), 'Debian source archive (pristine tarball) not found'

        # move pristine tarball and exit if asked by command-line
        if self.config.get_orig_source:
            self.move_package_files([self.config.get_orig_source],
                                    verbose=self.config.get_orig_source)
            self.finalize()

    def prepare_source_archive(self):
        """prepare and extract the upstream tarball

        FIXME replace by TarFile Object
        """
        # change directory context at each build
        self.create_build_context()

        logging.debug("prepare for %s distribution" % self.current_distrib or "default")
        logging.debug("extracting original source archive in %s" % self._tmpdir)
        try:
            cmd = 'tar --atime-preserve --preserve-permissions --preserve-order -xzf %s -C %s'\
                  % (self.config.orig_tarball, self._tmpdir)
            check_call(cmd.split(), stdout=sys.stdout)
        except CalledProcessError, err:
            raise LGPCommandException('an error occured while extracting the '
                                      'upstream tarball', err)

        # Find the right orig path in tarball
        # It can be different of the standard <upstream-name>-<upstream-version>
        # if pristine tarball was retrieve remotely (vcs frontend for example)
        self.origpath = [d for d in os.listdir(self._tmpdir)
                         if osp.isdir(osp.join(self._tmpdir,d))][0]

        format = "%s-%s" % (self.get_upstream_name(), self.get_upstream_version())
        if self.origpath != format:
            logging.warn("source directory of original source archive (pristine tarball) "
                         "has not the expected format (%s): %s" % (format, self.origpath))

        # directory containing the debianized source tree
        # (i.e. with a debian sub-directory and maybe changes to the original files)
        # origpath is depending of the upstream convention
        self.origpath = osp.join(self._tmpdir, self.origpath)

        # support of the multi-distribution
        return self.manage_current_distribution()


    def manage_current_distribution(self):
        """manage debian files depending of the current distrib from options

        We copy debian_dir directory into tmp build depending of the target distribution
        in all cases, we copy the debian directory of the default version (unstable)
        If a file should not be included, touch an empty file in the overlay
        directory.

        The distribution value will always be rewritten in final changelog.

        This is specific to Logilab (debian directory is in project directory)
        """
        try:
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, 'debian'), osp.join(self.origpath, 'debian/'))
        except IOError, err:
            raise LGPException(err)

        debian_dir = self.get_debian_dir()
        if debian_dir != "debian":
            logging.info("overriding files from '%s' directory..." % debian_dir)
            # don't forget the final slash!
            export(osp.join(self.config.pkg_dir, debian_dir), osp.join(self.origpath, 'debian/'),
                   verbose=self.config.verbose)

        # substitute distribution string in file only if line not starting by
        # spaces (simple heuristic to prevent other changes in content)
        # FIXME use debian_bundle.changelog.Changelog instead
        if self.current_distrib:
            cmd = ['sed', '-i', '/^[[:alpha:]]/s/\([[:alpha:]]\+\);/%s;/'
                   % self.current_distrib, osp.join(self.origpath, 'debian', 'changelog')]
            try:
                check_call(cmd, stdout=sys.stdout)
            except CalledProcessError, err:
                raise LGPCommandException("bad substitution for distribution field", err)

        # substitute version string in appending timestamp and suffix
        # suffix should not be empty
        # FIXME use debian_bundle.changelog.Changelog instead
        if self.config.suffix:
            timestamp = int(time.time())
            suffix = ''.join(self.config.suffix,timestamp)
            logging.debug("suffix '%s' added to package names" % suffix)
            cmd = ['sed', '-i', '1s/(\(.*\))/(\\1%s)/' % suffix,
                   osp.join(self.origpath, 'debian', 'changelog')]
            try:
                check_call(cmd, stdout=sys.stdout)
            except CalledProcessError, err:
                raise LGPCommandException("bad substitution for version field", err)

        return self.origpath

    def get_basetgz(self, distrib, arch, check=True):
        basetgz = osp.join(self.config.basetgz, "%s-%s.tgz" % (distrib, arch))
        if check and not osp.exists(basetgz):
            raise LGPException("lgp image '%s' not found. Please create it with lgp setup" % basetgz)
        return basetgz

    def create_build_context(self, suffix=""):
        """create new build temporary context

        Each context (directory for now) will be cleaned at the end of the build
        process by the finalize method"""
        self._tmpdir = tempfile.mkdtemp(suffix)
        logging.debug('changing build context... (%s)' % self._tmpdir )
        self._tmpdirs.append(self._tmpdir)
        return self._tmpdir

    def finalize(self):
        """clean all temporary build context and exit"""
        self.clean_tmpdirs()
        sys.exit(self.build_status)
