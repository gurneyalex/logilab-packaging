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
import os.path
import shutil
import logging
from string import Template
from distutils.core import run_setup
#from pkg_resources import FileMetadata
from subprocess import Popen, PIPE
from subprocess import check_call, CalledProcessError

from logilab.common.configuration import Configuration
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp, mv

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib import TextReporter
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException
from logilab.devtools.lgp.utils import get_distributions, get_architectures, cached

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
                 'help': "run silently without confirmation"
                }),
               ('distrib',
                {'type': 'csv',
                  'dest': 'distrib',
                  'default' : 'unstable',
                  'short': 'd',
                  'metavar': "<distribution>",
                  'help': "list of distributions (e.g. 'stable, unstable'). Use 'all' for automatic detection"
                }),
               ('arch',
                {'type': 'csv',
                 'dest': 'archi',
                 'default' : 'current',
                 'short': 'a',
                 'metavar' : "<architecture>",
                 'help': "build for the requested debian architectures only"
                }),
               ('pkg_dir',
                {'type': 'string',
                 'hide': True,
                 'dest': "pkg_dir",
                 'short': 'p',
                 'metavar' : "<project directory>",
                 'help': "set a specific project directory"
                }),
               ('no-color',
                {'action': 'store_true',
                 'default': not isatty,
                 'dest': "no_color",
                 'help': "print log messages without color"
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
                 'default': '/opt/buildd',
                 'dest': "basetgz",
                 'metavar' : "<pbuilder basetgz location>",
                 'help': "specifies the location of base.tgz used by pbuilder"
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
               ('known-distributions',
                {'type': 'csv',
                 'dest': 'known_distributions',
                 'hide': True,
                 'default' : ['oldstable', 'stable', 'unstable', 'testing',
                              'feisty', 'gutsy', 'hardy', 'intrepid', 'jaunty',
                             'dapper'],
                 'help': "List of hard-coded distributions"
                }),
               )
        if options:
            for opt in options:
                self.options += opt
        super(SetupInfo, self).__init__(options=self.options, **args)

        # Load the optional config files
        for config in ['/etc/lgp/lgprc', '~/.lgprc']:
            config = os.path.expanduser(config)
            if os.path.isfile(config):
                self.load_file_configuration(config)

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

        if self.config.dump_config:
            self.generate_config()
            sys.exit()

        # Go to package directory
        if self.config.pkg_dir is None:
            self.config.pkg_dir = os.path.abspath(self.arguments and self.arguments[0] or os.getcwd())
        try:
            os.chdir(self.config.pkg_dir)
        except OSError, err:
            raise LGPException(err)

        # print chroot information
        self.distributions = get_distributions(self.config.distrib,
                                               self.config.basetgz)
        logging.info("running for distribution(s): %s" % ', '.join(self.distributions))
        self.architectures = get_architectures(self.config.archi)
        logging.info("running for architecture(s): %s" % ', '.join(self.architectures))

        # Setup command can be run anywhere, so skip setup file retrieval
        if sys.argv[1] in ["setup", "login"]:
            return

        # FIXME
        if not hasattr(self, 'current_distrib'):
            self.current_distrib = 'unstable'

        # Guess the package format
        if self.config.setup_file == 'setup.py':
            # generic case for python project (distutils, setuptools)
            self._package = run_setup('./setup.py', None, stop_after="init")
        elif os.path.isfile('__pkginfo__.py'):
            # Logilab's specific format
            self._package = PackageInfo(reporter=TextReporter(sys.stderr, sys.stderr.isatty()),
                                        directory=self.config.pkg_dir)
        # Other script can be used if compatible with the expected targets in COMMANDS
        elif os.path.isfile(self.config.setup_file):
            self._package = file(self.config.setup_file)
            if not os.stat(self.config.setup_file).st_mode & stat.S_IEXEC:
                raise LGPException('setup file %s has no execute permission'
                                   % self.config.setup_file)
        else:
            raise LGPException('no valid setup file (expected: %s)'
                               % self.config.setup_file)

        logging.debug("guess the setup package class: %s" % self.package_format)
        self.get_upstream_name()
        self.get_upstream_version()

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
                                      % cmd, process)
        return pipe

    def get_debian_dir(self):
        """get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian' is for unstable distribution
        - 'debian.$OTHER' id for $OTHER distribution and if it exists
        """
        debiandir = 'debian' # standard
        # developper can create an overlay for the debian directory
        if self.current_distrib != 'unstable':
            new_debiandir = '%s.%s' % (debiandir, self.current_distrib)
            if os.path.isdir(os.path.join(self.config.pkg_dir, new_debiandir)):
                debiandir = new_debiandir
        return debiandir

    def get_debian_name(self):
        """obtain the debian package name

        The information is found in debian/control withe the 'Source:' field
        """
        try:
            control = os.path.join(self.config.pkg_dir, 'debian', 'control')
            for line in open(control):
                line = line.split(' ', 1)
                if line[0] == "Source:":
                    return line[1].rstrip()
        except IOError, err:
            raise LGPException('a Debian control file should exist in "%s"' % control)

    def get_debian_version(self):
        """get upstream and debian versions depending of the last changelog entry found in Debian changelog

           We parse the dpkg-parsechangelog output instead of changelog file
           Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        cwd = os.getcwd()
        os.chdir(self.config.pkg_dir)
        try:
            changelog = os.path.join(self.get_debian_dir(), 'changelog')
            try:
                cmd = 'dpkg-parsechangelog'
                if os.path.isfile(changelog):
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

    def check_debian_revision(self):
        # http://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
        try:
            debian_revision = self.get_debian_version().rsplit('-', 1)[1]
        except IndexError:
            logging.warn("The absence of a debian_revision is equivalent to a debian_revision of 0.")
            debian_revision = "0"

        if debian_revision == '0':
            logging.info("It is conventional to restart the debian_revision"
                         " at 1 each time the upstream_version is increased.")

        if debian_revision not in ['0', '1']:
            logging.critical('unable to build %s package for the Debian revision "%s"'
                             % (self.get_debian_name(), debian_revision))
            raise LGPException('--orig-tarball option is required when you don\'t'\
                               'build the first revision of a debian package.\n' \
                               'If you haven\'t the original tarball version, ' \
                               'please do an apt-get source of the Debian source package.')

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
        logging.debug("don't forget to track vcs tags if in use")
        if upstream_version != debian_upstream_version:
            logging.info("version provided by upstream is '%s'" % upstream_version)
            logging.info("upstream version read from Debian changelog is '%s'" % debian_upstream_version)
            logging.warn('please check coherence of the previous version numbers')

    def clean_repository(self):
        """Clean the project repository"""
        self._run_command('clean')
        logging.info("clean repository")

    def make_orig_tarball(self):
        """make upstream and debianized tarballs in a dedicated directory"""
        dist_dir = os.path.dirname(self.get_distrib_dir())
        fileparts = (self.get_upstream_name(), self.get_upstream_version())
        # directory containing the debianized source tree
        # (i.e. with a debian sub-directory and maybe changes to the original files)
        # origpath is depending of the upstream convention
        origpath = os.path.join(self._tmpdir, "%s-%s" % fileparts)
        tarball = '%s_%s.orig.tar.gz' % fileparts
        upstream_tarball = '%s-%s.tar.gz' % fileparts

        if self.config.orig_tarball is None:
            copy_command = mv
            logging.info("create a new source archive (tarball) from upstream release")
            try:
                self.check_debian_revision()
                self._run_command("sdist", dist_dir=self._tmpdir)
            except CalledProcessError, err:
                logging.error("creation of the source archive failed")
                logging.error("check if the version '%s' is really tagged in"\
                                  " your repository" % self.get_upstream_version())
                raise LGPCommandException("source distribution wasn't properly built", err)
            upstream_tarball = os.path.join(self._tmpdir, upstream_tarball)
        else:
            copy_command = cp
            expected = [upstream_tarball, tarball]
            if os.path.basename(self.config.orig_tarball) not in expected:
                logging.error("the provided archive hasn't one of the expected formats (%s)"
                              % ','.join(expected))
            upstream_tarball = os.path.abspath(os.path.expanduser(self.config.orig_tarball))
            logging.info("use provided archive '%s' as original source archive (tarball)"
                         % upstream_tarball)

        assert os.path.isfile(upstream_tarball), 'original source archive (tarball) not found'

        # exit if asked by command-line
        if self.config.get_orig_source:
            try:
                cp(upstream_tarball, tarball)
                logging.info('a new original source archive (tarball) in current directory (%s)'
                             % tarball)
                # clean tmpdir
                self.clean_tmpdir()
                sys.exit()
            except shutil.Error, err:
                raise LGPException(err)

        # dpkg-source expects the  original source as a tarfile
        # by default: package_upstream-version.orig.tar.extension
        logging.debug("rename '%s' to '%s'" % (upstream_tarball, tarball))
        tarball = os.path.join(self._tmpdir, tarball) # rewrite with absolute path
        copy_command(upstream_tarball, tarball)

        # test and extracting the .orig.tar.gz
        try:
            cmd = 'tar xzf %s -C %s' % (tarball, self._tmpdir)
            check_call(cmd.split(), stdout=sys.stdout,
                                    stderr=sys.stderr)
        except CalledProcessError, err:
            raise LGPCommandException('an error occured while extracting the '
                                      'upstream tarball', err)

        logging.info("extract original source archive in %s" % self._tmpdir)
        return(upstream_tarball, tarball, origpath)

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
