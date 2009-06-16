# This module uses some of meld source code :
#      Copyright (C) 2002-2003 Stephen Kennedy <stevek@gnome.org>
#      http://meld.sourceforge.net
#
# Copyright (c) 2004-2008 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""this module contains SVN vcs system mangagement implementation
"""

__metaclass__ = type
__all__ = ['SVNAgent']

import sys
import os
import re
from os.path import isdir, join, dirname, basename, exists, split
from datetime import datetime
from time import strptime, strftime, mktime
from xml.sax import make_parser, ContentHandler

from logilab.common.shellutils import Execute

from logilab.devtools.vcslib import VCS_UPTODATE, VCS_MODIFIED, \
     VCS_MISSING, VCS_NEW, VCS_CONFLICT, VCS_NOVERSION, VCS_IGNORED, \
     VCS_REMOVED, VCS_NEEDSPATCH, IVCSAgent, CheckInInfo, localtime_to_gmtime

# This one is for when the svn '-u' option will work ...
# ENTRY_SRE = re.compile("^(.)......(.)\s*\d*\s*(\d*)\s*[^ ]*\s*(.*)$(?m)")
ENTRY_SRE = re.compile("^(.)....\s*\d*\s*(\d*)\s*[^ ]*\s*(.*)$(?m)")

SVN_CODES =  {
    "?" : VCS_NOVERSION,
    "A" : VCS_NEW,
    " " : VCS_UPTODATE,
    "!" : VCS_MISSING,
    "I" : VCS_IGNORED,
    "M" : VCS_MODIFIED,
    "C" : VCS_CONFLICT,
    "D" : VCS_REMOVED,
    "*" : VCS_NEEDSPATCH,
    }

REM_LOCAL_DATE_RGX = re.compile(r' \+0000 \(\w\w\w, \d\d \w\w\w \d\d\d\d\)')


def get_info(path):
    """read the result of "svn status" command and returns a dictionnary
    with filenames as keys and a corresponding tuple as values :
    ('isdir', 'path', 'state', 'rev', 'tag', 'options').

    If 'path' points to a directory, the dict will contain infos on each
    entry recorded by the VC System. If it points to a file, its
    parent directory will be used

    This code is adapted from meld source code (meld/svnview.py)
    http://meld.sourceforge.net/
    """
    if not isdir(path):
        directory = dirname(path)
    else:
        directory = path
    svn_info = {}
    # FIXME: understand why the '-u' option fails most of time
    entries = os.popen("svn status -Nv " + directory).read()
    # if not entries:
    #     entries = os.popen("svn status -Nv " + directory).read()
    matches = ENTRY_SRE.findall( entries)
    matches.sort()
    for match in matches:
        name = match[2]
        if(match[0] == "!" or match[0] == "A"):
            # for new or missing files, the findall expression
            # does not supply the correct name
            name = re.sub(r'^[?]\s*(.*)$', r'\1', name)
        is_dir = isdir(name)
        path = join(path, name)
        base = basename(name)
        rev = match[1]
        options = ""
        tag = ""
        if tag:
            tag = tag[1:]
        if is_dir:
            if exists(path):
                state = VCS_UPTODATE
            else:
                state = VCS_MISSING
            # svn adds the path reported to the status list we get.
            if basename(name) != basename(directory):
                svn_info[base] = (state, rev, tag, options)
        else:
            state = SVN_CODES.get(match[0], VCS_NOVERSION)
            svn_info[base] = (state, rev, tag, options)
    return svn_info

class SVNAgent:
    """A SVN specific agent"""
    __implements__ = IVCSAgent,

    def __call__(self):
        return self

    def not_up_to_date(self, filepath):
        """get a list describing files which are not up to date under the
        given path

        :type filepath: str
        :param filepath: starting path

        :rtype: list(tuple(str, str))
        :return:
          a list of tuple (file, status) describing files which are not up to date
        """
        executed = Execute("svn status %s" % filepath)
        result = []
        for nouptodate in executed.out.splitlines():
            status, filename = nouptodate.split()
            result.append( (status.strip(), filename.strip()) )
        return result

    def edited(self, filepath):
        """get a list describing files which are currentlyedited under
        the given path

        :type filepath: str
        :param filepath: starting path

        :rtype: list(tuple(str, str))
        :return:
          a list of tuple (file, locked by) describing files which are in edition
        """
        raise NotImplementedError()

    def update(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to update

        :rtype: str
        :return:
          a shell command string to update the given file from the vc
          repository
        """
        return 'svn update %s' % filepath

    def commit(self, filepath, message):
        """
        :type filepath: str
        :param filepath: the file or directory to commit

        :type message: str
        :param message: the message used to commit

        :rtype: str
        :return:
          a shell command string to commit the given file to the vc
          repository
        """
        return 'svn ci -m "%s" %s' % (message, filepath)

    def add(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to add

        :rtype: str
        :return:
          a shell command string to add the given file to the vc
          repository
        """
        return 'svn add %s' % filepath

    def remove(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to remove

        :rtype: str
        :return:
          a shell command string to remove the given file from the vc
          repository
        """
        cmd = 'svn rm -f %s' % filepath
        return cmd

    def tag(self, filepath, tagname):
        """
        :type filepath: str
        :param filepath: the file or directory to commit

        :type tagname: str
        :param tagname: the name of the tag to add to the file

        :rtype: str
        :return:
          a shell command string to tag the given file in the vc
          repository using the given tag name
        """
        url = get_url(filepath)
        tag_url = url.split('/')
        for special in ('trunk', 'tags', 'branches'):
            if special in tag_url:
                special_index = tag_url.index(special)
                tag_url = tag_url[:special_index]
                tag_url.append('tags/%s' % tagname)
                tag_url = '/'.join(tag_url)
                break
        else:
            raise Exception('Unable to compute file path in the repository')
        cmd = 'svn rm -m "moving tag" %s ; svn copy -m "tagging" %s %s' % (
            tag_url, filepath, tag_url)
        return cmd

    def checkout(self, repository, path=None, tag=None, quiet=True):
        """
        :type repository: str
        :param repository: the svn repository url

        :type filepath: str
        :param filepath:
          relative path of the file or directory to check out in the repository

        :rtype: str
        :return:
          a shell command string to check out the given file or directory from
          the repository
        """
        if quiet:
            quiet ='-q'
        else:
            quiet = ''
        if tag:
            repository = '%s/%s' % (repository, tag)
        elif path:
            repository = '%s/%s' % (repository, path)
        return 'svn checkout --non-interactive %s %s' % (
           quiet, repository)

    def log_info(self, repository, from_date, to_date, path=None, tag=None):
        """get log messages between <from_date> and <to_date> (inclusive)

        Both date should be local time (ie 9-sequence)

        a log information is a tuple
        (file, revision_info_as_string, added_lines, removed_lines)
        """
        # XXX how-to to include time
        from_date = strftime('%Y-%m-%d %H:%M', localtime_to_gmtime(from_date))
        # since we want an inclusive range
        to_date = strftime('%Y-%m-%d %H:%M', localtime_to_gmtime(to_date))
        assert from_date < to_date, "%r < %r" % (from_date, to_date)
        command = 'LC_ALL=C TZ=UTC svn log --non-interactive -r "{%s}:{%s}" %s %s' % (
            from_date, to_date, repository, tag or path or '')
        separator = '-' * 72
        status, msg, rev, author, date = None, '', None, None, None
        infos = []
        cmd =  Execute(command)
        for line in cmd.out.splitlines():
            if not line.strip():
                continue
            if line == separator:
                if status is not None:
                    # FIXME: added/removed line information
                    date = datetime.fromtimestamp(mktime(strptime(date, '%Y-%m-%d %H:%M:%S')))
                    if hasattr(sys.stdout,'encoding') and sys.stdout.encoding is not None:
                        msg = unicode(msg, sys.stdout.encoding)
                    else:
                        msg = unicode(msg)
                    infos.append((date, CheckInInfo(date, author, msg, rev,
                                                    branch=tag)))
                status, msg = 'new', ''
            elif status == 'new':
                rev, author, date, added = [part.strip()
                                            for part in line.split('|')]
                date = REM_LOCAL_DATE_RGX.sub('', date)
                status = 'content'
            elif status == 'content':
                msg = '%s\n%s' % (msg, line)
        for _, info in reversed(sorted(infos)):
            yield info


# SVNAgent is a stateless object, transparent singleton thanks to its __call__
# method
SVNAgent = SVNAgent()

class ElementURLNotFound(Exception): pass
class ElementURLFound(Exception): pass

class SVNSAXHandler(ContentHandler):
    def __init__(self, name):
        self._look_for = name

    def startElement(self, name, attrs):
        if name == 'entry' and attrs['name'] == self._look_for:
            raise ElementURLFound(attrs['url'])

def get_url(path):
    if isdir(path):
        dirpath, filename = path, ''
    else:
        dirpath, filename = split(path)
    p = make_parser()
    print 'looking for', filename, 'in', dirpath
    p.setContentHandler(SVNSAXHandler(filename))
    try:
        p.parse(file(join(dirpath, '.svn', 'entries')))
    except ElementURLFound, ex:
        return ex.args[0]
    except KeyError:
        assert filename
        return '%s/%s' % (get_url(dirpath), filename)
    raise ElementURLNotFound()
