#!/usr/bin/env python
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

"""Check a package: correctness of __pkginfo__.py, release number
consistency, MANIFEST.in matches what is int the directory, scripts in
bin have a --help option and .bat equivalent, execute tests, setup.py
matches devtools template, announce matches template too.
"""

__all__ = ('check_info_module', 'check_release_number', 'check_manifest_in',
           'check_bin', 'check_test', 'check_setup_py', 'check_announce')

import sys
import os
import stat
import re
import commands
from os.path import basename, join, exists, isdir

from logilab.common.compat import set

from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PackageInfo, check_info_module
from logilab.devtools.lib.manifest import check_manifest_in
from logilab.devtools.vcslib import BASE_EXCLUDE
from logilab.devtools import templates
from logilab.devtools.lib.changelog import ChangeLog, ChangeLogNotFound, \
     find_ChangeLog

def is_executable(filename):
    """return true if the file is executable"""
    mode = os.stat(filename)[stat.ST_MODE]
    return mode & stat.S_IEXEC

def make_executable(filename):
    """make a file executable for everybody"""
    mode = os.stat(filename)[stat.ST_MODE]
    os.chmod(filename, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    

def check_bat(reporter, bat_file):
    """try to check windows .bat files
    """
    status = 1
    f = open(bat_file)
    data = f.read().strip()
    if not data[:11] == '@python -c ':
        msg = "unrecognized command %s" % data[:11]
        reporter.warning(bat_file, None, msg)
        return status
    if data[-26:] == '%1 %2 %3 %4 %5 %6 %7 %8 %9':
        command = data[1:-26]
    elif data[-2:] == '%*':
        command = data[1:-2]
    else:
        command = data
        reporter.error(bat_file, None, "forget arguments")
        status = 0
    error = os.popen3('%s --help' % command)[2].read()
    if error:
        reporter.error(bat_file, None,
                       "error while executing (%s):\n%s"%(command, error))
        status = 0
    return status

def check_sh(reporter, sh_file):
    """try to check executable script files
    """
    status = 1
    data = open(sh_file).read()
    if data[:2] != '#!':
        reporter.error(sh_file, None, 'Script doesn\'t starts with "#!"')
        status = 0
    if not is_executable(sh_file):
        make_executable(sh_file)
    cmd = '%s --help' % sh_file
    cmdstatus, output = commands.getstatusoutput(cmd)
    if cmdstatus:
        reporter.error(sh_file, None,
                       '%r returned status %s, ouput:\n%s' % (cmd, cmdstatus, output))
        status = 0
    return status

def check_template(reporter, filename, templatename):
    """check a file is similar to a reference template
    """
    if not exists(filename):
        reporter.warning(filename, None, 'Missing file')
        return 0
    template = open(join(templates.__path__[0], templatename)).read()
    template = REV_LINE.sub('', template)
    actual = open(filename).read()
    actual = REV_LINE.sub('', actual)
    if actual != template:
        reporter.warning(filename, None, 'Does not match the template')
    return 1


###############################################################################
        
def check_bin(reporter, dirname):
    """Checking scripts in the 'bin' directory
    """
    status = 1
    bindir = join(dirname, 'bin')
    if not exists(bindir):
        return status
    for filename in os.listdir(bindir):
        if filename in BASE_EXCLUDE:
            continue
        if filename[-4:] == '.bat':
            continue
        sh_file = join(bindir, filename)
        bat_file = sh_file + '.bat'
        if not exists(bat_file):
            reporter.warning(bindir, None, 'No %s file' % basename(bat_file))
        elif filename[-4:] == '.bat':
            _status = check_bat(reporter, bat_file )
            status = status and _status
        _status = check_sh(reporter, sh_file)
        status = status and _status
    return status

REV_LINE = re.compile('__revision__.*')
    
def check_setup_py(reporter, dirname):
    """Checking the setup.py file
    """
    return check_template(reporter, join(dirname, 'setup.py'), 'setup.py')
    
def check_announce(reporter, dirname):
    """Checking the announce.txt file
    """
    check_template(reporter, join(dirname, 'announce.txt'), 'announce.txt')
    return 1

def check_test(reporter, dirname):
    """Checking the test directory
    """
    for test_dir_name in ('test', 'tests'):
        if exists(join(dirname, test_dir_name)):
            test_dir = join(dirname, test_dir_name)
            break
    else:
        reporter.warning(dirname, None, 'No test directory')
        return 1
    #if not exists(join(test_dir, 'runtests.py')):
    #    reporter.warning(join(basename(test_dir), 'runtests.py'), None,
    #                    'Missing file')
    return 1

def normalize_version(version):
    """remove trailing .0 in version if necessary (i.e. 1.1.0 -> 1.1,
    2.0.0 -> 2)
    """
    while version and version[-1] == 0:
        version = version[:-1]
    return version

def check_release_number(reporter, dirname, info_module='__pkginfo__'):
    """Check inconsistency with release number
    """
    try:
        pi = PackageInfo(reporter, dirname, info_module=info_module)
    except ImportError:
        return 0
    version = normalize_version(pi.version)
    status = 1
    try:
        cl_version = ChangeLog(find_ChangeLog(dirname)).get_latest_revision()
        cl_version = normalize_version(cl_version)
        if cl_version != version:
            msg = 'Version inconsistency : found %s in ChangeLog \
(reference is %s)'
            reporter.error('ChangeLog', None, msg % (cl_version, version))
            status = 0
    except ChangeLogNotFound:
        reporter.warning('ChangeLog', None, 'Missing file')
    if exists(join(dirname, 'debian')):
        if not exists(join(dirname, 'debian', 'changelog')):
            reporter.error('debian/changelog', None, 'Missing file')
            status = 0
        else:
            deb_version = pi.debian_version()
            deb_version = normalize_version(deb_version.split('-', 1)[0])
            if deb_version != version:
                msg = 'Version inconsistency : found %s in debian/changelog \
(reference is %s)'
                reporter.error('debian/changelog', None,
                               msg % (deb_version, version))
                status = 0
    return status

DEFAULT_CHECKS = ('info_module', 'release_number', 'manifest_in',
                  'bin', 'test', 'setup_py', 'announce')


CHECKERS = dict([(name, value) for name, value in globals().items()
                 if name.startswith('check_') and name[6:] in DEFAULT_CHECKS and callable(value)])

def start_checks(package_dir, package_info='__pkginfo__', checks=DEFAULT_CHECKS):
    reporter = TextReporter(color=sys.stdout.isatty())
    for check in checks:
        try:
            check_func = CHECKERS['check_%s' % check]
        except KeyError:
            reporter.warning(None, None, 'skipping invalid check: %r' % check)
            continue
        try:
            check_func(reporter, package_dir, package_info)
        except TypeError:
            check_func(reporter, package_dir)
    return reporter.errors



def add_options(parser):
    parser.usage = "lgp check [options] <package>"
    parser.description += ". Available checks: %s" % ', '.join(DEFAULT_CHECKS)
    parser.add_option('-i', '--package-info', default='__pkginfo__',
                      help='module where the packaging information may be found',
                      metavar='<INFOMODULE>')
    parser.add_option('-x', '--exclude', action="append", dest="exclude", 
                      help="do not perform that check (can't be used with '-o')",
                      metavar='<CHECK>', default=[])
    parser.add_option('-o', '--only', action="append", dest="only",
                      help="perform only that check (can't be used with '-x')",
                      metavar='<CHECK>', default=[])
    parser.max_args = 1


def run(pkgdir, options, args):
    """main function to execute check package from command line"""
    debdir = join(pkgdir, 'debian')
    if not isdir(debdir):
        print >> sys.stderr, "invalid package: no directory %r" % debdir
        return 1

    if options.exclude and options.only:
        print "--exclude and --only can't be used together"
        return 1
    to_test = options.only or (set(DEFAULT_CHECKS) - set(options.exclude))
    return start_checks(pkgdir, options.package_info, to_test)

    
