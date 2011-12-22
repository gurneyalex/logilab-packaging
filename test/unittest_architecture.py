from __future__ import with_statement

from subprocess import Popen, PIPE

from logilab.common.testlib import TestCase, unittest_main
from logilab.devtools.lgp.utils import get_architectures
from logilab.devtools.lgp.exceptions import ArchitectureException


class ArchitectureTC(TestCase):

    def test_default_architecture(self):
        archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
        self.assertEqual(get_architectures(), archi)
        self.assertEqual(get_architectures(['all']), archi)
        self.assertEqual(get_architectures(['current']), archi)

    def test_one_valid_architecture(self):
        archi = ['i386']
        self.assertEqual(get_architectures(archi), archi)

    def test_several_valid_architectures(self):
        archi = ['i386', 'amd64', 'openbsd-i386']
        self.assertEqual(get_architectures(archi), archi)

    def test_one_unvalid_architecture(self):
        archi = ['window$']
        with self.assertRaises(ArchitectureException):
            get_architectures(archi)

    def test_mixed_unvalid_architectures(self):
        archi = ['i386', 'openbsd-arm', 'hurd-i386', 'window$', 'sparc']
        with self.assertRaises(ArchitectureException):
            get_architectures(archi)


if __name__  == '__main__':
    unittest_main()
