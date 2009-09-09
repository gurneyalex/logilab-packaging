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
import glob
import tempfile
from string import Template
from distutils.core import run_setup
#from pkg_resources import FileMetadata
from subprocess import Popen, PIPE
from subprocess import check_call, CalledProcessError

from logilab.common.configuration import Configuration
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp, mv
from logilab.common.fileutils import export

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib import TextReporter
from logilab.devtools.lgp import LGP_CONFIG_FILE
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException)
from logilab.devtools.lgp.utils import get_distributions, cached

LOG_FORMAT='%(levelname)1.1s:%(name)s: %(message)s'
COMMANDS = {
        "sdist" : {
            "file": './$setup dist-gzip -e DIST_DIR=$dist_dir',
            "Distribution": 'python setup.py -q sdist -d $dist_dir',
            "PackageInfo": 'python setup.py -q sdist --force-manifest -d $dist_dir',
        },
        "clean" : {
            "file": './$setup clean',
            "Distribution": 'python setup.py clean',
            "PackageInfo": 'python setup.py clean',
        },
        "version" : {
            "file": './$setup version',
            "Distribution": 'python setup.py --version',
            "PackageInfo": 'python setup.py --version',
        },
        "project" : {
            "file": './$setup project',
            "Distribution": 'python setup.py --name',
            "PackageInfo": 'python setup.py --name',
        },
}

