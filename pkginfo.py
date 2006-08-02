# Copyright (c) 2003-2005 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""USAGE:  pkginfo [OPTIONS] COMMAND [COMMAND ARGUMENTS]

package info command line tool.

COMMANDS:

  * check, check the package information file. Take no argument.
  
  * dump, dump some package information. Optionaly take a list of attribute to
    dump, else dump all the detected configuration.

  * help, get help for a list of variables from the package info. Optionaly
    take a list of attribute, else get help for all configuration variables.
    
OPTIONS:
  -h / --help
       display this help message and exit.
       
  -d / --package-dir <DIRECTORY>
       package directory. Default to current working directory
       
  -i / --package-info <INFOMODULE>
       module where the packaging information may be found. Default to
       __pkginfo__.
"""

__revision__ = "$Id: pkginfo.py,v 1.10 2005-07-26 09:41:12 syt Exp $"

import sys
import os
import getopt

from logilab.common.textutils import normalize_text
from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PKGINFO, PKGINFO_ATTRIBUTES, \
     PackageInfo, check_info_module

REPORTER = TextReporter(output=sys.stderr)

    
def dump_values(pkginfo, values):
    """dump a list of values from the package info
    dump everything in no specific attributes specifed
    """
    if values:
        print_arg_name = len(values) > 1
        for arg in values:
            try:
                value = getattr(pkginfo, arg)
                if callable(value):
                    value = value()
                if print_arg_name:
                    print '%s: ' % arg,
                print value
            except AttributeError:
                print 'No such attribute %s' % arg
    else:
        for cat, cat_def in PKGINFO:
            print cat
            print '=' * len(cat)
            for opt_def in cat_def:
                opt_name = opt_def['name']
                value = pkginfo.getattr(opt_name)
                if callable(value):
                    value = value()
                if not value:
                    continue
                
                print '%s: %s' % (opt_name, value)
            print

def help(values):
    """get help for a list of variables from the package info
    """
    if values:
        for arg in values:
            try:
                print '%s:' % arg, PKGINFO_ATTRIBUTES[arg]['help']
            except KeyError:
                print 'No such attribute %s' % arg
    else:
        print '__pkginfo__ variables description'
        print '================================='
        print
        print 
        for cat, cat_def in PKGINFO:
            print cat
            print '-' * len(cat)
            print
            for opt_def in cat_def:
                print opt_def['name'],
                if not opt_def.has_key('default'):
                    print '(required)'
                else:
                    print 
                    
                print normalize_text(opt_def['help'], indent='  ')
                print
            print


def add_options(parser):
    pass

def run(options, args):
    """extract package info according to command line arguments
    """
    opts, args = getopt.getopt(args, 'hd:i:', ['help', 'package-dir=',
                                               'package-info='])
    package_dir = os.getcwd()
    package_info = '__pkginfo__'
    for opt, val in opts:
        if opt in ('-h', '--help'):
            print __doc__
            return 0
        elif opt in ('--package-dir', '-d'):
            package_dir = val
        elif opt in ('--package-info', '-i'):
            package_info = val
    command = args[0]
    command_args = args[1:]
    if command == 'check':
        REPORTER.reset()
        return check_info_module(REPORTER, package_dir, package_info)
    elif command == 'dump':
        pi = PackageInfo(REPORTER, package_dir, package_info)
        dump_values(pi, command_args)
##     elif command == 'rest':
##         pi = PackageInfo(REPORTER, package_dir, package_info)
##         rest(pi)
    elif command == 'help':
        help(command_args)
    else:
        raise Exception('Unknown command "%s"' % command)
    return 0
    
if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
