# Author: Bohua Zhan

import unittest
import io

from kernel.type import TVar, TFun, hol_bool
from kernel.term import Term, Var
from kernel.thm import Thm
from kernel.proof import Proof
from kernel.report import ProofReport
from logic import logic
from logic import basic
from logic import nat
from logic import list
from syntax import printer
from server import tactic
from server.tactic import ProofState

thy = basic.loadTheory('logic_base')

A = Var("A", hol_bool)
B = Var("B", hol_bool)
conj = logic.mk_conj
disj = logic.mk_disj
imp = Term.mk_implies
neg = logic.neg
exists = logic.mk_exists

class TacticTest(unittest.TestCase):
    def testIncrIdAfter(self):
        test_data = [
            (((0,), (0,), 1), (1,),),
            (((0, 1), (0,), 1), (1, 1)),
            (((1,), (2, 2), 1), (1,)),
            (((2, 1), (2, 2), 1), (2, 1)),
            (((2, 2), (2, 2), 1), (2, 3)),
            (((2, 3, 2), (2, 2), 1), (2, 4, 2)),
            (((3,), (2, 2), 1), (3,)),
        ]

        for (id, start, n), res in test_data:
            self.assertEqual(tactic.incr_id_after(id, start, n), res)

    def testInitProof(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        self.assertEqual(len(state.prf.items), 3)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testParseInitState(self):
        state = ProofState.parse_init_state(
            thy, {'vars': {'A': 'bool', 'B': 'bool'}, 'prop': "A & B --> B & A"})
        self.assertEqual(len(state.prf.items), 3)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testJsonData(self):
        state = ProofState.parse_init_state(
            thy, {'vars': {'A': 'bool', 'B': 'bool'}, 'prop': "A & B --> B & A"})
        json_data = state.json_data()
        self.assertEqual(len(json_data['vars']), 2)
        self.assertEqual(len(json_data['proof']), 3)
        self.assertIn('report', json_data)

    def testParseProof(self):
        data = {
            'vars': {'A': 'bool', 'B': 'bool'},
            'proof': [
                {'id': 0, 'rule': 'assume', 'args': 'A & B', 'prevs': [], 'th': ''},
                {'id': 1, 'rule': 'sorry', 'args': '', 'prevs': [], 'th': 'A & B |- B & A'},
                {'id': 2, 'rule': 'implies_intr', 'args': 'A & B', 'prevs': [1], 'th': ''}
            ]
        }
        state = ProofState.parse_proof(thy, data)
        self.assertEqual(len(state.vars), 2)
        self.assertEqual(len(state.prf.items), 3)

    def testGetCtxt(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        self.assertEqual(state.get_ctxt(0), {'A':hol_bool, 'B':hol_bool})

    def testAddLineAfter(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        
        state.add_line_after(0)
        self.assertEqual(len(state.prf.items), 4)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))
        self.assertEqual(state.prf.items[1].rule, "")

    def testAddLineAfter2(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))

        state.add_line_after(1)
        self.assertEqual(len(state.prf.items), 4)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))
        self.assertEqual(state.prf.items[2].rule, "")

    def testAddLineBefore(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))

        state.add_line_before(2, 1)
        self.assertEqual(len(state.prf.items), 4)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

        state.add_line_before(2, 3)
        self.assertEqual(len(state.prf.items), 7)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testRemoveLine(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        state.add_line_after(1)
        state.remove_line(2)
        self.assertEqual(len(state.prf.items), 3)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testSetLine(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        state.add_line_after(1)
        state.set_line(2, "theorem", args="conjD1")
        self.assertEqual(len(state.prf.items), 4)
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testApplyBackwardStepThms(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        ths = state.apply_backward_step_thms(1)
        self.assertEqual([name for name, _ in ths], ["conjI"])

    def testApplyBackwardStepThms2(self):
        state = ProofState.init_state(thy, [A, B], [disj(A, B)], disj(B, A))
        ths = state.apply_backward_step_thms(1, prevs=[0])
        self.assertEqual([name for name, _ in ths], ["disjE"])

    def testApplyBackwardStepThms3(self):
        """Example of two results."""
        state = ProofState.init_state(thy, [A, B], [disj(A, B)], disj(B, A))
        ths = state.apply_backward_step_thms(1)
        self.assertEqual([name for name, _ in ths], ["disjI1", "disjI2"])

    def testApplyBackwardStep(self):
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        state.apply_backward_step(1, "conjI")
        self.assertEqual(state.check_proof(), Thm.mk_implies(conj(A, B), conj(B, A)))
        self.assertEqual(len(state.rpt.gaps), 2)

    def testApplyBackwardStep2(self):
        """Case where one or more assumption also needs to be matched."""
        state = ProofState.init_state(thy, [A, B], [disj(A, B)], disj(B, A))
        state.apply_backward_step(1, "disjE", prevs=[0])
        self.assertEqual(state.check_proof(), Thm.mk_implies(disj(A, B), disj(B, A)))
        self.assertEqual(len(state.rpt.gaps), 2)

    def testIntroduction(self):
        state = ProofState.init_state(thy, [A, B], [], imp(disj(A, B), disj(B, A)))
        state.introduction(0)
        self.assertEqual(state.check_proof(), Thm.mk_implies(disj(A, B), disj(B, A)))

    def testIntroduction2(self):
        state = ProofState.init_state(thy, [A, B], [], imp(A, B, conj(A, B)))
        state.introduction(0)
        self.assertEqual(state.check_proof(), Thm.mk_implies(A, B, conj(A, B)))

    def testIntroduction3(self):
        Ta = TVar("a")
        A = Var("A", TFun(Ta, hol_bool))
        B = Var("B", TFun(Ta, hol_bool))
        x = Var("x", Ta)
        state = ProofState.init_state(thy, [A, B], [], Term.mk_all(x, imp(A(x), B(x))))
        state.introduction(0, ["x"])
        self.assertEqual(state.check_proof(), Thm([], Term.mk_all(x, imp(A(x), B(x)))))
        self.assertEqual(len(state.prf.items), 1)
        self.assertEqual(len(state.prf.items[0].subproof.items), 5)

    def testApplyInduction(self):
        thy = basic.loadTheory('nat')
        n = Var("n", nat.natT)
        state = ProofState.init_state(thy, [n], [], Term.mk_equals(nat.plus(n, nat.zero), n))
        state.apply_induction(0, "nat_induct", "n")
        self.assertEqual(state.check_proof(), Thm([], Term.mk_equals(nat.plus(n, nat.zero), n)))
        self.assertEqual(len(state.prf.items), 3)

    def testConjComm(self):
        """Proof of A & B --> B & A."""
        state = ProofState.init_state(thy, [A, B], [conj(A, B)], conj(B, A))
        state.apply_backward_step(1, "conjI")
        state.set_line(1, "apply_theorem", args="conjD2", prevs=[0])
        state.set_line(2, "apply_theorem", args="conjD1", prevs=[0])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_implies(conj(A, B), conj(B, A)))

    def testDisjComm(self):
        """Proof of A | B --> B | A."""
        state = ProofState.init_state(thy, [A, B], [disj(A, B)], disj(B, A))
        state.apply_backward_step(1, "disjE", prevs=[0])
        state.introduction(1)
        state.apply_backward_step((1, 1), "disjI2", prevs=[(1, 0)])
        state.introduction(2)
        state.apply_backward_step((2, 1), "disjI1", prevs=[(2, 0)])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_implies(disj(A, B), disj(B, A)))

    def testDoubleNegInv(self):
        """Proof of ~~A --> A."""
        state = ProofState.init_state(thy, [A], [neg(neg(A))], A)
        state.add_line_after(0)
        state.set_line(1, "theorem", args="classical")
        state.apply_backward_step(2, "disjE", prevs=[1])
        state.introduction(2)
        state.introduction(3)
        state.apply_backward_step((3, 1), "falseE")
        state.apply_backward_step((3, 1), "negE", prevs=[0])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_implies(neg(neg(A)), A))

    def testExistsConj(self):
        """Proof of (?x. A x & B x) --> (?x. A x) & (?x. B x)."""
        Ta = TVar("a")
        A = Var("A", TFun(Ta, hol_bool))
        B = Var("B", TFun(Ta, hol_bool))
        x = Var("x", Ta)
        ex_conj = exists(x,conj(A(x),B(x)))
        conj_ex = conj(exists(x,A(x)),exists(x,B(x)))
        state = ProofState.init_state(thy, [A, B], [ex_conj], conj_ex)
        state.apply_backward_step(1, "conjI")
        state.apply_backward_step(1, "exE", prevs=[0])
        state.introduction(1, "x")
        state.add_line_after((1, 1))
        state.set_line((1, 2), "apply_theorem", args="conjD1", prevs=[(1, 1)])
        state.apply_backward_step((1, 3), "exI", prevs=[(1, 2)])
        state.apply_backward_step(3, "exE", prevs=[0])
        state.introduction(3, "x")
        state.add_line_after((3, 1))
        state.set_line((3, 2), "apply_theorem", args="conjD2", prevs=[(3, 1)])
        state.apply_backward_step((3, 3), "exI", prevs=[(3, 2)])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_implies(ex_conj, conj_ex))

    def testAddZeroRight(self):
        """Proof of n + 0 = n by induction."""
        thy = basic.loadTheory('nat')
        n = Var("n", nat.natT)
        state = ProofState.init_state(thy, [n], [], Term.mk_equals(nat.plus(n, nat.zero), n))
        state.apply_induction(0, "nat_induct", "n")
        state.rewrite_goal(0, "plus_def_1")
        state.set_line(0, "reflexive", args=nat.zero)
        state.introduction(2, names=["n"])
        state.rewrite_goal((2, 2), "plus_def_2")
        state.set_line((2, 2), "arg_combination", args=nat.Suc, prevs=[(2, 1)])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_equals(nat.plus(n,nat.zero),n))

    def testMultZeroRight(self):
        """Proof of n * 0 = 0 by induction."""
        thy = basic.loadTheory('nat')
        n = Var("n", nat.natT)
        state = ProofState.init_state(thy, [n], [], Term.mk_equals(nat.times(n, nat.zero), nat.zero))
        state.apply_induction(0, "nat_induct", "n")
        state.rewrite_goal(0, "times_def_1")
        state.set_line(0, "reflexive", args=nat.zero)
        state.introduction(2, names=["n"])
        state.rewrite_goal((2, 2), "times_def_2")
        state.rewrite_goal((2, 2), "plus_def_1")
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_equals(nat.times(n,nat.zero),nat.zero))

    def testAppendNil(self):
        """Proof of xs @ [] = xs by induction."""
        thy = basic.loadTheory('list')
        Ta = TVar("a")
        xs = Var("xs", list.listT(Ta))
        nil = list.nil(Ta)
        state = ProofState.init_state(thy, [xs], [], Term.mk_equals(list.mk_append(xs, nil), xs))
        state.apply_induction(0, "list_induct", "xs")
        state.apply_backward_step(0, "append_def_1")
        state.introduction(1, names=["x", "xs"])
        state.rewrite_goal((1, 3), "append_def_2")
        self.assertEqual(state.get_ctxt((1, 3)), {'x': Ta, 'xs': list.listT(Ta)})
        state.set_line((1, 3), "arg_combination", args=list.cons(Ta)(Var("x",Ta)), prevs=[(1, 2)])
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_equals(list.mk_append(xs, nil), xs))

    def testRewriteGoalThms(self):
        thy = basic.loadTheory('nat')
        n = Var("n", nat.natT)
        state = ProofState.init_state(thy, [n], [], Term.mk_equals(nat.plus(nat.zero, n), n))
        ths = state.rewrite_goal_thms((0,))
        self.assertEqual([name for name, _ in ths], ["add_comm", "plus_def_1"])

    def testRewriteGoalWithAssum(self):
        Ta = TVar("a")
        a = Var("a", Ta)
        b = Var("b", Ta)
        eq_a = Term.mk_equals(a, a)
        if_t = logic.mk_if(eq_a, b, a)
        state = ProofState.init_state(thy, [a, b], [], Term.mk_equals(if_t, b))
        state.rewrite_goal(0, "if_P")
        state.set_line(0, "reflexive", args=b)
        state.set_line(1, "reflexive", args=a)
        self.assertEqual(state.check_proof(no_gaps=True), Thm.mk_equals(if_t, b))


if __name__ == "__main__":
    unittest.main()
