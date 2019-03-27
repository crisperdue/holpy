# Author: Bohua Zhan

from kernel.type import Type, TFun, hol_bool
from kernel.term import Const
from kernel.thm import Thm
from kernel.macro import MacroSig, global_macros
from logic import logic
from logic import nat
from logic import function
from logic.nat import natT
from logic.conv import arg_conv
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
    """Prove a theorem of the form avalI s t n."""
    def __init__(self):
        self.level = 10
        self.sig = MacroSig.TERM

    def get_avalI_th(self, thy, s, t):
        f, args = t.strip_comb()
        if f == N:
            n = args[0]
            return init_theorem(thy, "avalI_const", inst={"s": s, "n": n})
        elif f == V:
            x = args[0]
            pt = init_theorem(thy, "avalI_var", inst={"s": s, "x": x})
            return arg_conv(function.fun_upd_eval_conv()).apply_to_pt(thy, pt)
        elif f == Plus:
            a1, a2 = args
            pt1 = self.get_avalI_th(thy, s, a1)
            pt2 = self.get_avalI_th(thy, s, a2)
            pt = apply_theorem(thy, "avalI_plus", pt1, pt2)
            return arg_conv(nat.nat_conv()).apply_to_pt(thy, pt)
        elif f == Times:
            a1, a2 = args
            pt1 = self.get_avalI_th(thy, s, a1)
            pt2 = self.get_avalI_th(thy, s, a2)
            pt = apply_theorem(thy, "avalI_times", pt1, pt2)
            return arg_conv(nat.nat_conv()).apply_to_pt(thy, pt)
        else:
            raise NotImplementedError

    def get_proof_term(self, thy, args, pts):
        assert len(pts) == 0, "prove_avalI_macro"
        f, args = args.strip_comb()
        s, t, n = args
        pt = self.get_avalI_th(thy, s, t)
        res_n = pt.th.concl.arg
        assert n == res_n, "prove_avalI_macro: wrong result."
        return pt

global_macros.update({
    "prove_avalI": prove_avalI_macro(),
})
