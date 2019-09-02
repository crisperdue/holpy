"""Unit test for parsing."""

import unittest

from geometry import parser
from geometry.expr import Fact, Rule, Line

class ParserTest(unittest.TestCase):
    def testParseFact(self):
        test_data = [
            ("coll(A, C, B)", Fact("coll", ["A", "C", "B"])),
            ("coll(A,C,B)", Fact("coll", ["A", "C", "B"])),
        ]

        for s, f in test_data:
            self.assertEqual(parser.parse_fact(s), f)

    def testParseFactPtsOnLine(self):
        test_data = [
            ("para(l:{A, B}, m:{C, D})", Fact("para", ["l:{A, B}", "m:{C, D}"])),
            ("para(l:{A, B}, C, D)", Fact("para", ["l:{A, B}", "C", "D"])),
            ("para(A, B, l:{C, D})", Fact("para", ["A", "B", "l:{C, D}"])),
        ]

        for s, f in test_data:
            self.assertEqual(parser.parse_fact(s), f)


    def testParseRule(self):
        test_data = [
            ("coll(A, C, B) :- coll(A, B, C)",
             Rule([Fact("coll", ["A", "B", "C"])], Fact("coll", ["A", "C", "B"]))),
        ]

        for s, r in test_data:
            self.assertEqual(parser.parse_rule(s), r)

    def testParseLine(self):
        test_data = [
            ("line(A, B, C)", Line(["A", "B", "C"])),
        ]

        for s, l in test_data:
            self.assertEqual(parser.parse_line(s), l)


if __name__ == "__main__":
    unittest.main()
