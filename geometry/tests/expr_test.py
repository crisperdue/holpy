"""Unit test for expressions."""

import unittest

from geometry import expr
from geometry.expr import Fact, Rule, Line
from geometry import parser
from geometry.ruleset import ruleset


class ExprTest(unittest.TestCase):
    def testPrintExpr(self):
        test_data = [
            (Fact("coll", ["A", "B", "C"]), "coll(A,B,C)"),
        ]

        for f, s in test_data:
            self.assertEqual(str(f), s)

    def testPrintRule(self):
        test_data = [
            (Rule([Fact("coll", ["A", "B", "C"])], Fact("coll", ["A", "C", "B"])),
             "coll(A,C,B) :- coll(A,B,C)"),
        ]

        for r, s in test_data:
            self.assertEqual(str(r), s)

    def testGetArgTypeByFact(self):
        test_data = [
            ("coll(A, B, C)", [expr.POINT, expr.POINT, expr.POINT]),
            ("perp(l, A, B)", [expr.LINE, expr.PonL]),
            ("cong(A, B, C, D)", [expr.SEG, expr.SEG]),
            ("para(A, B, C, D)", [expr.PonL, expr.PonL]),
            ("eqangle(k, l, m, A, B)", [expr.LINE, expr.LINE, expr.LINE, expr.PonL]),
        ]
        for fact, r in test_data:
            self.assertEqual(expr.get_arg_type_by_fact(parser.parse_fact(fact)), r)

    def testGetCircle(self):
        test_data = [
            (["circle(None, A, B, C, D)"], ["A", "B", "C", "E"], None, "circle(None, A, B, C, D)"),
            (["circle(O, A, B, C, D)"], ["A", "B", "C", "E"], "O", "circle(O, A, B, C, D)"),
            (["circle(O, A, B, C, D)"], ["E", "F", "G", "H"], "P", "circle(P, E, F, G, H)"),
        ]
        for circles, points, center, concl in test_data:
            circles = [parser.parse_circle(circle) for circle in circles]
            concl = parser.parse_circle(concl)
            new_circle = expr.get_circle(circles, points, center=center)
            self.assertEqual({new_circle}, {concl})

    def testCombineCircles(self):
        test_data = [
            ("circle(O, A, B, C, D)", "circle(O, B, C, D, E, F)", "circle(O, A, B, C, D, E, F)"),
            ("circle(O, A, B, C)", "circle(P, C, D, E)", "circle(O, A, B, C)"),
            ("circle(None, A, B, C)", "circle(O, A, B, C)", "circle(O, A, B, C)"),
        ]

        for this_circle, other_circle, combined in test_data:
            this_circle = parser.parse_circle(this_circle)
            other_circle = parser.parse_circle(other_circle)
            combined = parser.parse_circle(combined)
            this_circle.combine(other_circle)
            self.assertEqual(this_circle.center, combined.center)
            self.assertEqual(this_circle.args, combined.args)

    def testMatchFact(self):
        test_data = [
            ("coll(A,B,C)", "coll(P,Q,R)", {}, [{"A": "P", "B": "Q", "C": "R"}]),
            ("coll(A,B,C)", "coll(P,Q,R)", {"A": "P"}, [{"A": "P", "B": "Q", "C": "R"}]),
            ("coll(A,B,C)", "coll(P,Q,R)", {"A": "Q"}, []),
            ("coll(A,B,C)", "para(P,Q,R,S)", {}, []),
            ("coll(A,B,C,D,E,F)", "coll(P,Q,R,S,T,U)", {}, [{"A": "P", "B": "Q", "C": "R", "D": "S",
                                                             "E": "T", "F": "U"}]),
            ("cong(A, B, A, D)", "cong(P, Q, R, S)", {}, []),
            ("cong(A, B, C, D)", "cong(P, Q, P, S)", {}, []),
            ("coll(A, B, A, D)", "coll(P, Q, P, S)", {}, [{"A": "P", "B": "Q", "D": "S"}]),
            ("cong(A, B, A, D)", "cong(P, Q, P, S)", {}, [{"A": "P", "B": "Q", "D": "S"}]),
        ]

        for pat, f, inst, res in test_data:
            pat = parser.parse_fact(pat)
            f = parser.parse_fact(f)
            insts = expr.match_expr(pat, f, inst)
            self.assertEqual(insts, res)

    def testMatchFactLines(self):
        test_data = [
            # ("perp(l, m)", "perp(P, Q, R, S)", {}, ["line(O, P, Q)"], [{"l": ("P", "Q"), "m": ("R", "S")}]),
            # ("perp(l, m)", "perp(P, Q, R, S)", {"l": ("Q", "P")}, ["line(O, P, Q)"],
            #  [{"l": ("Q", "P"), "m": ("R", "S")}]),
            # ("perp(l, m)", "perp(P, Q, R, S)", {"l": ("Q", "P")}, [], [{"l": ("Q", "P"), "m": ("R", "S")}]),
            # ("perp(l, m)", "perp(P, Q, R, S)", {"l": ("A", "P")}, ["line(O, P, Q)"], []),
            # ("para(p, q)", "para(E, N, C, D)", {}, [], [{"p": ("E", "N"), "q": ("C", "D")}]),

            # ("para(A, B, C, D)", "para(P, Q, R, S)", {'A': 'M', 'B': 'N'}, ["line(M, N, P, Q)"],
            #  [{'A': 'M', 'B': 'N', 'C': 'R', 'D': 'S'}, {'A': 'M', 'B': 'N', 'C': 'S', 'D': 'R'}]),

            # ("para(A, B, C, D)", "para(P, Q, R, S)", {'A': 'M', 'B': 'N'}, ["line(E, F, G, H)"], []),

            # ("para(A, B, m)", "para(P, Q, R, S)", {"A": "Q"}, ["line(O, P, Q)"],
            #  [{"A": "Q", "B": "P", "m": ("R", "S")}, {"A": "Q", "B": "O", "m": ("R", "S")}]),

            # ("cong(A, B, C, D)", "cong(P, Q, R, S)", {}, [], [{"A": "P", "B": "Q", "C": "R", "D": "S"},
            #                                                   {"A": "P", "B": "Q", "C": "S", "D": "R"},
            #                                                   {"A": "Q", "B": "P", "C": "R", "D": "S"},
            #                                                   {"A": "Q", "B": "P", "C": "S", "D": "R"}, ]),

            # ("perp(B, A, C, A)", "perp(P, Q, P, R)", {}, [], [{"A": "P", "B": "Q", "C": "R"}]),
            #
            # ("cong(E, A, E, B)", "cong(A, Q, B, Q)", {"A": "A", "B": "B", "D": "P"}, [],
            #  [{"A": "A", "B": "B", "D": "P", "E": "Q"}]),
            # ("perp(m, n)", "perp(A, C, B, E)", {"m": ("A", "C"), "l": ("B", "E")}, [], []),
            # ("eqangle(C, A, C, B, R, P, R, Q)", "eqangle(C, F, C, E, H, F, H, E)", {}, [], []),
            # ("eqangle(C, A, C, B, R, P, R, Q)", "eqangle(B, E, A, C, B, C, A, F)", {},
            #  ["line(E, A, C)", "line(F, B, C)", "line(H, A, F)", "line(H, B, E)", "line(G, A, B)", "line(G, C, H)"], []),

        ]

        for pat, f, inst, lines, res in test_data:
            pat = parser.parse_fact(pat)
            f = parser.parse_fact(f)
            lines = [parser.parse_line(line) for line in lines]
            insts = expr.match_expr(pat, f, inst, lines=lines)
            self.assertEqual(insts, res)

    def testMatchFactCircles(self):
        test_data = [
            # ("cyclic(A, B, C, D)", "cyclic(P, Q, R, S)", {}, [], [{"A": "P", "B": "Q", "C": "R", "D": "S"}]),
            # ("cyclic(A, B, C, D)", "cyclic(P, Q, R, S)", {"A": "T"}, [], []),
            # ("cyclic(A, B, C, D)", "cyclic(P, Q, R, S)", {"A": "R"}, ["circle(None, P, Q, R, S)"],
            #  [{"A": "R", "B": "P", "C": "Q", "D": "S"}]),
            # ("cyclic(A, B, C, D)", "cyclic(P, Q, R, S)", {"A": "R", "B": "Q"}, ["circle(None, P, Q, R, S)"],
            #  [{"A": "R", "B": "Q", "C": "P", "D": "S"}]),
            # ("circle(A, B, C, D)", "circle(P, Q, R, S)", {}, [], [{"A": "P", "B": "Q", "C": "R", "D": "S"}]),
            # ("circle(A, B, C, D)", "circle(P, Q, R, S)", {"A": "P"}, [], [{"A": "P", "B": "Q", "C": "R", "D": "S"}]),
        ]

        for pat, f, inst, circles, res in test_data:
            pat = parser.parse_fact(pat)
            f = parser.parse_fact(f)
            circles = [parser.parse_circle(circle) for circle in circles]
            insts = expr.match_expr(pat, f, inst, circles=circles)
            self.assertEqual(insts, res)

    def testApplyRule(self):
        test_data = [
            (ruleset["D5"], ["para(E, F, G, H)"], ["line(E, F)", "line(G, H)"], [],
             ["para(G, H, E, F)"]),
            (ruleset["D44"], ["midp(P, E, F)", "midp(Q, E, G)"], ["line(E, F)", "line(G, E)"], [],
             ["para(P, Q, F, G)"]),
            (ruleset["D45"], ["midp(N, B, D)", "para(E, N, C, D)", "coll(E, B, C)"],
             ["line(M, N, E)", "line(C, D)", "line(D, N, B)", "line(C, E, B)"], [],
             ["midp(E, B, C)"]),
            (ruleset["D56"], ["cong(D, A, D, B)", "cong(E, A, E, B)"],
             [], [], ["perp(A, B, D, E)"]),
            (ruleset["D13"], ["cong(E, P, P, F)", "cong(P, E, G, P)", "cong(P, E, H, P)"], [], [],
             ["cyclic(E, F, G, H)"]),
            (ruleset["D43"], ["eqangle(E, F, E, G, C, D, C, B)", "cyclic(E, D, G, B, F, C)"],
             ["line(E, F)", "line(E, G)", "line(D, C)", "line(D, B)", "line(F, G)", "line(C, B)"],
             ["circle(None, E, D, G, B, F, C)"], ["cong(F, G, D, B)"]),
            (ruleset["D42"], ["eqangle(A, F, B, C, A, C, B, E)"],
             ["line(E, A, C)", "line(F, B, C)", "line(H, A, F)", "line(H, B, E)", "line(G, A, B)", "line(G, C, H)"],
             [], ["cyclic(A, B, F, E)"]),
            (ruleset["D9"], ["perp(B, E, A, C)", "perp(A, C, B, E)"], [], [], []),
            (ruleset["D43"], ["eqangle(B, E, A, C, B, C, A, F)", "cyclic(B, A, E, F)"],
             ["line(E, A, C)", "line(F, B, C)", "line(H, A, F)", "line(H, B, E)", "line(G, A, B)", "line(G, C, H)"], [], []),
            (ruleset["D42"], ["eqangle(B, E, A, C, A, F, B, C)"],
             ["line(E, A, C)", "line(F, B, C)", "line(H, A, F)", "line(H, B, E)", "line(G, A, B)", "line(G, C, H)"],
             [], ["cyclic(H, C, E, F)"]),
        ]

        for rule, facts, lines, circles, concls in test_data:
            facts = [parser.parse_fact(fact) for fact in facts]
            concls = [parser.parse_fact(concl) for concl in concls]
            lines = [parser.parse_line(line) for line in lines]
            circles = [parser.parse_circle(circle) for circle in circles]
            facts = expr.apply_rule(rule, facts, lines=lines, circles=circles)
            self.assertEqual(facts, concls)

    def testMakeNewLines(self):
        test_data = [
            (["coll(A, B, C)", "coll(A, B, D)", "coll(P, Q, R)", "coll(R, S, T)", "coll(Q, R, S)"], [],
             ["line(A, B, C, D)", "line(P, Q, R, S, T)"]),

            (["coll(A, B, C)"], ["line(B, C, D)"], ["line(A, B, C, D)"]),

            (["coll(E, F)"], ["line(F, G, H)"], ["line(E, F)", "line(F, G, H)"]),

        ]
        for facts, lines, concls in test_data:
            facts = [parser.parse_fact(fact) for fact in facts]
            lines = [parser.parse_line(line) for line in lines]
            prev_lines = lines
            expr.make_new_lines(facts, lines)
            self.assertEqual(set(prev_lines), set(lines))

    def testMakeNewCircles(self):
        test_data = [
            (["cyclic(A, B, C, D)"], [], ["circle(None, A, B, C, D)"]),
            (["circle(O, A, B, C)"], [], ["circle(O, A, B, C)"]),
            (["cyclic(A, B, C, D)"], ["circle(P, B, C, D, E)"], ["circle(P, A, B, C, D, E)"]),
            (["circle(P, A, B, C)"], ["circle(Q, E, F, G)"], ["circle(P, A, B, C)", "circle(Q, E, F, G)"]),
        ]
        for facts, circles, combined in test_data:
            facts = [parser.parse_fact(fact) for fact in facts]
            circles = [parser.parse_circle(circle) for circle in circles]
            combined = [parser.parse_circle(circle) for circle in combined]
            expr.make_new_circles(facts, circles)
            self.assertEqual(set(combined), set(circles))

    def testGetShortFacts(self):
        test_data = [
            ["cong(A, B, C, D, E, F)", ["cong(A, B, C, D)", "cong(A, B, E, F)", "cong(C, D, E, F)"]],
            ["simtri(A, B, C, D, E, F, P, Q, R)", ["simtri(A, B, C, D, E, F)", "simtri(A, B, C, P, Q, R)",
                                                   "simtri(D, E, F, P, Q, R)"]],
            ["para(l, A, B, m)", ["para(l, A, B)", "para(l, m)", "para(A, B, m)"]],
            ["perp(l, m)", ["perp(l, m)"]],
        ]
        for fact, concls in test_data:
            fact = parser.parse_fact(fact)
            concls = [parser.parse_fact(concl) for concl in concls]
            short_facts = expr.get_short_facts(fact)
            self.assertEqual(set(concls), set(short_facts))

    def testApplyRuleHyps(self):
        test_data = [
            (ruleset["D3"], ["coll(E, F, G)", "coll(E, F, H)", "coll(P, Q, R)", "coll(P, Q, S)", "coll(A, B, C)"],
             [], ["coll(G, H, E)", "coll(H, G, E)", "coll(R, S, P)", "coll(S, R, P)"]),

            (ruleset["D5"], ["para(P, Q, R, S)"], [], ["para(R, S, P, Q)"]),

            (ruleset["D45"], ["midp(N, B, D)", "para(E, N, C, D)", "coll(E, B, C)"],
             ["line(M, N, E)", "line(C, D)", "line(D, N, B)", "line(C, E, B)"],
             ["midp(E, B, C)"]),
        ]

        for rule, hyps, lines, concls in test_data:
            hyps = [parser.parse_fact(fact) for fact in hyps]
            concls = [parser.parse_fact(concl) for concl in concls]
            lines = [parser.parse_line(line) for line in lines]
            new_facts = expr.apply_rule_hyps(rule, hyps, lines=lines)
            self.assertEqual(set(new_facts), set(concls))

    def testApplyRulesetHyps(self):
        test_data = [
            # (ruleset, ["midp(N, B, D)", "para(E, N, C, D)", "coll(E, B, C)"],
            #  ["line(M, N, E)", "line(C, D)", "line(D, N, B)", "line(C, E, B)"],
            #  ["midp(E, B, C)", "para(C, D, E, N)", "coll(B, E, C)", "coll(E, C, B)"]),
            # (ruleset, ["cyclic(A, B, F, E)"],
            #  ["line(E, A, C)", "line(F, B, C)", "line(H, A, F)", "line(H, B, E)", "line(G, A, B)", "line(G, C, H)"], []
            #  , ["cyclic(H, C, E, F)"])
        ]
        for rules, hyps, lines, circles, concls, in test_data:
            hyps = [parser.parse_fact(fact) for fact in hyps]
            concls = [parser.parse_fact(concl) for concl in concls]
            lines = [parser.parse_line(line) for line in lines]
            circles = [parser.parse_circle(circle) for circle in circles]
            new_facts = expr.apply_ruleset_hyps(rules, hyps, lines=lines, circles=circles)
            self.assertEqual(set(new_facts), set(concls))

    def testSearchStep(self):
        test_data = [
        ]
        for rules, hyps, lines, concls in test_data:
            hyps = [parser.parse_fact(fact) for fact in hyps]
            lines = [parser.parse_line(line) for line in lines]
            concls = [parser.parse_fact(concl) for concl in concls]
            expr.search_step(rules, hyps, lines=lines)
            self.assertEqual(set(hyps), set(concls))

    def testSearchFixpoint(self):
        test_data = [
            (ruleset, ["cong(D, A, D, B)", "cong(E, A, E, B)", "perp(G, F, D, E)"],
             ["line(A, C, B)", "line(A, G, E)", "line(B, F, E)", "line(D, C, E)"], [],
             "para(A, C, G, F)")
        ]
        for rules, hyps, lines, circles, concl in test_data:
            hyps = [parser.parse_fact(fact) for fact in hyps]
            concl = parser.parse_fact(concl)
            lines = [parser.parse_line(line) for line in lines]
            circles = [parser.parse_circle(circle) for circle in circles]
            hyps = expr.search_fixpoint(ruleset, hyps, lines, circles, concl)
            fact = expr.find_goal(hyps, concl, lines, circles)
            self.assertIsNotNone(fact)

    def testRewriteFact(self):
        test_data = [
            ("eqangle(A, B, B, D, B, D, A, D)", "∠[AB,BD] = ∠[BD,AD]"),
        ]
        for fact, concl in test_data:
            s = expr.rewrite_fact(parser.parse_fact(fact))
            self.assertEqual(s, concl)

    def testPrintSearch(self):
        test_data = [
             (ruleset, ["cong(D, A, D, B)", "cong(E, A, E, B)", "perp(G, F, D, E)", "coll(A, C, B)", "coll(A, G, E)",
                       "coll(B, F, E)", "coll(D, C, E)"], [], [], "para(A, C, G, F)"),
            (ruleset, ["cong(A, B, B, C, C, D, D, A)"], [], [], "eqangle(A, B, B, D, B, D, A, D)"),

            # It takes too long time to prove this...
            # (ruleset, ["eqangle(E, F, E, G, D, C, B, C)", "cyclic(E, D, G, B, F, C)"], [],
            #  ["circle(None, E, D, G, B, F, C)"], "cong(D, B, F, G)"),

            (ruleset, ["coll(E, A, C)", "perp(B, E, A, C)", "coll(F, B, C)", "perp(A, F, B, C)", "coll(H, A, F)",
                       "coll(H, B, E)", "coll(G, A, B)", "coll(G, C, H)"], [], [], "perp(C, G, A, B)"),
        ]
        for rules, hyps, lines, circles, concl in test_data:
            hyps = [parser.parse_fact(fact) for fact in hyps]
            concl = parser.parse_fact(concl)
            lines = [parser.parse_line(line) for line in lines]
            circles = [parser.parse_circle(circle) for circle in circles]
            hyps = expr.search_fixpoint(ruleset, hyps, lines, circles, concl)
            # print(hyps)
            fact = expr.find_goal(hyps, concl, lines, circles)
            self.assertIsNotNone(fact)
            expr.print_search(ruleset, hyps, fact)
            print("------------------------")



if __name__ == "__main__":
    unittest.main()
