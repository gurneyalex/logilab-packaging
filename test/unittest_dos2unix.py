#!/usr/bin/python2.3
# Copyright (c) 2004 LOGILAB S.A. (Paris, FRANCE).
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
"""dos2unix converts ends-of-file from dos to unix, removing(replacing) '\\r'"""

__revision__ = "$ Id: $"

import unittest
from logilab.devtools.dos2unix import *
from os import mkdir, removedirs

class BasicTests(unittest.TestCase):

    def setUp(self):
        self.options = OptionParser()
        self.options.recursive = True
        self.options.new_char = '\\n'
        self.options.do_listing = True
        self.options.logger = create_logger()
        self.options.logger.setLevel(logging.CRITICAL)

      
    def test_convert_file(self):
        """ check that file exists and apply conversion if so."""
        self.assertRaises(TypeError, convert_file)
        self.assertEquals(convert_file("__fake__", self.options), False)

    def test_visit_dir(self):
        """ check that directory exists and apply conversion to its content."""
        self.assertRaises(TypeError, visit_dir)
        self.assertEquals(visit_dir("__fake__", self.options), False)
        # SUCCESS
        mkdir("temp_dos2unix_dir")
        mkdir("temp_dos2unix_dir/subdir")
        mkdir("temp_dos2unix_dir/subdir/temp")
        self.assertEquals(visit_dir("temp_dos2unix_dir", self.options), True)
        self.options.recursive=False
        self.assertEquals(visit_dir("temp_dos2unix_dir", self.options), True)
        removedirs("temp_dos2unix_dir/subdir/temp")

    
if __name__ == "__main__":
   unittest.main()
