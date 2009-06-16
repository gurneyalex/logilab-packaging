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
"""this module contains CVS vcs system mangagement implementation
"""

__docformat__ = "restructuredtext en"

__all__ = ('CVSAgent',)
__metaclass__ = type

import sys
import os
import os.path as osp
import time
import re
from datetime import datetime
from time import strptime, strftime, mktime

from logilab.common.shellutils import Execute

from logilab.devtools.cvslog import get_logs
from logilab.devtools.vcslib import VCS_UPTODATE, VCS_MODIFIED, \
     VCS_MISSING, VCS_NEW, VCS_REMOVED, VCS_CONFLICT, VCS_NEEDSPATCH, \
     IVCSAgent, CheckInInfo, localtime_to_gmtime
from logilab.devtools.vcslib.cvsparse import DATE_FORMAT

ENTRY_SRE = re.compile('^(?P<isdir>D?)/(?P<name>[^/]+)/(?P<status>.+)$(?m)')


def get_info(path):
    """read the content of CVS'Entries file and returns a dictionnary with
    filenames as keys and a corresponding tuple as values :
    ('isdir', 'path', 'state', 'rev', 'tag', 'options').

    If 'path' points to a directory, the dict will contain infos on each
    entry recorded by the VC System. If it points to a file, its
    parent directory will be used

    This code is adapted from meld source code (meld/cvsview.py)
    http://meld.sourceforge.net/
    """
    # FIXME: cache result, reread only if the file has been modified
    if not osp.isdir(path):
        directory = osp.dirname(path)
    else:
        directory = path
    cvs_info = {}
    try:
        entries_file = file(osp.join(directory, 'CVS/Entries'))
        entries = entries_file.read()
        entries_file.close()
    except IOError:
        return {}
    for match in ENTRY_SRE.finditer(entries):
        entry_name = match.group('name')
        rev, date, options, tag = match.group('status').split("/")
        path = osp.join(directory, entry_name)
        if tag:
            tag = tag[1:]
        if not osp.exists(path):
            state = VCS_MISSING
        elif osp.isdir(path):
            state = VCS_UPTODATE
        else:
            state = _get_cvsfile_state(path, rev, date)
        cvs_info[entry_name] = (state, rev, tag, options)
    return cvs_info

def _get_cvsfile_state(filepath, rev, date):
    """returns the 'filepath's status

    This code is adapted from meld source code (meld/cvsview.py)
    http://meld.sourceforge.net/
    """
    if rev.startswith("-"):
        state = VCS_REMOVED
    elif rev[0] == '0':
        state = VCS_NEW
    elif date=="dummy timestamp":
        if rev[0] == "0":
            state = VCS_NEW
        else:
            print "Revision '%s' not understood" % rev
    elif date=="dummy timestamp from new-entry":
        state = VCS_MODIFIED
    else:
        plus = date.find("+")
        if plus >= 0:
            state = VCS_CONFLICT
        else:
            try:
                mtime = os.stat(filepath).st_mtime
            except OSError:
                state = VCS_MISSING
            else:
                if time.asctime(time.gmtime(mtime))==date:
                    # Either up-to-date or needs-patch
                    if _ensure_file_uptodate(filepath, rev):
                        state = VCS_UPTODATE
                    else:
                        state = VCS_NEEDSPATCH
                else:
                    state = VCS_MODIFIED
    return state

# FIXME: this function need local access to the cvs repository !
def _ensure_file_uptodate(filepath, rev):
    """Once CVS/Entries is read, we can't say if a file is up-to-date or
    if it needs patch. This function reads the ',v' file in the CVS
    repository (if local), and checks if the last head revision is
    more recent

    :return: True by default, False if the ',v' was found and the
    head revision does not match current rev
    /!\ If any error occurs, this function returns True
    """
    cur_dirname = osp.dirname(filepath)
    file_basename = osp.basename(filepath)
    try:
        cvs_root = file(osp.join(cur_dirname, 'CVS', 'Root')).read()
        cvs_root = cvs_root.strip()
    except IOError:
        return True
    try:
        repo = file(osp.join(cur_dirname, 'CVS', 'Repository')).read()
        repo = repo.strip()
    except IOError:
        return True
    info_filename = osp.join(cvs_root, repo, file_basename +',v')
    try:
        fp = file(info_filename)
    except IOError:
        return True
    head_line = fp.readline()
    fp.close()
    match = re.match('head\s+(?P<rev>.*?);', head_line)
    if match is not None:
        head_rev = match.group('rev')
        if str(rev) != head_rev:
            return False
    return True


