#!/usr/bin/env python
# Copyright (c) 2003-2005 LOGILAB S.A. (Paris, FRANCE).
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
"""USAGE: checkpackage [OPTIONS]

Check a package: correctness of __pkginfo__.py, release number consistency,
MANIFEST.in matches what is int the directory, scripts in bin have a --help
option and .bat equivalent, execute tests, setup.py matches devtools template,
announce matches template too.

OPTIONS:
  -h / --help
       display this help message and exit.
       
  -d / --package-dir <DIRECTORY>
       package directory. Default to current working directory
       
  -i / --package -info <INFOMODULE>
       module where the packaging information may be found. Default to
       __pkginfo__.

  -x / --exclude <CHECK>
       do not perform that check (can't be used with '-o')

  -o / --only <CHECK>
       perform only that check (can't be used with '-x')
"""

__revision__ = '$Id: check_package.py,v 1.25 2005-06-20 10:35:21 syt Exp $'

import sys
import getopt
import os
import stat
import re
import commands
from os.path import basename, join, exists

from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PackageInfo, check_info_module
from logilab.devtools.lib.manifest import check_manifest_in
from logilab.devtools import templates

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
        reporter.log(WARNING, bat_file, None, msg)
        return status
    if data[-26:] == '%1 %2 %3 %4 %5 %6 %7 %8 %9':
        command = data[1:-26]
    elif data[-2:] == '%*':
        command = data[1:-2]
    else:
        command = data
        reporter.log(ERROR, bat_file, None, "forget arguments")
        status = 0
    error = os.popen3('%s --help' % command)[2].read()
    if error:
        reporter.log(ERROR, bat_file, None,
                     "error while executing (%s):\n%s"%(command, error))
        status = 0
    return status

def check_sh(reporter, sh_file):
    """try to check executable script files
    """
    status = 1
    data = open(sh_file).read()
    if data[:2] != '#!':
        reporter.log(ERROR, sh_file, None, 'Script doesn\'t starts with "#!"')
        status = 0
    if not is_executable(sh_file):
        make_executable(sh_file)
    cmd = '%s --help' % sh_file
    cmdstatus, output = commands.getstatusoutput(cmd)
    if cmdstatus:
        reporter.log(ERROR, sh_file, None,
                     '%r returned status %s, ouput:\n%s' % (cmd, cmdstatus, output))
        status = 0
    return status

def check_template(reporter, filename, templatename):
    """check a file is similar to a reference template
    """
    if not exists(filename):
        reporter.log(WARNING, filename, None, 'Missing file')
        return 0
    template = open(join(templates.__path__[0], templatename)).read()
    template = REV_LINE.sub('', template)
    actual = open(filename).read()
    actual = REV_LINE.sub('', actual)
    if actual != template:
        reporter.log(WARNING, filename, None, 'Does not match the template')
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
        if filename in ('CVS', '.svn'):
            continue
        if filename[-4:] == '.bat':
            continue
        sh_file = join(bindir, filename)
        bat_file = sh_file + '.bat'
        if not exists(bat_file):
            reporter.log(WARNING, bindir, None,
                         'No %s file' % basename(bat_file))
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
        reporter.log(WARNING, dirname, None,
                     'No test directory')
        return 1
    if not exists(join(test_dir, 'runtests.py')):
        reporter.log(WARNING, join(basename(test_dir), 'runtests.py'), None,
                     'Missing file')
    return 1

def normalize_version(version):
    """remove trailing .0 in version if necessary (i.e. 1.1.0 -> 1.1,
    2.0.0 -> 2)
    """
    while version.endswith('.0'):
        version = version[:-2]
    return version

def check_release_number(reporter, dirname, info_module='__pkginfo__'):
    """Check inconsistency with release number
    """
    from logilab.devtools.lib.changelog import ChangeLog, ChangeLogNotFound, \
         find_ChangeLog
    pi = PackageInfo(reporter, dirname, info_module=info_module)
    version = normalize_version(pi.version)
    status = 1
    try:
        cl_version = ChangeLog(find_ChangeLog(dirname)).get_latest_revision()
        cl_version = normalize_version(cl_version)
        if cl_version != version:
            msg = 'Version inconsistency : found %s in ChangeLog \
(reference is %s)'
            reporter.log(ERROR, 'ChangeLog', None, msg % (cl_version, version))
            status = 0
    except ChangeLogNotFound:
        reporter.log(WARNING, 'ChangeLog', None, 'Missing file')
    if exists(join(dirname, 'debian')):
        if not exists(join(dirname, 'debian', 'changelog')):
            reporter.log(ERROR, 'debian/changelog', None, 'Missing file')
            status = 0
        else:
            deb_version = pi.debian_version()
            deb_version = normalize_version(deb_version.split('-', 1)[0])
            if deb_version != version:
                msg = 'Version inconsistency : found %s in debian/changelog \
(reference is %s)'
                reporter.log(ERROR, 'debian/changelog', None, msg % (deb_version,
                                                                     version))
                status = 0
    return status

REPORTER = TextReporter()


def run(args=None):
    """main function to execute check package from command line"""
    # /!\ import Set here since we want check_package to be usable as a
    # /!\ library with python 2.2
    from sets import Set
    if args is None:
        args = sys.argv[1:]
    s_opts = 'hd:i:x:o:'
    l_opts = ['help', 'package-dir=', 'package-info=', 'exclude=', 'only=']
    opts, args = getopt.getopt(args, s_opts, l_opts)
    package_dir = os.getcwd()
    package_info = '__pkginfo__'
    excludes = Set()
    only = Set()
    for opt, val in opts:
        if opt in ('-h', '--help'):
            print __doc__
            return 0
        elif opt in ('--package-dir', '-d'):
            package_dir = val
        elif opt in ('--package-info', '-i'):
            package_info = val
        elif opt in ('--exclude', '-x'):
            excludes.add(val)
        elif opt in ('--only', '-o'):
            only.add(val)
    # check for command line consistency
    if excludes and only:
        print "--exclude and --only can't be used together"
        return 1
    # check args
    if args:
        print __doc__
        return 1
    checks = {
        'info_module' : check_info_module,
        'release_number' : check_release_number,
        'manifest_in' : check_manifest_in,
        'bin' : check_bin,
        'test' : check_test,
        'setup_py' : check_setup_py,
        'announce' : check_announce,
        }
    if only:
        to_test = only
    else:
        to_test = Set(checks) - excludes
    for name in to_test:
        check_func = checks[name]
        try:
            check_func(REPORTER, package_dir, package_info)
        except TypeError:
            check_func(REPORTER, package_dir)
    
    return REPORTER.counts[ERROR]

if __name__ == '__main__':
    run(sys.argv[1:])

    
__all__ = ('check_info_module', 'check_release_number', 'check_manifest_in',
           'check_bin', 'check_test', 'check_setup_py', 'check_announce')
