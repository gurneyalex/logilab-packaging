# -*- coding: ISO-8859-1 -*-
"""this module defines useful functions for OoBrother's unit tests
"""

__revision__ = '$Id: utest_utils.py,v 1.2 2005-01-12 14:20:44 syt Exp $'

import os, shutil

def make_test_fs(arch):
    """creates a default file system for unittests purpose
    The following arch. will be created under data/ : 
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

