from __future__ import with_statement

import os
from os.path import exists
from unittest2 import main, TestCase

from logilab.devtools.lgp import utils

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
