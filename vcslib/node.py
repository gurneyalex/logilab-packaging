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
"""this modules defines a basic node class which is used here to handle
the file system tree representation, but it could be used to represent any tree
like data structure.
"""

__docformat__ = "restructuredtext en"
__metaclass__ = type

from logilab.devtools.vcslib.interfaces import INode


class BaseNode:
    """Simple implementation of the `INode` interface"""
    
    __implements__ = INode,
    
    def __init__(self, node_id, parent=None):
        self._parent = parent 
        self._nid = node_id

    ## misc. node methods ############################################
        
    def __str__(self):
        return self._nid

    def __repr__(self):
        return '<%s Class instance at %s>' % (self.__class__, hex(id(self)))
    
    ## node protcol methods ##########################################
    
    def is_leaf(self):
        """
        :rtype: bool
        :return:
          True if this file isn' a directory or has no children, else False
        """    
        if not self.get_children():
            return True
        return False

    def get_value(self):
        """
        :rtype: str
        :return: the node's identifier
        """
        return self._nid

    def get_child_number(self):
        """
        :rtype: int
        :return: the number of child for this node
        """
        return len(self.get_children())
    
    def get_root(self):
        """
        :rtype: `INode`
        :return: the top level node (i.e. the root of the tree)
        """
        child, parent = self, self._parent
        while parent is not None:
            child = parent
            parent = parent.get_parent()
        return child

    def get_parent(self):
        """
        :rtype: `INode`
        :return: the parent directory
        """
        return self._parent
    
    def get_children(self):
        """
        :rtype: list(`INode`)
        :return:
          a list of instances implementing `INode` for each node contained by
          this one
        """
        return []

    def next_sibling(self):
        """
        :rtype: `INode` or None
        :return: the next sibling or None if there is no next sibling
        """
        if self._parent is None:
            return None
        parent_children = self._parent.get_children()
        self_pos = parent_children.index(self)
        try:
            return parent_children[self_pos + 1]
        except IndexError:
            return None

    def previous_sibling(self):
        """
        :rtype: `INode` or None
        :return: the previous sibling or None if there is no previous sibling
        """
        if self._parent is None:
            return None
        parent_children = self._parent.get_children()
        self_pos = parent_children.index(self)
        if self_pos == 0:
            return None
        return parent_children[self_pos - 1]

