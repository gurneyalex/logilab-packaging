# -*- encoding: iso-8859-15 -*-

import sys
from optparse import OptionParser as OP

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


class OptionParser(OP):

    def __init__(self, *args, **kwargs):
        OP.__init__(self, *args, **kwargs)
        self._commands = {}
        self.min_args, self.max_args = 0, 0
        
    def add_command(self, name, module, help=''):
        self._commands[name] = (module, help)

    def parse_command(self, args):
        if len(args) == 0:
            self.error('no command given')
        cmd = args[0]
	args = args[1:]
        if cmd not in self._commands:
            if cmd in ('-h', '--help'):
                self.print_help()
                print '\ncommands:'
                for cmdname, (_, help) in self._commands.items():
                    print '% 10s - %s' % (cmdname, help)
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
    parser.usage = 'lgp COMMAND [options] <arg> ...'
    COMMANDS = [('prepare', 'logilab.devtools.preparedist',
                 'process to prepare distrib'),
                ('build', 'logilab.devtools.buildpackage',
                 'build debian and source packages'),
                ('tag', 'logilab.devtools.tagpackage',
                 'tag package repository'),
                ('check', 'logilab.devtools.checkpackage',
                 'check that package is ready to be built'),
                ('info', 'logilab.devtools.pkginfo',
                 'extract info from __pkginfo__'),
                ]
    for item in COMMANDS:
        parser.add_command(*item)
    run, options, args = parser.parse_command(sys.argv[1:])
    return run(options, args)

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))

