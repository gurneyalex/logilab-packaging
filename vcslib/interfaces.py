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
"""this module defines interfaces used by this version control
system library.
"""

__docformat__ = "restructuredtext en"
__metaclass__ = type

from logilab.common.interface import Interface


class INode(Interface):
    """a simple Node interface, originaly designed to suit the gtk's
    tree model needs
    """
    
    def get_value(self):
        """
        :rtype: str
        :return: the node's identifier
        """

    def get_root(self):
        """
        :rtype: `INode`
        :return: the top level node (i.e. the root of the tree)
        """
        
    def get_parent(self):
        """
        :rtype: `INode`
        :return: the parent directory
        """
    
    def get_children(self):
        """
        :rtype: list(`INode`)
        :return:
          a list of instances implementing `INode` for each node contained by
          this one
        """

    def next_sibling(self):
        """
        :rtype: `INode` or None
        :return: the next sibling or None if there is no next sibling
        """
        
    def previous_sibling(self):
        """
        :rtype: `INode` or None
        :return: the previous sibling or None if there is no previous sibling
        """

    def is_leaf(self):
        """
        :rtype: bool
        :return:
          True if this file isn' a directory or has no children, else False
        """    


class IVCSFile(INode):
    """interface for file wrapping a VCS implementation according to
    a working copy of a file
    """

    def update(self):
        """return a shell command string to update this file from the vc
        repository
        
        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

    def commit(self, msg=''):
        """return a shell command string to commit this file to the vc
        repository

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

    def add(self):
        """return a shell command string to add this file to the vc
        repository
        
        :raise: `AlreadyUnderVCS` exception if this file is already under
        version control
        """

    def remove(self):
        """return a shell command string to remove this file from the vc
        repository
        
        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

    def tag(self, tagname):
        """return a shell command string to tag this file using the
        given tag

        :type tagname: str
        :param tagname: the name of the tag to apply
        
        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

    def get_status(self):
        """
        :rtype: int
        :return: the vc status of this file as a symbolic constant
        """

    def get_tag(self):
        """
        :rtype: str or None
        :return: the vc tag of this file if any

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

    def get_revision(self):
        """
        :rtype: str or None
        :return: the current vc revision of this file

        :raise: `NoVersionControl` exception if this file is not under
        version control
        """

##     def history(self):
##         """returns history of 'filepath'
##         Raises a NoVersionControl exception is 'filepath' is not under
##         version control
##         """
##         raise NotImplementedError()
##     def diff_version(self, version1, version2):
##         """returns diff between 'version1' and 'version2' of 'filepath'
##         Raises a NoVersionControl exception is 'filepath' is not under
##         version control
##         """
##         raise NotImplementedError()



class IVCSAgent(Interface):
    """interface for a VCS agent. A VC agent is used to get a generic
    implementation of `IVCSFile`
    """
        
    def not_up_to_date(self, filepath):
        """get a list describing files which are not up to date under the
        given path

        :type filepath: str
        :param filepath: starting path
        
        :rtype: list(tuple(str, str))
        :return:
          a list of tuple (file, status) describing files which are not up to date
        """

    def edited(self, filepath):
        """get a list describing files which are currentlyedited under
        the given path
        
        :type filepath: str
        :param filepath: starting path
        
        :rtype: list(tuple(str, str))
        :return:
          a list of tuple (file, locked by) describing files which are in edition
        """
    
    def update(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to update
        
        :rtype: str
        :return:
          a shell command string to update the given file from the vc
          repository
        """

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

    def add(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to add
        
        :rtype: str
        :return:
          a shell command string to add the given file to the vc
          repository
        """

    def remove(self, filepath):
        """
        :type filepath: str
        :param filepath: the file or directory to remove
        
        :rtype: str
        :return:
          a shell command string to remove the given file from the vc
          repository
        """

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
