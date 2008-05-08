# -*- coding: utf-8 -*-
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

"""unittests for FileWrapper
"""

import unittest
import os, shutil

from logilab.devtools.vcslib import FileWrapper

from utest_utils import make_test_fs, delete_test_fs
basedir = os.path.dirname(__file__)

ARCH = [(os.path.join(basedir, 'data/dir1'), ('file1.py', 'file2.py')),
        (os.path.join(basedir, 'data/dir2'), ()),
        (os.path.join(basedir, 'data/dir3'), ('file1.py', 'file2.py', 'file3.py')),
        ]


class FileWrapperTC(unittest.TestCase):
    """test case for file wrappers"""

    def setUp(self):
        self.cwd = os.path.dirname(__file__)
        make_test_fs(ARCH)
        self.root_dir = FileWrapper(os.path.join(self.cwd, 'data'))

    def tearDown(self):
        """restore default filesystem"""
        delete_test_fs(ARCH)
        

    def test_dirname(self):
        """test filewrapper directories basenames / abspath"""
        self.assertEquals(self.root_dir.abspath, os.path.join(self.cwd, 'data'))
        self.assertEquals(self.root_dir.get_name(), 'data')

    def test_children(self):
        """test child count"""
        dir1 = self.root_dir['dir1']
        dir1_files = dir1.get_children()
        self.assertEquals(len(dir1_files), 2)
        file1_child, file2_child = dir1_files
        self.assertEquals(file1_child.get_name(), 'file1.py')
        self.assertEquals(id(file1_child.get_parent()), id(dir1))
        self.assertEquals(id(file1_child.get_root()), id(self.root_dir))
        self.assertEquals(file2_child.get_name(), 'file2.py')
        self.assertEquals(id(file2_child.get_parent()), id(dir1))
        self.assertEquals(id(file1_child.next_sibling()), id(file2_child))
        self.assertEquals(file1_child.previous_sibling(), None)
        self.assertEquals(id(file2_child.previous_sibling()), id(file1_child))
        self.assertEquals(file2_child.next_sibling(), None)
    
    def test_getitem(self):
        """test FileWrapper __getitem__() method"""
        self.assertRaises(KeyError, self.root_dir.__getitem__, 'dir1/file3.py')
        self.assertRaises(KeyError, self.root_dir.__getitem__, 'dir4')
        file1 = self.root_dir['dir1/file1.py']
        self.assertEquals(file1.get_name(), 'file1.py')
        dir1 = self.root_dir['dir1']
        self.assertEquals(dir1.get_name(), 'dir1')
        self.assertEquals(id(dir1.get_parent()), id(self.root_dir))

    def test_is_leaf(self):
        """test FileWrapper.is_leaf()"""
        file1 = self.root_dir['dir1/file1.py']
        self.assertEquals(file1.is_leaf(), True)
        dir1 = self.root_dir['dir1']
        self.assertEquals(dir1.is_leaf(), False)
        dir2 = self.root_dir['dir2']
        self.assertEquals(dir2.is_leaf(), True)
        
    def test_isfile(self):
        """test FileWrapper.is_file()"""
        file1 = self.root_dir['dir1/file1.py']
        self.assertEquals(file1.is_file(), True)
        dir1 = self.root_dir['dir1']
        self.assertEquals(dir1.is_file(), False)
        dir2 = self.root_dir['dir2']
        self.assertEquals(dir2.is_file(), False)

    def test_isdir(self):
        """test FileWrapper.is_directory()"""
        file1 = self.root_dir['dir1/file1.py']
        self.assertEquals(file1.is_directory(), False)
        dir1 = self.root_dir['dir1']
        self.assertEquals(dir1.is_directory(), True)
        dir2 = self.root_dir['dir2']
        self.assertEquals(dir2.is_directory(), True)

    def test_force_update(self):
        """test FileWrapper.force_update()"""
        self.assertRaises(KeyError, self.root_dir.__getitem__, 'dir1/file3.py')
        file(os.path.join(self.cwd, 'data/dir1/file3.py'), 'w').close()
        dir1 = self.root_dir['dir1']
        dir1.force_update()
        try:
            self.root_dir['dir1/file3.py']
        except KeyError:
            raise AssertionError('file3 should be accessible after a force_update()')
        
    def test_no_force_update(self):
        """test FileWrapper.no_force_update()"""
        self.assertRaises(KeyError, self.root_dir.__getitem__, 'dir1/file3.py')
        file(os.path.join(self.cwd, 'data/dir1/file3.py'), 'w').close()
        self.assertRaises(KeyError, self.root_dir.__getitem__, 'dir1/file3.py')


    def test_walk(self):
        """tests FileWrapper.walk()"""
        # Create a default arch (brutal mode !)
        root = FileWrapper('')
        root._children = []
        for childpath, subchildren in ARCH:
            child = root.create_child(childpath)
            root._children.append(child)
            child._children = []
            for subpath in subchildren:
                child._children.append(child.create_child(subpath))
        trace = []
        root.walk(trace_walk, trace)
        self.assertEquals(trace,
                          [os.path.join(self.cwd, d)
                           for d in
                           ('data/dir1',
                            'data/dir1/file1.py',
                            'data/dir1/file2.py',
                            'data/dir2',
                            'data/dir3',
                            'data/dir3/file1.py',
                            'data/dir3/file2.py',
                            'data/dir3/file3.py')])


def trace_walk(node, trace):
    trace.append(node.abspath)


if __name__ == '__main__': 
    unittest.main()


