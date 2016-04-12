from __future__ import print_function

import os
from os.path import exists
try:
    from unittest2 import main, TestCase
except ImportError:
    from unittest import main, TestCase

from logilab.packaging.lgp import utils

class UtilsTC(TestCase):
    def test_tempdir_utility(self):
        with self.assertRaises(AssertionError):
            with utils.tempdir(False) as tmpdir:
                # force exception raising in with block
                assert False
        self.assertFalse(exists(tmpdir))

        with self.assertRaises(AssertionError):
            with utils.tempdir(True) as tmpdir:
                # force exception raising in with block
                assert False
        self.assertTrue(exists(tmpdir))
        os.rmdir(tmpdir)

if __name__ == '__main__':
    main()