class CVSAgent:
    """A CVS specific agent"""
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
        if osp.isdir(filepath):
            dirname, filepath = filepath, ''
        else:
            dirname, filepath = osp.split(filepath)
        cmd = "cd %s && (cvs -Q status %s | grep Status | grep -v Up-to-date)" % (
            dirname, filepath)
        executed = Execute(cmd)
        result = []
        for nouptodate in executed.out.splitlines():
            file, status = nouptodate.split('Status:')
            result.append( (status.strip(), file[5:].strip()) )
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
        executed = Execute("cvs -Q editors -R %s | grep -v '^?'" % filepath)
        result = []
        for edited in executed.out.splitlines():
            result.append('%s: %s' % tuple([w.strip() for w in edited.split()[:2]]))
        return result

    def update(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to update

        :rtype: str
        :return:
          a shell command string to update the given file from the vc
          repository
        """
        dirpath, filename = osp.split(filepath)
        return self._in_dir_cmd(dirpath, "cvs up -dP %s" % filename)

    def commit(self, filepath, msg):
        """
        :type filepath: str
        :param filepath: the file or directory to commit

        :type msg: str
        :param msg: the message used to commit

        :rtype: str
        :return:
          a shell command string to commit the given file to the vc
          repository
        """
        msg = msg.replace("'", r"\'")
        dirpath, filename = osp.split(filepath)
        return self._in_dir_cmd(dirpath, "cvs ci -m '%s' %s" % (msg, filename))

    def add(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to add

        :rtype: str
        :return:
          a shell command string to add the given file to the vc
          repository
        """
        dirpath, filename = osp.split(filepath)
        return self._in_dir_cmd(dirpath, "cvs add %s" % filename)

    def remove(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to remove

        :rtype: str
        :return:
          a shell command string to remove the given file from the vc
          repository
        """
        dirpath, filename = osp.split(filepath)
        return self._in_dir_cmd(dirpath, 'cvs rm -f %s' % filename)

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
            filepath = ' '.join(filepath)
        #dirpath, filename = osp.split(filepath)
        return "cvs tag -F %s %s" % (tagname, filepath)

    def checkout(self, repository, path=None, tag=None, quiet=True):
        """
        :type repository: str
        :param repository: the cvs repository address (url or path)

        :type filepath: str
        :param filepath:
          relative path of the file or directory to check out in the repository

        :rtype: str
        :return:
          a shell command string to check out the given file or directory from
          the repository
        """
        tag = tag or 'HEAD'
        if quiet:
            quiet = '-Q'
        else:
            quiet = ''
        return 'cvs -d %s %s checkout -r %s %s' % (repository, quiet, tag, path)

    def log_info(self, repository, from_date, to_date, path=None, tag=None):
        """get log messages between <from_date> and <to_date> (inclusive)

        Both date should be local time (ie 9-sequence)

        a log information is a tuple
        (file, revision_info_as_string, added_lines, removed_lines)
        """
        assert from_date < to_date
        from_date = strftime('%Y-%m-%d %H:%M', localtime_to_gmtime(from_date))
        to_date = strftime('%Y-%m-%d %H:%M', localtime_to_gmtime(to_date))
        cmdoptions = ['-d "%s<=%s"' % (from_date, to_date)]
        if tag and tag != 'HEAD':
            cmdoptions.append('-r%s' % tag)
        if repository:
            cvsoptions = ['-d', repository]
        else:
            cvsoptions = []
        loginfo = get_logs(cvsoptions, cmdoptions, rlog=path)
        for fileobj in loginfo:
            for rev in fileobj.children:
                if fileobj.repo_file.find('/Attic/') > -1:
                    continue
                date = datetime.fromtimestamp(mktime(strptime(rev.date, DATE_FORMAT)))

                kargs = { 'encoding': getattr(sys.stdout,"encoding",None)}
                if kargs['encoding'] is None:
                     kargs['encoding'] = 'ascii'
                     kargs['errors'] = 'ignore'

                msg = unicode('\n'.join(rev.message), **kargs)
                yield CheckInInfo(date, rev.author, msg,
                                  rev.revision, rev.lines[0], rev.lines[1],
                                  files=(fileobj.repo_file,), branch=tag)

    def _in_dir_cmd(self, directory, cmd):
        if directory:
            cmd = "cd %s && %s" % (directory, cmd)
        return cmd


# CVSAgent is a stateless object, transparent singleton thanks to its __call__
# method
CVSAgent = CVSAgent()

