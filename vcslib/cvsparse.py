# -*- coding: utf-8 -*-
# Copyright (c) 2002-2008 LOGILAB S.A. (Paris, FRANCE).
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
"""library to analyze cvs log
"""

import os
import re
from time import time, localtime, strftime

from logilab.common.tree import Node
from logilab.common.interface import Interface

TODAY = strftime("%Y/%m/%d", localtime(time()))


# base parser #################################################################

def parse(stream, line_handler):
    line_handler.init()
    unknowns = []
    start = 1
    for line in stream.readlines():
        if start is not None and line[0] == '?':
            unknowns.append(line[1:].strip())
        else:
            start = None
            line_handler.parse_line(line)
    line_handler.end()
    return unknowns

class ILineHandler(Interface):
    def init(self):
        """start parsing"""
    def end(self):
        """finished parsing"""
    def parse_line(self, line):
        """parse a content line"""


# "cvs status" output handler #################################################

class StatusLineHandler:
    __implements__ = ILineHandler

    def __init__(self, noup=1, mod_level=0):
        self.noup = noup
        self.mod_level = mod_level

    def init(self):
        self._current_file = ''

    def end(self):
        pass

    def parse_line(self, line):
        line = line.strip()
        if line[:6] == 'File: ':
            self._current_file = line[6:].split()[0]
            self._status = line[line.find('Status:')+8:]
        elif line[:17] == 'Working revision:':
            self._w_revision = line
        elif (line[:11] == 'Sticky Tag:' and
              line[-6:] != '(none)' and
              self._status != 'Up-to-date'):
            print line
        elif line[:20] == 'Repository revision:':
            s = line.split()
            cvs_file = s[-1][:-2]
            if self.mod_level:
                cvs_file = os.sep.join(cvs_file.split(os.sep)[1+self.mod_level:])
            if not self.noup or self._status != 'Up-to-date':
                print '--'
                if len(self._status) < 16:
                    tab = '\t\t'
                else:
                    tab = '\t'
                if self._status == 'Locally Added':
                    print '%s%s%s' % (self._status, tab, self._current_file)
                else:
                    print '%s%s%s' % (self._status, tab, cvs_file)
                print self._w_revision
                print '%s\t%s'% (' '.join(s[:2]), s[2])

DATE_FORMAT = '%Y/%m/%d %H:%M:%S'

# "cvs log" output handler #####################################################

# match "date: 2001/09/15 01:48:06;  author: molson;  state: Exp;"
#       "date: 2001/09/15 02:24:47;  author: molson;  state: Exp;  lines: +29 -0"
REV_DATE_RGX = re.compile('(?P<date>\d\d\d\d[-/]\d\d[-/]\d\d [^;]*);  \
author: (?P<author>[^;]*);  state: ([^;]*);(  lines: \+(?P<new>\d+) -(?P<removed>\d+))?')
#
REV_TOTAL_RGX = re.compile('(?P<total>\d+);\s+selected revisions: (?P<selected>\d+)')

class File(Node):
    """handle CVS file information"""
    def __init__(self):
        Node.__init__(self)
        self.working_file = None
        self.repo_file = None
        # total number of revisions in the repository. We only have those
        # selected by "cvs log" !
        self.total_rev = 0
        self.head = None
        self.branch = None
        self.keyword_substitution = None
        self.description = None
        self.symbolic_names = []

    def __str__(self):
        s = [ self.repo_file ]
        write = s.append
        if self.working_file:
            if self.branch:
                write('working file: %s (branch %s)' % (self.working_file, self.branch))
            else:
                write('working file: %s' % (self.working_file))

        if self.keyword_substitution:
            write('keywords: %s' % (self.keyword_substitution))
        write('head: %s'%self.head)
        write('total revisions: %s (%s selected)' % (self.total_rev, len(self.children)))
        if self.symbolic_names:
            write('symbolic names: %s' % (' '.join(self.symbolic_names)))
        if self.description:
            write('description: %s' % (self.description))
        return '\n'.join(s)

class Revision(Node):
    """handle a revision information for a file"""
    def __init__(self):
        Node.__init__(self)
        self.revision = None
        self.date = None
        self.author = None
        self.lines = (0, 0)
        self.initial = None
        self.branch = None
        self.message = []

    def __str__(self):
        if self.initial:
            s = [ '%s (%s, %s)' % (self.revision, self.author, self.date) ]
        else:
            s = [ '%s (%s, %s) +%s -%s' % (self.revision, self.author, self.date,
                                           self.lines[0], self.lines[1]) ]
        write = s.append
        if self.branch:
            write('branch: %s' % (self.branch))
        if self.message:
            s += self.message
        return '\n'.join(s)

PATTERN_INDEX = 0
STATE_INDEX = 1

FILE_STATE = 1
REVISION_STATE = 2

SDD = {
    FILE_STATE: (('-'*28, REVISION_STATE), ('='*77, FILE_STATE)),
    REVISION_STATE: (('='*77, FILE_STATE), ('-'*28, REVISION_STATE)),
    }

KEYWORDS = {
    FILE_STATE : ['RCS file', 'Working file', 'head', 'branch', 'locks',
                  'access list', 'symbolic names', 'start',
                  'keyword substitution', 'total revisions', 'description'],
    REVISION_STATE : ['revision', 'date', 'branch']
    }

def total_revisions(file, line):
    m = REV_TOTAL_RGX.match(line)
    file.total_rev = int(m.group('total'))

def symbolic_names(file, line):
    pass

