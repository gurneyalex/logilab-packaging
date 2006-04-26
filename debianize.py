#!/usr/bin/env python
# Copyright (c) 2003-2004 LOGILAB S.A. (Paris, FRANCE).
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
"""Debianize a Python / Zope package

USAGE: debianize [OPTIONS] [package_dir]
          create / update debian files (debian mode). If no python versions are
          provided, default to 2.1 2.2 2.3 (on the first run). Used options are
          saved in a config file (debian/debianizerc) so you don't have to
          provide them on futur runs.
          The <python version> arguments is only used with the python-library
          handler.  
          
       debianize [OPTIONS] [package_dir] prepare 
          create a directory to build the package (prepare mode).

Both commands should be run in the root of the source package.

OPTIONS:
  -h / --help
       display this help message and exit.

  -o / --orig
       create a .orig.tar.gz (only in prepare mode).

EXAMPLE:
$ cd logilab/pyreverse
$ debianize 2.2 2.3
$ cd `debianize prepare --orig`
$ fakeroot make -f debian/rules binary
"""

__revision__ = '$Id: debianize.py,v 1.30 2004-11-10 12:02:12 syt Exp $'

import sys
import os
import getopt
from os.path import join

from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.debhdlrs import get_package_handler, replace, empty

REPORTER = TextReporter()
DEBIAN_DIR = 'debian'
    
def debianize(command='update', reporter=REPORTER,
              directory=None, orig=False,
              replace_func=replace, empty_func=empty):
    directory = directory or os.getcwd()
    pkginfo = PackageInfo(reporter, directory)
    pkghandler = get_package_handler(pkginfo, replace_func, empty_func)
    debian_dir = join(directory, DEBIAN_DIR)
    if command == 'update':
        pkghandler.update_debian_files(debian_dir)
    else: # command == 'prepare'
        print pkghandler.prepare_debian(orig)


def run(args):
    """debianize a package according to command line arguments"""
    orig = False
    directory = None
    options, args = getopt.getopt(args, 'ho', ['help', 'orig'])
    for option in options:
        if option[0] in ('-h', '--help'):
            print __doc__
            return
        if option[0] in ('-o', '--orig'):
            orig = True
    command = 'update'
    try:
        args.remove('update')
    except ValueError:
        pass
    if args:
        try:
            args.remove('prepare')
            command = 'prepare'
        except ValueError:
            command = 'update'
        if len(args) > 1:
            raise Exception('Too many arguments %s' % ' '.join(args[1:]))
        elif args:
            directory = args[0]
    print '*' * 80
    print 'creating/updating debian files'
    debianize(command, directory=directory, orig=orig)
        
if __name__ == '__main__':
    run(sys.argv[1:])
