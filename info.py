# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
"""You should use grep instead
"""

import sys

from logilab.common.textutils import normalize_text
from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PKGINFO, PKGINFO_ATTRIBUTES
from logilab.devtools.lib.pkginfo import PackageInfo

    
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

def print_list(values=()):
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
    parser.usage = "lgp info [options] <args>"
    parser.add_option("-f", "--field", help="print field value read from package info")
    parser.add_option("--list", action="store_true", default=False,
                      help="list all pkginfo fields")
    parser.max_args = 1


def run(pkgdir, options, args):
    """extract package info according to command line arguments
    """
    if options.list:
        print_list()
    elif options.field:
        try:
            out = sys.stderr
            reporter = TextReporter(out, color=out.isatty())
            pi = PackageInfo(reporter, pkgdir)
            dump_values(pi, [options.field])
        except ImportError:
            sys.stderr.write("%r does not appear to be a valid package " % pkgdir)
            sys.stderr.write("(no __pkginfo__ found)\n")
            return 1
    return 0