def revision_date(revision, line):
    m = REV_DATE_RGX.match(line)
    assert m is not None, "%s doesn't match %s" % (line, REV_DATE_RGX.pattern)
    revision.author = m.group('author')
    # cvs date format differs according to cvs version, need normalisation (purpose of the .replace call)
    revision.date = m.group('date').replace('-', '/').split('+', 1)[0].strip()
    if m.group('new') is None:
        revision.initial = 1
    else:
        revision.lines = (int(m.group('new')), int(m.group('removed')))


ATTRS_MAP = {
    'RCS file' : 'repo_file',
    'Working file' : 'working_file',
    'access list' : 'access_list',
    'symbolic names' : symbolic_names,
    'keyword substitution' : 'keyword_substitution',
    'total revisions' : total_revisions,
    'date' : revision_date,
    }

class LogLineHandler:
    __implements__ = ILineHandler

    def init(self):
        self.root = []
        last = File()
        self.root.append(last)
        self._last = last
        self._state = FILE_STATE
        self._last_line = ''
        self._index = 0

    def set_next_state(self, line):
        """ check if the line trigger a transition
        if so, go to next state and return 1
        else return 0
        """
        for transition in SDD[self._state]:
            if line.startswith(transition[PATTERN_INDEX]):
                self._state = transition[STATE_INDEX]
                if self._state == FILE_STATE:
                    last = File()
                    self.root.append(last)
                else: # REVISION_STATE
                    last = Revision()
                    self.root[-1].append(last)
                self._index = 0
                self._last = last
                return 1
        return 0

    def parse_line(self, line):
        if self.set_next_state(line):
            # don't do anything on transition lines
            return

        for i in range(self._index, len(KEYWORDS[self._state])):
            keyword = KEYWORDS[self._state][i]
            if line.startswith(keyword):
                value = line[len(keyword)+1:].strip()
                try:
                    if callable(ATTRS_MAP[keyword]):
                        ATTRS_MAP[keyword](self._last, value)
                    else:
                        setattr(self._last, ATTRS_MAP[keyword], value)
                except KeyError:
                    setattr(self._last, keyword, value)
                self._index = i
                break
        else:
            if self._state == REVISION_STATE and self._index > 0:
                if line.strip() != '*** empty log message ***':
                    self._last.message.append(line[:-1])
            elif self._state == FILE_STATE and self._index == 6:
                self._last.symbolic_names.append(line.strip())
##             else:
##                 print self._state, 'IGNORE', line.strip()

    def end(self):
        self.root.pop()


# Output formatter ############################################################

class AbstractLogResultFormatter:
    """an abstract class for log result formatter"""
    def format(self, results):
        """render the log report"""
        self.print_title()#results['limit_date'])
        authors = results['authors'].keys()
        authors.sort()
        for author in authors:
            data = results['authors'][author]
            self.print_author_stats(author, data)
        self.print_end(results['winner'])

    def print_title(self):
        """print report title"""
        raise NotImplementedError()

    def print_author_stats(self, author, data):
        """print some statistics for a given author"""
        raise NotImplementedError()

    def print_end(self, winner):
        """close the report"""
        raise NotImplementedError()

class LogResultTextPrinter(AbstractLogResultFormatter):
    """a class rendering log result as plain text"""

    def print_title(self, limit_date=None):
        """print report title"""
        print '*'*80
        if limit_date is not None:
            print '\t\tCVS statistics from %s to %s\n' % (
                limit_date, TODAY)
        else:
            print '\t\tCVS statistics on %s\n' % (TODAY)
        print '-'*80
        print '\n'
        print '\t+---------------------------------------------------+'
        print '\t| Author | Commits |     Lines    | New |  Avg  | % |'

    def print_author_stats(self, author, data):
        """print some statistics for a given author"""
        data['s+'] = '+%i' % data['+']
        print '\t|---------------------------------------------------|'
        print '\t|%(author)-8s|%(commit)-9i|%(s+)-7s%(-)-7i|\
%(new)-5i|%(changedcommit)7i|%(%)3i|' % data
#print '\t%s%7s lines per commit' % (' '*28, '+%s'%(data['changedcommit']))

    def print_end(self, winner):
        """close the report"""
        print '\t+---------------------------------------------------+'
        print
        print 'Most frequent committer : %s' % winner
        print
        print '*'*80

class LogResultHTMLPrinter(AbstractLogResultFormatter):
    """a class rendering log result as HTML"""

    def print_title(self, limit_date=None):
        """print report title"""
        if limit_date is not None:
            print '<h1>CVS statistics from %s to %s</h1>' % (
                limit_date, TODAY)
        else:
            print '<h1>CVS statistics on %s</h1>' % (TODAY)
        print '<table colspacing="4" border="1" align="center"><tr>'
        print '<th>Author</th><th>Commits</th><th>Lines</th><th>New</th><th>Avg</th><th>%</th>'
        print '</tr>'

    def print_author_stats(self, author, data):
        """print some statistics for a given author"""
        data['s+'] = '+%i' % data['+']
        print '<tr align="center">'
        print '<td>%(author)s</td><td>%(commit)s</td><td>%(s+)s%(-)i</td><td>\
%(new)i</td><td>%(changedcommit)i</td><td>%(%)i</td>' % data
#print '\t%s%7s lines per commit' % (' '*28, '+%s'%(data['changedcommit']))
        print '</tr>'

    def print_end(self, winner):
        """close the report"""
        print '</tr></table>'
        print '<p>Most frequent committer : <b>%s</b></p>' % winner

