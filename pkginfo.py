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
    parser.usage = 'lgp info [options] <args>'
    parser.add_option("--dump", help="dump package info")
    parser.add_option("--check", action="store_true", default=False,
                      help="check module info")
    parser.max_args = 1


def run(options, args):
    """extract package info according to command line arguments
    """
    package_dir = args and args[0] or os.getcwd()
    if options.check:
        REPORTER.reset()
        return check_info_module(REPORTER, package_dir)
    elif options.dump:
        try:
            pi = PackageInfo(REPORTER, package_dir)
            dump_values(pi, [options.dump])
        except ImportError:
            sys.stderr.write("%r does not appear to be a valid package " % package_dir)
            sys.stderr.write("(no __pkginfo__ found)\n")
            return 1
    return 0
