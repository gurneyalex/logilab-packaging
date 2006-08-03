# -*- encoding: iso-8859-15 -*-
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

import sys
import os, os.path as osp
import optparse

## class Command:

##     def __init__(self, module=None, run=None, add_opt=None):
##         self.module = module
##         self.run = run
##         self.add_options = add_opt

##     def get_(self):
##         if self.module:
##             exec('from %s import run, add_options'%self.module)
##             return run, add_options:
##         else:
##             return self.run, self.add_options


class OptionParser(optparse.OptionParser):

    def __init__(self, *args, **kwargs):
        optparse.OptionParser.__init__(self, *args, **kwargs)
        self._commands = {}
        self.min_args, self.max_args = 0, 0
        
    def add_command(self, name, module, help=''):
        self._commands[name] = (module, help)


    def print_main_help(self):
        optparse.OptionParser.print_help(self)
        print '\ncommands:'
        for cmdname, (_, help) in self._commands.items():
            print '% 10s - %s' % (cmdname, help)
        

    def parse_command(self, args):
        if len(args) == 0:
            self.print_main_help()
            sys.exit(1)
        cmd = args[0]
	args = args[1:]
        if cmd not in self._commands:
            if cmd in ('-h', '--help'):
                self.print_main_help()
                sys.exit(0)
            self.error('unknow command')
        self.prog = '%s %s' % (self.prog, cmd)
        module, help = self._commands[cmd]
        # optparse inserts self.description between usage and options help
        self.description = help
        exec('from %s import run, add_options'%module)
        add_options(self)
        (options, args) = self.parse_args(args)        
        if not (self.min_args <= len(args) <= self.max_args):
            self.error('incorrect number of arguments')
        return run, options, args


def run(args):
    parser = OptionParser()
    parser.usage = 'lgp COMMAND [options] <pkgdir> ...'
    COMMANDS = [('prepare', 'logilab.devtools.preparedist',
                 'process to prepare distrib'),
                ('build', 'logilab.devtools.buildpackage',
                 'build debian and source packages'),
                ('tag', 'logilab.devtools.tagpackage',
                 'tag package repository'),
                ('check', 'logilab.devtools.checkpackage',
                 'check that package is ready to be built'),
                ('info', 'logilab.devtools.info',
                 'extract info from __pkginfo__'),
                ]
    for item in COMMANDS:
        parser.add_command(*item)
    run, options, args = parser.parse_command(sys.argv[1:])
    pkgdir = osp.abspath(args and args[0] or os.getcwd())
    return run(pkgdir, options, args[1:])

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))

