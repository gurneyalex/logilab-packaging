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
import os.path
import os
import glob
import logging
import rfc822
import commands
from distutils.core import run_setup
from subprocess import Popen, PIPE
try:
    from subprocess import check_call, CalledProcessError # only python2.5
except ImportError:
    from logilab.common.compat import check_call, CalledProcessError

from logilab.common.configuration import Configuration
from logilab.common.logging_ext import ColorFormatter
from logilab.common.shellutils import cp

from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lgp.exceptions import LGPException, LGPCommandException

LOG_FORMAT='%(levelname)1.1s:%(name)s: %(message)s'
COMMANDS = {
        "sdist" : {
            "pkginfo": 'python setup.py -q sdist --force-manifest -d %s',
            "setuptools": 'python setup.py sdist -d %s',
            "makefile": 'make -f setup.mk dist-gzip -e DIST_DIR=%s',
        },
        "clean" : {
            "pkginfo": 'fakeroot debian/rules clean',
            "setuptools": 'fakeroot debian/rules clean',
            "makefile": 'make -f setup.mk clean',
        },
}

class SetupInfo(Configuration):
    """ a setup class to handle several package setup information """
    _package_format = None

    def __init__(self, arguments, options=None, **args):
        isatty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        self.options = (
               ('version',
                {'help': "output version information and exit"
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
               ('pkg_dir',
                {'type': 'string',
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
                 'dest': "dump_config",
                 'help': "dump lgp configuration (debugging purpose)"
                }),
               )
        if options:
            for opt in options:
                self.options += opt
        super(SetupInfo, self).__init__(options=self.options, **args)

        # Instanciate the default logger configuration
        if not logging.getLogger().handlers:
            logging.getLogger().name = sys.argv[1]
            logging.getLogger().setLevel(logging.INFO)
            console = logging.StreamHandler()
            if self.config.no_color or not isatty:
                console.setFormatter(logging.Formatter(LOG_FORMAT))
            else:
                console.setFormatter(ColorFormatter(LOG_FORMAT))
            logging.getLogger().addHandler(console)
            if self.config.verbose:
                logging.getLogger().setLevel(logging.DEBUG)

        # Version information
        if self.config.version:
            from logilab.devtools.__pkginfo__ import version, distname, copyright
            print "lgp (%s) %s\n%s" % (distname, version, copyright)
            sys.exit()

        # Load the optional config files
        for config in ['/etc/lgp/lgprc', '~/.lgprc']:
            config = os.path.expanduser(config)
            if os.path.isfile(config):
                #logging.debug('loading lgp configuration found in %s...' % config)
                self.load_file_configuration(config)

        # Manage arguments (project path essentialy)
        self.arguments = self.load_command_line_configuration(arguments)

        if self.config.dump_config:
            self.generate_config()
            sys.exit()

        # Go to package directory
        if self.config.pkg_dir is None:
            self.config.pkg_dir = os.path.abspath(self.arguments and self.arguments[0] or os.getcwd())
        os.chdir(self.config.pkg_dir)

        if os.path.isfile('__pkginfo__.py'):
            self._package_format = 'pkginfo'
            self._package = PackageInfo(directory=self.config.pkg_dir)
        elif os.path.isfile('setup.py'):
            self._package_format = 'setuptools'
            self._package = run_setup('./setup.py', None, stop_after="init")
        elif os.path.isfile('setup.mk'):
            self._package_format = 'makefile'
        elif sys.argv[1] == "setup":
            pass
        else:
            raise LGPException('no valid setup file (setup.py or setup.mk)')
        logging.debug("guess the package format: %s" % self._package_format)

    def get_debian_name(self):
        """ obtain the debian package name

        The information is found in debian*/control withe the 'Source:' field
        """
        try:
            path = os.path.join(self.config.pkg_dir, self.get_debian_dir())
            for line in open('%s/control' % path):
                line = line.split(' ', 1)
                if line[0] == "Source:":
                    return line[1].rstrip()
        except IOError, err:
            raise LGPException('a Debian control file is required in "%s"' % path)

    def get_debian_dir(self):
        """ get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian/' is for unstable distribution
        - 'debian.$OTHER/' id for $OTHER distribution and if it exists
        """
        if self.config.distrib != 'unstable':
            debiandir = 'debian.%s/' % self.config.distrib
            if os.path.isdir(os.path.join(self.config.pkg_dir, debiandir)):
                return debiandir
        return 'debian/'

    def get_debian_version(self):
        """ get the debian version depending of the last changelog entry

            Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        cwd = os.getcwd()
        os.chdir(self.config.pkg_dir)
        try:
            status, output = commands.getstatusoutput('dpkg-parsechangelog')
            if status != 0:
                msg = 'dpkg-parsechangelog exited with status %s' % status
                raise LGPException(msg)
            for line in output.split('\n'):
                line = line.strip()
                if line and line.startswith('Version:'):
                    return line.split(' ', 1)[1].strip()
            raise LGPException('Debian version not found')
        finally:
            os.chdir(cwd)

    def get_upstream_name(self):
        # FIXME
        if self._package_format == 'makefile':
            p1 = Popen(["make", "-f", "setup.mk", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^\(PROJECT\|NAME\)"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        elif hasattr(self._package, 'get_name'):
            return self._package.get_name()
        elif self._package_format == 'pkginfo':
            try:
                from __pkginfo__ import distname
            except ImportError:
                from __pkginfo__ import modname
                distname = modname
            return distname

    def get_upstream_version(self):
        if self._package_format == 'pkginfo':
            from __pkginfo__ import version
            return version
        elif self._package_format == 'makefile':
            p1 = Popen(["make", "-f", "setup.mk", "-p"], stdout=PIPE)
            p2 = Popen(["grep", "^VERSION"], stdin=p1.stdout, stdout=PIPE)
            output = p2.communicate()[0]
            return output.rsplit()[2]
        else:
            return self._package.get_version()

    def get_changes_file(self):
        changes = '%s_%s_*.changes' % (self.get_debian_name(), self.get_debian_version())
        changes = glob.glob(os.path.join(self.get_distrib_dir(), changes))
        return changes[0]

    def get_packages(self):
        packages = rfc822.Message(file(self.get_changes_file()))
        packages = [a.split()[-1] for a in packages['Files'].split('\n')]
        packages.append(self.get_changes_file())
        return packages

    def compare_versions(self):
        upstream_version = self.get_upstream_version()
        debian_upstream_version = self.get_debian_version().rsplit('-', 1)[0]
        logging.debug("don't forget to track vcs tags if in use")
        logging.info("version provided by upstream is '%s'" % upstream_version)
        logging.info("upstream version provided by Debian changelog is '%s'" % debian_upstream_version)
        if upstream_version != debian_upstream_version:
            raise LGPException('please check coherence of the previous version numbers')

    def clean_repository(self):
        """Clean the project repository"""
        if self._package_format in COMMANDS["clean"]:
            # FIXME rewrite the os.system() call
            cmd = COMMANDS["clean"][self._package_format]
            if not self.config.verbose:
                cmd += ' 1>/dev/null 2>/dev/null'
            logging.debug("cleaning repository...")
            os.system(cmd)
        else:
            logging.error("no way to clean the repository...")

    def create_orig_tarball(self, tmpdir):
        """Create an origin tarball"""
        tarball = os.path.join(tmpdir, '%s_%s.orig.tar.gz' %
                    (self.get_upstream_name(), self.get_upstream_version()))
        if self.config.orig_tarball is None:
            logging.debug("creating a new source archive (tarball)...")
            dist_dir = os.path.dirname(self.get_distrib_dir())

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
                raise LGPException('--orig-tarball option is required when '\
                                   'not building the first revision of a debian package.\n' \
                                   'If you haven\'t the original tarball version, ' \
                                   'please do an apt-get source of the Debian source package.')
            if self._package_format in COMMANDS["sdist"]:
                cmd = COMMANDS["sdist"][self._package_format] % dist_dir
            else:
                raise LGPException("no way to create the source archive (tarball)")

            try:
                check_call(cmd.split(), stdout=sys.stdout, stderr=sys.stderr)
            except CalledProcessError, err:
                logging.error("creation of the source archive failed")
                logging.error("check if the version '%s' is really tagged in"\
                                  " your repository" % self.get_upstream_version())
                raise LGPCommandException("source distribution wasn't properly built", err)

            upstream_tarball = os.path.join(dist_dir, '%s-%s.tar.gz'
                                            % (self.get_upstream_name(), self.get_upstream_version()))
        else:
            upstream_tarball = self.config.orig_tarball
            expected = '%s-%s.tar.gz' % (self.get_upstream_name(), self.get_upstream_version())
            if os.path.basename(upstream_tarball) != expected:
                logging.error("the provided tarball (%s) has not the expected filename (%s)"
                              % (os.path.basename(upstream_tarball), expected))
                raise LGPException('rename manually your file for sanity')

        if os.path.isfile(upstream_tarball):
            logging.info("use '%s' as original source archive (tarball)" % upstream_tarball)
        else:
            raise LGPException('the original source archive (tarball) in not found in %s' % dist_dir)

        logging.debug("copy '%s' to '%s'" % (upstream_tarball, tarball))
        cp(upstream_tarball, tarball)

        return tarball
