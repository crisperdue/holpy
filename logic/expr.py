# Author: Bohua Zhan

from kernel.type import Type, TFun, hol_bool
from kernel.term import Const
from kernel.thm import Thm
from logic import nat
from logic.nat import natT
from logic.proofterm import ProofTermMacro, ProofTerm
from logic.logic_macro import apply_theorem, init_theorem

"""Automation for arithmetic expressions."""

aexpT = Type("aexp")

N = Const("N", TFun(natT, aexpT))
V = Const("V", TFun(natT, aexpT))
Plus = Const("Plus", TFun(aexpT, aexpT, aexpT))
Times = Const("Times", TFun(aexpT, aexpT, aexpT))

avalI = Const("avalI", TFun(TFun(natT, natT), aexpT, natT, hol_bool))

class prove_avalI_macro(ProofTermMacro):
    """Given a state s and an expression t, return a theorem of
    the form avalI s t n, where n is a constant natural number.

    """
    def __init__(self):
        pass

    def get_proof_term(self, thy, args, *pts):
        s, t = args
        f, args = t.strip_comb()
        if f == N:
            n = args[0]
            return init_theorem(thy, "avalI_const", inst={"s": s, "n": n})
        elif f == V:
            x = args[0]
            return init_theorem(thy, "avalI_var", inst={"s": s, "x": x})
        elif f == Plus:
            a1, a2 = args
            pt1 = self.get_proof_term(thy, (s, a1))
            pt2 = self.get_proof_term(thy, (s, a2))
            _, args1 = pt1.th.concl.strip_comb()
            _, args2 = pt2.th.concl.strip_comb()
            return apply_theorem(thy, "avalI_plus", pt1, pt2)
        elif f == Times:
            a1, a2 = args
            pt1 = self.get_proof_term(thy, (s, a1))
            pt2 = self.get_proof_term(thy, (s, a2))
            _, args1 = pt1.th.concl.strip_comb()
            _, args2 = pt2.th.concl.strip_comb()
            return apply_theorem(thy, "avalI_times", pt1, pt2)
        else:
            raise NotImplementedError
