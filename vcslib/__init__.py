# pylint: disable-msg=E0201
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
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""this module defines common classes / operations / globals used by different
implementation of Version Control Systems

typical use would be:

>>> agent = get_vcs_agent(some_path)
>>> if agent.not_up_to_date('.'): print 'not up to date'

etc.
"""

__docformat__ = "restructuredtext en"
__metaclass__ = type

import mimetypes
import os
from datetime import datetime
from os.path import join, exists, isfile, isdir, dirname, basename

from logilab.common.textutils import splittext

from logilab.devtools.vcslib.interfaces import IVCSFile, IVCSAgent
from logilab.devtools.vcslib.node import BaseNode

BASE_EXCLUDE = ('CVS', '.svn', '.hg', 'bzr')

VCS_IGNORED    = 0
VCS_NOVERSION  = 1
VCS_UPTODATE   = 2
VCS_MODIFIED   = 3
VCS_MISSING    = 4
VCS_NEW        = 5
VCS_REMOVED    = 6
VCS_CONFLICT   = 7
VCS_NEEDSPATCH = 8

STATUS_LABELS = ['ignored', 'noversion', 'up-to-date',
                 'modified', 'missing', 'new', 'removed',
                 'conflict', 'needs patch']

class NoVersionControl(Exception):
    """raised when a vcs command is executed on a file which is
    not under version control
    """

class AlreadyUnderVC(Exception):
    """raised when a vcs-add command is executed on a file which is
    already under version control
    """


def get_mimetype(filename):
    """
    :type filename: str
    :param filename: base name of a file

    :rtype: str or None
    :return: mimetype found for `filename`
    """
    # FIXME: do this using regular mimetypes module api
    mt = mimetypes.guess_type(filename)[0]
    if mt is None:
        if filename.endswith('.changes'):
            mt = 'application/x-debian-changes'
        elif filename.endswith('.dsc'):
            mt = 'application/x-debian-dsc'
        elif filename in ('TODO', 'README'):
            mt = 'text/plain'
    return mt


class FileWrapper(BaseNode):
    """file wrapper implementing IVCSFile interface (extending the INode
    interface)
    """

    __implements__ = IVCSFile

    def __init__(self, abspath, parent=None):
        BaseNode.__init__(self, abspath, parent)
        self.abspath = abspath
        self.basename = basename(abspath)
        self.mimetype = get_mimetype(self.basename)
        # vc attributes
        self.status = VCS_NOVERSION
        self.revision = None
        self._tag = None
        self._vcs_agent = None
        # internal attributes
        self._is_dir = isdir(abspath)
        self._use_cache = True
        self._children = None
        # post initialization for version control
        self._vc_init()

    def __str__(self):
        """use absolute path as string representation"""
        return self.abspath

    def __repr__(self):
        """include absolute path in internal string representation"""
        return '<%s for %s at 0x%x>' % (self.__class__.__name__,
                                        self.abspath, id(self))

    def __getitem__(self, path):
        """provide dict like access to contained files, allowing things
        such as :

        >>> f = FileWrapper('/')
        >>> syt_home = f['home/syt']
        >>> syt_home.abspath
        '/home/syt'
        """
        splitted_path = path.split(os.sep, 1)
        if len(splitted_path) == 1:
            child_name = splitted_path[0]
            remaining_path = None
        else:
            child_name, remaining_path = splitted_path
        # XXX maybe we should build a dict in "get_children()" ?
        for child in self.get_children():
            if child.get_name() == child_name:
                if remaining_path is None:
                    return child
                return child[remaining_path]
        raise KeyError('%s has no child %s' % (self, child_name))


    # miscellaneous file methods ##############################################

    def create_child(self, filename):
        """create a child node element for the given file name

        :type filename: str
        :param filename: the name of the child file

        :rtype: `FileWrapper`
        :return: the wrapped file object
        """
        file_abspath = join(self.abspath, filename)
        return FileWrapper(file_abspath, self)

    def filter_filename(self, filename):
        """
        :rtype: bool
        :return:
          True if the given filename should be wrapped as a node children

        This default implementation always return True
        """
        return True

    def is_leaf(self):
        """
        :rtype: bool
        :return:
          True if this file isn' a directory or has no children, else False
        """
        # don't use BaseNode.is_leaf since it would build the children list
        return not self.get_child_number()

    def is_directory(self):
        """
        :rtype: bool
        :return: True if this file is a directory, else False
        """
        return self._is_dir

    def is_file(self):
        """
        :rtype: bool
        :return: True if this file is a regular file, else False
        """
        return isfile(self.abspath)

    def get_value(self):
        """
        :rtype: str
        :return: the node's absolute path
        """
        return self.abspath

    def get_name(self):
        """
        :rtype: str
        :return: the node's base name
        """
        return self.basename

    def get_child_number(self):
        """
        This method is overridden from `BaseNode` since it can be a bit
        more efficient than simply len(node.get_children() as here
        get_children is a lazy method building children on the first call

        :rtype: int
        :return: the number of children for this node
        """
        if not self._is_dir:
            return 0
        if self._use_cache and self._children is not None:
            return len(self._children)
        return len([fname for fname in os.listdir(self.abspath)
                    if self.filter_filename(fname)])

    def get_children(self):
        """
        :rtype: list(`FileWrapper`)
        :return:
          a list of `FileWrapper` instances for each file contained by
          this one
        """
        if self._use_cache and self._children is not None:
            return self._children
        if not self._is_dir:
            self._children = []
            return self._children
        to_load = [fname for fname in os.listdir(self.abspath)
                   if self.filter_filename(fname)]
        to_load.sort()
        self._children = [self.create_child(fname) for fname in to_load]
        return self._children

    def walk(self, func, *args, **kwargs):
        """walk through the computed part of the FS tree, and calls <func> on
        each visited node.
        :param func: will be called with the visited node as first argument
        :type func: callable
        """
        # FIXME: add top-down, left-right option
        if not self._children:
            return
        for child in self._children:
            func(child, *args, **kwargs)
            child.walk(func, *args, **kwargs)

    # ICVSFile interface ######################################################

    def not_up_to_date(self):
        """return a list of tuple (file, status) which are not up to date"""
        return self._vcs_agent.not_up_to_date(self)

    def get_status(self):
        """
        :rtype: int
        :return: the vc status of this file as a symbolic constant
        """
        return self.status

    def get_revision(self):
        """
        :rtype: str or None
        :return: the current vc revision of this file

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        return self.revision

    def get_tag(self):
        """
        :rtype: str or None
        :return: the vc tag of this file if any

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        return self._tag

    def update(self):
        """return a shell command string to update this file from the vc
        repository

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        self._ensure_version_controlled()
        return self._vcs_agent.update(self.abspath)

    def commit(self, msg=''):
        """return a shell command string to commit this file to the vc
        repository

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        self._ensure_version_controlled()
        return self._vcs_agent.commit(self.abspath, msg)

    def add(self):
        """return a shell command string to add this file to the vc
        repository

        :raise: `AlreadyUnderVCS` exception if this file is already under
        version control
        """
        if self.status != VCS_NOVERSION:
            raise AlreadyUnderVC('%s is already under version control' % (
                self.abspath))
        if not self.parent or self.parent.status == VCS_NOVERSION:
            raise Exception('can\'t add %s to version control since his \
parent is not under version control' % self.abspath)
        return self.parent._vcs_agent.add(self.abspath)

    def remove(self):
        """return a shell command string to remove this file from the vc
        repository

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        self._ensure_version_controlled()
        return self._vcs_agent.remove(self.abspath)

    def tag(self, tagname):
        """return a shell command string to tag this file using the
        given tag

        :type tagname: str
        :param tagname: the name of the tag to apply

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """
        self._ensure_version_controlled()
        return self._vcs_agent.tag(self.abspath, tagname)


    # file system synchronization methods #####################################

    def force_update(self):
        """force re-computation of children list (re-read filesystem info)"""
        # there's nothing to do if we don't use cache
        if self._use_cache:
            # prevent get_children() of using cached values
            self._use_cache = False
            # FIXME: not yet working
            #self.disable_cache()
            self.get_children()
            self._use_cache = True
            #child._children = None

    def disable_cache(self):
        self._use_cache = False
        if self._children is not None:
            for child in self._children:
                child.disable_cache()

    def update_parent(self):
        """force re-computation of parent's list (re-read filesystem info)"""
        parent = self.get_parent()
        if parent:
            parent.force_update()


    # internal methods ########################################################
    def _get_children_cvs_info(self):
        """returns a dictionary of children's VC (CVS) informations

        This method is used to only compute CVS informations once
        """
        if not self.is_directory():
            return {}
        if hasattr(self, '_children_cvs_info'):
            return self._children_cvs_info
        if exists(join(self.abspath, 'CVS')):
            from logilab.devtools.vcslib import cvs
            self._children_cvs_info = cvs.get_info(self.abspath)
        else:
            self._children_cvs_info = {}
        return self._children_cvs_info

    children_cvs_info = property(_get_children_cvs_info,
                                 doc = "children's CVS informationss")

    def _get_children_svn_info(self):
        """returns a dictionary of children's VC (SVN) informations

        This method is used to only compute SVN informations once
        """
        if not self.is_directory():
            return {}
        if hasattr(self, '_children_svn_info'):
            return self._children_svn_info
        if exists(join(self.abspath, '.svn')):
            from logilab.devtools.vcslib import svn
            self._children_svn_info = svn.get_info(self.abspath)
        else:
            self._children_svn_info = {}
        return self._children_svn_info

    children_svn_info = property(_get_children_svn_info,
                                 doc = "children's SVN informationss")

    def _ensure_version_controlled(self):
        """
        :raise: `NoVersionControl` if self is not under version control
        """
        if self.status == VCS_NOVERSION:
            raise NoVersionControl('%s is not under version control' %
                                   self.abspath)

    def _set_use_cache(self, use_it=True):
        """Defines whether or not we should re-use the children list that
        was computed on the last get_children() call
        """
        self._use_cache = use_it

    def _vc_init(self):
        """set the correct vc attributes values for this file"""
        if self._parent is None:
            return
        # check if parent node holds CVS informations about us
        cvs_info = self._parent.children_cvs_info
        try:
            state, rev, tag, _ = cvs_info[self.basename]
            self.status, self.revision, self._tag = state, rev, tag
            from logilab.devtools.vcslib import cvs
            self._vcs_agent = cvs.CVSAgent()
            return
        except KeyError:
            pass
        # no CVS => check if parent node holds SVN informations about us
        svn_info = self._parent.children_svn_info
        try:
            state, rev, tag, _ = svn_info[self.basename]
            self.status, self.revision, self._tag = state, rev, tag
            from logilab.devtools.vcslib import svn
            self._vcs_agent = svn.SVNAgent()
            return
        except KeyError:
            pass

def agent(name):
    if name == 'cvs':
        from logilab.devtools.vcslib.cvs import CVSAgent
        return CVSAgent()
    if name == 'svn':
        from logilab.devtools.vcslib.svn import SVNAgent
        return SVNAgent()
    if name == 'hg':
        from logilab.devtools.vcslib.hg import HGAgent, find_repository
        return HGAgent()
    raise ValueError(name)

def get_vcs_agent(directory):
    """returns the appropriate VCS agent according to the version control
    system  detected in the given directory"""
    if isfile(directory):
        directory = dirname(directory)
    if exists(join(directory, 'CVS')):
        from logilab.devtools.vcslib.cvs import CVSAgent
        return CVSAgent()
    if exists(join(directory, '.svn')):
        from logilab.devtools.vcslib.svn import SVNAgent
        return SVNAgent()
    try:
        from logilab.devtools.vcslib.hg import HGAgent, find_repository
    except ImportError:
        # mercurial not installed
        pass
    else:
        if find_repository(directory):
            return HGAgent()
    return None


class CheckInInfo:
    def __init__(self, date, author, message,
                 revision=None, added=0, removed=0, files=(), branch=None):
        """information relative to a vcs checkin

        required arguments:

        * `date`: GMT date (`datetime.datetime` instance) on which the check-in
          has been done
        * `author`: string representing the author of the check-in
        * `message`: unicode string giving the check-in message

        optional arguments:

        * `revision`: revision on vcs where it make sense. Type will depend on
          the scm.
        * `added`: integer number of lines added by this check-in
        * `removed`: integer number of lines removed by this check-in
        * `files`: list of files on which the check-in apply
        * `branch`: branch on which the check-in apply if it's not the main trunk
        """
        assert isinstance(date, datetime), repr(date)
        assert isinstance(author, basestring), repr(author)
        assert isinstance(message, unicode), repr(message)
        assert isinstance(added, int), repr(added)
        assert isinstance(removed, int), repr(removed)
        self.date = date
        self.author = author
        self.message = message
        self.revision = revision
        self.added = added
        self.removed = removed
        self.files = files
        self.branch = branch

    def message_summary(self, maxlen=72, ellispis='...'):
        """return a short summary of the message in case it's too long"""
        msg = ' '.join(self.message.split()).strip()
        if len(msg) > maxlen:
            msg = splittext(msg, maxlen - len(ellispis))[0] + ellispis
        return msg

    def __str__(self):
        return '%s: %s (%s)' % (self.author,
                                self.message_summary().encode('ascii', 'replace'),
                                self.revision)
    def __repr__(self):
        return "<CheckInInfo (%s)>"%self

    def __cmp__(self, other):
        return cmp(str(self),other)


from time import gmtime, mktime

def localtime_to_gmtime(localtime):
    if not isinstance(localtime, float):
        localtime = mktime(localtime)
    return gmtime(localtime)
