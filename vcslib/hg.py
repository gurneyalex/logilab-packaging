# This module uses some of meld source code :
#      Copyright (C) 2002-2003 Stephen Kennedy <stevek@gnome.org>
#      http://meld.sourceforge.net
#
# Copyright (c) 2004-2007 LOGILAB S.A. (Paris, FRANCE).
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
"""this module contains mercurial scm"""
    
__metaclass__ = type
__all__ = ['HGAgent', 'find_repository']

import sys
import os
import datetime
from time import gmtime, mktime
from os.path import abspath, isdir, join, dirname
from cStringIO import StringIO

from logilab.common.compat import sorted, reversed

from logilab.devtools.vcslib import VCS_UPTODATE, VCS_MODIFIED, \
     VCS_MISSING, VCS_NEW, VCS_CONFLICT, VCS_NOVERSION, VCS_IGNORED, \
     VCS_REMOVED, VCS_NEEDSPATCH, IVCSAgent

from mercurial.hg import repository as Repository
from mercurial.ui import ui as Ui
from mercurial.cmdutil import walkchangerevs
from mercurial.util import cachefunc

def find_repository(path):
    """returns <path>'s mercurial repository

    None if <path> is not under hg control
    """
    path = abspath(path)
    while not isdir(join(path, ".hg")):
        oldpath = path
        path = dirname(path)
        if path == oldpath:
            return None
    return path


def changeset_info(repo, rev=0, changenode=None):
    """returns matching (rev, date, user, sumarry)"""
    log = repo.changelog
    if changenode is None:
        changenode = log.node(rev)
    elif not rev:
        rev = log.rev(changenode)
    manifest, user, (time, timezone), files, desc, extra = log.read(changenode)
    summary = desc.splitlines()[0]
    checkin_date = datetime.datetime.fromtimestamp((float(time) + timezone))
    return rev, checkin_date, user, summary


class HGAgent:
    """A hg specific agent"""
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
        # we don't want mercurial's stdout to interfere with ours
        sys.stdout = StringIO()
        try:
            parentui = Ui()
            repo = Repository(parentui, path=find_repository(filepath))
            localui = repo.ui
            remote = Repository(parentui, localui.expandpath('default'))
            changes = []
            # XXX: httprepository doesn't have changelog attribute
            if hasattr(remote, 'changelog'):
                for nid in repo.findincoming(remote):
                    manifest, user, timeinfo, files, desc, extra = remote.changelog.read(nid)
                    for filename in files:
                        # .ljust(15)
                        changes.append(('incoming', filename))
                for nid in repo.findoutgoing(remote):
                    manifest, user, timeinfo, files, desc, extra = repo.changelog.read(nid)
                    for filename in files:
                        # .ljust(15)
                        changes.append(('outgoing', filename))
            statuslist = ('modified', 'added', 'removed', 'deleted', 'unknown')
            return changes + [(status, filename)
                              for status, files in zip(statuslist, repo.status())
                              for filename in files]
        finally:
            sys.stdout = sys.__stdout__
            
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
        return 'hg pull -u %s' % filepath

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
        print "warning: this is only a commit in the local repository"
        return 'hg ci -m "%s" %s' % (message, filepath)

    def add(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to add
        
        :rtype: str
        :return:
          a shell command string to add the given file to the vc
          repository
        """
        return 'hg add %s' % filepath

    def remove(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to remove
        
        :rtype: str
        :return:
          a shell command string to remove the given file from the vc
          repository
        """
        return 'hg rm -f %s' % filepath

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
        if not isinstance(filepath, basestring):
            filepath = filepath[0] #' '.join(filepath)
        #print os.getcwd()
        #print '**'
        #print abspath(filepath)
        assert abspath(filepath).startswith(os.getcwd()), \
               "I don't know how to deal with filepath and <hg tag>"
        return "hg tag %s" % tagname

    def checkout(self, repository, path, tag=None):
        """
        :type repository: str
        :param repository: the CVS repository address
        
        :type filepath: str
        :param filepath:
          the path of the file or directory to check out *in the
          repository*
        
        :rtype: str
        :return:
          a shell command string to check out the given file or
          directory from the vc repository
        """
        if tag and tag != 'HEAD':
            raise NotImplementedError("don't know how to co a given tag "
                                      "(hg clone -r tag ?")
        #if path:
        #    print "warning: <%s> argument not needed and ignored" % path
        return 'hg clone %s' % repository

    def log_info(self, path, from_date, to_date, repository=None, tag=None):
        """get log messages between <from_date> and <to_date> (inclusive)
        
        Both date should be local time (ie 9-sequence)
        
        a log information is a tuple
        (file, revision_info_as_string, added_lines, removed_lines)
        """
        ui = Ui()
        repo = Repository(ui, path=find_repository(path))
        opts = dict(rev=['tip:0'], branches=None, include=(), exclude=())
        get = cachefunc(lambda r: repo.changectx(r).changeset())
        changeiter, matchfn = walkchangerevs(ui, repo, (), get, opts)
        # changeset_info return GMT time, convert from_date and to_date
        # as well so we can compare
        from_date = datetime.datetime(*gmtime(mktime(from_date))[:6])
        to_date = datetime.datetime(*gmtime(mktime(to_date))[:6])
        infos = []
        msg_template = '%s by %s on %s: %s'
        for st, rev, fns in changeiter:
            if st == 'add':
                changenode = repo.changelog.node(rev)
                br = None
                if opts['branches']:
                    br = repo.branchlookup([repo.changelog.node(rev)])
                rev, date, user, summary = changeset_info(repo, rev, changenode)
                if from_date <= date <= to_date:
                    # FIXME: lines information
                    infos.append((rev, user, date, summary))
                    # msg = '%s by %s on %s: %s' % (rev, user, date, summary)
        for info in reversed(sorted(infos)):
            yield '', msg_template % info, 1, 0


# HGAgent is a stateless object, transparent singleton thanks to its __call__
# method
HGAgent = HGAgent()
