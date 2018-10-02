# Author: Bohua Zhan

import unittest
from kernel.term import *
from kernel.thm import *
from kernel.proof import *

A = Var("A", hol_bool)
B = Var("B", hol_bool)
A_to_B = Term.mk_implies(A,B)

class ProofTest(unittest.TestCase):
    def testProof(self):
        prf = Proof()
        prf.add_item("A1", Thm([A_to_B], A_to_B), "assume", A_to_B, None)
        prf.add_item("A2", Thm([A], A), "assume", A, None)
        prf.add_item("C", Thm([A, A_to_B], B), "implies_elim", None, ["A1", "A2"])

        self.assertEqual(len(prf.get_items()), 3)
        self.assertEqual(prf.get_thm(), Thm([A, A_to_B], B))

        str_prf = "\n".join([
            "A1: implies A B |- implies A B by assume implies A B",
            "A2: A |- A by assume A",
            "C: A, implies A B |- B by implies_elim from A1, A2"])
        
        self.assertEqual(str(prf), str_prf)

if __name__ == "__main__":
    unittest.main()