class SetupInfo(Configuration):
    """ a setup class to handle several package setup information """

    def __init__(self, arguments, options=None, **args):
        isatty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        self.options = (
               ('version',
                {'help': "output version information and exit",
                 #'dest' : "version",
                }),
               ('verbose',
                {'action': 'store_true',
                 'dest' : "verbose",
                 'short': 'v',
                 'help': "run silently without confirmation",
                }),
               ('distrib',
                {'type': 'csv',
                  'dest': 'distrib',
                  'short': 'd',
                  'metavar': "<distribution>",
                  'help': "list of Debian distributions (from images created by setup). "
                          "Use 'all' for automatic detection or 'changelog' "
                          "for the value found in debian/changelog",
                 'group': 'Default',
                }),
               ('arch',
                {'type': 'csv',
                 'dest': 'archi',
                 'default' : 'current',
                 'short': 'a',
                 'metavar' : "<architecture>",
                 'help': "build for the requested debian architectures only. Use 'all' for automatic detection",
                 'group': 'Default',
                }),
               ('pkg_dir',
                {'type': 'string',
                 'hide': True,
                 'dest': "pkg_dir",
                 'short': 'p',
                 'metavar' : "<project directory>",
                 'help': "set a specific project directory",
                }),
               ('no-color',
                {'action': 'store_true',
                 'default': not isatty,
                 'dest': "no_color",
                 'help': "print log messages without color",
                }),
               ('dump-config',
                {'action': 'store_true',
                 'hide': True,
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
                #{'type': 'csv',
                {'type': 'string',
                 'dest': 'setup_file',
                 'hide': True,
                 #'default' : ['setup.py', 'setup.mk'],
                 'default' : 'setup.mk',
                 'metavar': "<setup file names>",
                 'help': "list of setup files to use"
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

        if self.config.dump_config:
            self.generate_config()
            sys.exit()

        # Go to package directory
        if self.config.pkg_dir is None:
            self.config.pkg_dir = osp.abspath(self.arguments
                                              and self.arguments[0]
                                              or os.getcwd())
        try:
            os.chdir(self.config.pkg_dir)
        except OSError, err:
            if sys.argv[1] != "piuparts":
                raise LGPException(err)

        # no default value for distribution. Try to retrieve it in changelog
        if self.config.distrib is None or 'changelog' in self.config.distrib:
            self.config.distrib = self.get_debian_distribution()

        # Define mandatory attributes for lgp commands
        self.architectures = self.get_architectures(self.config.archi,
                                                    self.config.basetgz)
        self.distributions = get_distributions(self.config.distrib,
                                               self.config.basetgz)

        # Setup command can be run anywhere, so skip setup file retrieval
        if sys.argv[1] in ["setup", "login", "script", "piuparts"]:
            return

        # Guess the package format
        if self.config.setup_file == 'setup.py':
            # generic case for python project (distutils, setuptools)
            self._package = run_setup('./setup.py', None, stop_after="init")
        elif osp.isfile('__pkginfo__.py'):
            # Logilab's specific format
            self._package = PackageInfo(reporter=TextReporter(sys.stderr, sys.stderr.isatty()),
                                        directory=self.config.pkg_dir)
        # Other script can be used if compatible with the expected targets in COMMANDS
        elif osp.isfile(self.config.setup_file):
            self._package = file(self.config.setup_file)
            if not os.stat(self.config.setup_file).st_mode & stat.S_IEXEC:
                raise LGPException('setup file %s has no execute permission'
                                   % self.config.setup_file)
        else:
            raise LGPException('no valid setup file (expected: %s)'
                               % self.config.setup_file)

        # print chroot information
        logging.debug("running for distribution(s): %s" % ', '.join(self.distributions))
        logging.debug("running for architecture(s): %s" % ', '.join(self.architectures))

        logging.debug("guess the setup package class: %s" % self.package_format)

    @property
    def current_distrib(self):
        # workaround: we set current distrib immediately to be able to copy
        # pristine tarball in a valid location
        return self.distributions[0]

    @property
    def package_format(self):
        return self._package.__class__.__name__

    def _run_command(self, cmd, output=False, **args):
        """run an internal declared command as new subprocess"""
        cmdline = Template(COMMANDS[cmd][self.package_format])
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
        - 'debian/$OTHER' subdirectory for $OTHER distribution if need
        """
        # TODO Check the X-Vcs-* to fetch remote Debian configuration files
        debiandir = 'debian' # default debian config location

        if not self.current_distrib:
            return debiandir

        override_dir = osp.join(debiandir, self.current_distrib)

        # Use new directory scheme with separate Debian repository in head
        # developper can create an overlay for the debian directory
        old_override_dir = '%s.%s' % (debiandir, self.current_distrib)
        if osp.isdir(osp.join(self.config.pkg_dir, old_override_dir)):
            logging.warn("new distribution overlay system available: you "
                         "can use '%s' subdirectory instead of '%s' and "
                         "merge the files"
                         % (override_dir, old_override_dir))
            debiandir = old_override_dir

        if osp.isdir(osp.join(self.config.pkg_dir, override_dir)):
            debiandir = override_dir
        return debiandir

    def get_debian_name(self):
        """obtain the debian package name

        The information is found in debian/control withe the 'Source:' field
        """
        try:
            control = osp.join(self.config.pkg_dir, 'debian', 'control')
            for line in open(control):
                line = line.split(' ', 1)
                if line[0] == "Source:":
                    return line[1].rstrip()
        except IOError, err:
            raise LGPException('a Debian control file should exist in "%s"' % control)

    def get_debian_architecture(self):
        """obtain the debian architecture(s)

        The information is found in debian/control withe the 'Architecture:' field
        """
        try:
            control = osp.join('debian', 'control')
            for line in open(control):
                line = line.split(' ', 1)
                if line[0] == "Architecture:":
                    return line[1].rstrip().split(',')
        except IOError, err:
            raise LGPException('a Debian control file should exist in "%s"' % control)

    def is_architecture_independant(self):
        return 'all' in self.get_debian_architecture()

    def get_debian_distribution(self):
        """get the default debian distribution in debian/changelog

           Useful to determine a default distribution different from unstable if need
        """
        try:
            cmd = "dpkg-parsechangelog"
            process = Popen(cmd.split(), stdout=PIPE)
            pipe = process.communicate()[0]
            if process.returncode > 0:
                msg = 'dpkg-parsechangelog exited with status %s' % process.returncode
                process.cmd = cmd.split()
                raise LGPCommandException(msg, process)

            for line in pipe.split('\n'):
                line = line.strip()
                if line and line.startswith('Distribution:'):
                    distribution = line.split(' ', 1)[1].strip()
                    logging.info('retrieve default debian distribution from debian/changelog: %s'
                                 % distribution)
                    return [distribution,]
            raise LGPException('Debian Distribution field not found in debian/changelog')
        except CalledProcessError, err:
            raise LGPCommandException(msg, err)

    def get_debian_version(self):
        """get upstream and debian versions depending of the last changelog entry found in Debian changelog

           We parse the dpkg-parsechangelog output instead of changelog file
           Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        cwd = os.getcwd()
        os.chdir(self.config.pkg_dir)
        try:
            changelog = osp.join(self.get_debian_dir(), 'changelog')
            try:
                cmd = 'dpkg-parsechangelog'
                if osp.isfile(changelog):
                    cmd += ' -l%s' % changelog

                process = Popen(cmd.split(), stdout=PIPE)
                pipe = process.communicate()[0]
                if process.returncode > 0:
                    msg = 'dpkg-parsechangelog exited with status %s' % process.returncode
                    process.cmd = cmd.split()
                    raise LGPCommandException(msg, process)

                for line in pipe.split('\n'):
                    line = line.strip()
                    if line and line.startswith('Version:'):
                        debian_version = line.split(' ', 1)[1].strip()
                        logging.debug('retrieve debian version from %s: %s' %
                                      (changelog, debian_version))
                        return debian_version
                raise LGPException('Debian Version field not found in %s'
                                   % changelog)
            except CalledProcessError, err:
                raise LGPCommandException(msg, err)
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
            initial = False
            if not self.config.orig_tarball:
                logging.error("--orig-tarball option is required when you don't "
                              "build the first revision of a debian package")
                logging.error("If you haven't the original tarball version, please do "
                              "an 'apt-get source --tar-only %s' of the Debian source package"
                             % self.get_debian_name())
                raise LGPException('unable to build upstream tarball of %s package '
                                   'for Debian revision "%s"'
                                   % (self.get_debian_name(), debian_revision))
        return initial

    def get_architectures(self, archi=None, basetgz=None):
        """ Ensure that the architectures exist

            :param:
                archi: str or list
                    name of a architecture
            :return:
                list of architecture
        """
        known_archi = Popen(["dpkg-architecture", "-L"], stdout=PIPE).communicate()[0].split()
        if archi is None:
            archi = self.get_debian_architecture()
            logging.debug('retrieve architecture field value from debian/control: %s'
                          % ','.join(archi))
        if 'all' in self.config.archi:
            logging.warn('the "all" keyword can be confusing about the '
                        'target architecture. You should let lgp finds '
                        'the value in debian/changelog by itself.')
            archi = ['any']
            logging.warn('"any" keyword will be use for this build')
        if 'current' in archi:
            archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
        else:
            if 'any' in archi:
                archi = [os.path.basename(f).split('-', 1)[1].split('.')[0]
                           for f in glob.glob(os.path.join(basetgz,'*.tgz'))]
                archi = set(known_archi) & set(archi)
            for a in archi:
                if a not in known_archi:
                    raise ArchitectureException(a)
        return archi

    @cached
    def get_upstream_name(self):
        return self._run_command('project')

    @cached
    def get_upstream_version(self):
        return self._run_command('version')

    def get_versions(self):
        versions = self.get_debian_version().rsplit('-', 1)
        return versions

    def compare_versions(self):
        upstream_version = self.get_upstream_version()
        #debian_upstream_version = self.get_versions()[0]
        debian_upstream_version = self.get_debian_version().rsplit('-', 1)[0]
        assert debian_upstream_version == self.get_versions()[0], "get_versions() failed"
        if upstream_version != debian_upstream_version:
            logging.warn("version provided by upstream is '%s'" % upstream_version)
            logging.warn("upstream version read from Debian changelog is '%s'" % debian_upstream_version)
            logging.error('please check coherence of the previous version numbers')

    def clean_repository(self):
        """clean the project repository"""
        logging.debug("clean the project repository")
        self._run_command('clean')

    def make_orig_tarball(self):
        """make upstream and debianized tarballs in a dedicated directory

        call to move_package_files() will reset instance variable
        config.orig_tarball to its new name for later reuse

        # TODO run 'fakeroot debian/rules get-orig-source' if available
        # http://www.debian.org/doc/debian-policy/ch-source.html
        # http://wiki.debian.org/SandroTosi/Svn_get-orig-source
        # http://hg.logilab.org/<upstream_name>/archive/<upstream_version>.tar.gz
        logging.info("fetch creation of a new Debian source archive (pristine tarball) from upstream release")
        """
        # compare versions here to alert developpers
        self.compare_versions()

        self._tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(self._tmpdir)

        fileparts = (self.get_upstream_name(), self.get_upstream_version())
        tarball = '%s_%s.orig.tar.gz' % fileparts
        upstream_tarball = '%s-%s.tar.gz' % fileparts

        # warn if old archive file (it's surely a test package)
        old_tarball = osp.join(self.get_distrib_dir(), tarball)
        if osp.isfile(osp.join(self.get_distrib_dir(), tarball)):
            logging.warn("a precedent Debian source archive detected in "
                         "'%s' will be deleted by the current build"
                         % self.get_distrib_dir())

        if self.config.orig_tarball is None:
            logging.info("creation of a new Debian source archive (pristine tarball) from upstream release")
            try:
                self._run_command("sdist", dist_dir=self._tmpdir)
            except CalledProcessError, err:
                logging.error("creation of the source archive failed")
                logging.error("check if the version '%s' is really tagged in"\
                                  " your repository" % self.get_upstream_version())
                raise LGPCommandException("source distribution wasn't properly built", err)
            self.config.orig_tarball = osp.join(self._tmpdir, upstream_tarball)
        else:
            expected = [upstream_tarball, tarball]
            if osp.basename(self.config.orig_tarball) not in expected:
                logging.warn("the provided archive hasn't one of the expected formats (%s)"
                             % ', '.join(expected))
            self.config.orig_tarball = osp.expanduser(self.config.orig_tarball)
            logging.info("reuse provided archive '%s' as original source archive (tarball)"
                         % self.config.orig_tarball)

        tarball = osp.join(self._tmpdir, tarball)
        try:
            urllib.urlretrieve(self.config.orig_tarball, tarball)
        except Exception, err:
            raise LGPCommandException("the provided original source archive "
                                      "(tarball) can't be retrieved",
                                     err)
        assert osp.isfile(tarball), 'Debian source archive (pristine tarball) not found'

        # move pristine tarball
        self.move_package_files(verbose=self.config.get_orig_source)

        # exit if asked by command-line
        if self.config.get_orig_source:
            sys.exit()

    def prepare_source_archive(self):
        """prepare and extract the upstream tarball

        FIXME replace by TarFile Object
        """
        logging.debug("prepare for %s distribution" % self.current_distrib)
        logging.debug("extracting original source archive in %s" % self._tmpdir)
        try:
            cmd = 'tar --atime-preserve --preserve -xzf %s -C %s'\
                  % (self.config.orig_tarball, self._tmpdir)
            check_call(cmd.split(), stdout=sys.stdout,
                                    stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException('an error occured while extracting the '
                                      'upstream tarball', err)

        # only provide a pristine tarball when it's an initial revision
        if self.is_initial_debian_revision():
            cp(self.config.orig_tarball, self._tmpdir)
            logging.debug("copy original source archive (pristine tarball) to "
                          "Debian source manifest (first revision of package)")

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
        cmd = ['sed', '-i', '/^[[:alpha:]]/s/\([[:alpha:]]\+\);/%s;/'
               % self.current_distrib, osp.join(self.origpath, 'debian', 'changelog')]
        try:
            check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException("bad substitution for distribution field", err)

        # substitute version string in appending timestamp and suffix
        # suffix should not be empty
        if self.config.suffix:
            timestamp = int(time.time())
            cmd = ['sed', '-i', '1s/(\(.*\))/(%s:\\1%s)/' % (timestamp, self.config.suffix),
                   osp.join(self.origpath, 'debian', 'changelog')]
            try:
                check_call(cmd, stdout=sys.stdout) #, stderr=sys.stderr)
            except CalledProcessError, err:
                raise LGPCommandException("bad substitution for version field", err)

        return self.origpath


    def get_basetgz(self, distrib, arch, check=True):
        basetgz = osp.join(self.config.basetgz, "%s-%s.tgz" % (distrib, arch))
        if check and not osp.exists(basetgz):
            raise LGPException("lgp image '%s' not found. Please create it with lgp setup" % basetgz)
        return basetgz
