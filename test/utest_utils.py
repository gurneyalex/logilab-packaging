# -*- coding: utf-8 -*-
"""this module defines useful functions for OoBrother's unit tests
"""

import os, shutil

def make_test_fs(arch):
    """creates a default file system for unittests purpose
    Given the input:

    [('dir1', ('file1.py', 'file2.py')),
     ('dir2', ()),
     ('dir3', ('file1.py', 'file2.py', 'file3.py')),
     ]
     
    The following tree will be created in the current working dir : 

      |- dir1
      |  |- file1.py
      |  \- file2.py
      |- dir2
      \- dir3
         |- file1.py
         |- file2.py
         \- file3.py
    """
    for dirname, filenames in arch:
        os.mkdir(dirname)
        for fname in filenames:
            filename = os.path.join(dirname, fname)
            file(filename, 'w').close()


def delete_test_fs(arch):
    """deletes the test fs"""
    for dirname, filenames in arch:
        try:
            shutil.rmtree(dirname, True)
        except:
            pass

