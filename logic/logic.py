# Author: Bohua Zhan

from typing import List, Tuple

from kernel.type import TVar, TFun, boolT
from kernel import term
from kernel.term import Term, SVar, Var, Const, Abs
from kernel.thm import Thm
from kernel import theory
from kernel import macro
from logic.conv import Conv, then_conv, all_conv, arg_conv, binop_conv, rewr_conv, \
    top_conv, top_sweep_conv, beta_conv, has_rewrite
from logic.proofterm import ProofTerm, ProofTermDeriv, ProofTermMacro, refl
from logic import matcher
from util import name
from util import typecheck


"""Utility functions for logic."""

conj = Const("conj", TFun(boolT, boolT, boolT))
disj = Const("disj", TFun(boolT, boolT, boolT))
neg = Const("neg", TFun(boolT, boolT))
true = Const("true", boolT)
false = Const("false", boolT)

def exists_t(T):
    return Const("exists", TFun(TFun(T, boolT), boolT))

def is_conj(t):
    """Whether t is of the form A & B."""
    return t.is_binop() and t.head == conj

def mk_conj(*args):
    """Construct the term s1 & ... & sn."""
    if args:
        assert isinstance(args[0], Term), "mk_conj: each argument must be a term"
        if len(args) > 1:
            return conj(args[0], mk_conj(*args[1:]))
        else:
            return args[0]
    else:
        return true

def strip_conj(t):
    """Given term of the form s1 & ... & sn, return the list
    [s1, ..., sn].

    """
    if is_conj(t):
        return [t.arg1] + strip_conj(t.arg)
    else:
        return [t]

def is_disj(t):
    """Whether t is of the form A | B."""
    return t.is_binop() and t.head == disj

def mk_disj(*args):
    """Construct the term s1 | ... | sn."""
    if args:
        assert isinstance(args[0], Term), "mk_disj: each argument must be a term"
        if len(args) > 1:
            return disj(args[0], mk_disj(*args[1:]))
        else:
            return args[0]
    else:
        return false

def strip_disj(t):
    """Given term of the form s1 | ... | sn, return the list
    [s1, ..., sn].

    """
    if is_disj(t):
        return [t.arg1] + strip_disj(t.arg)
    else:
        return [t]

def is_neg(t):
    """Whether t is of the form ~ A."""
    return t.is_comb() and t.fun == neg

def is_exists(t):
    """Whether t is of the form ?x. P x."""
    return t.is_comb() and t.fun.is_const_name("exists") and t.arg.is_abs()

def mk_exists(x, body):
    """Given a variable x and a term P possibly depending on x, return
    the term ?x. P.

    """
    assert x.is_var(), "mk_exists"
    return exists_t(x.T)(Term.mk_abs(x, body))

def is_exists1(t):
    """Whether t is of the form ?!x. P x."""
    return t.is_comb() and t.fun.is_const_name("exists1") and t.arg.is_abs()

def mk_exists1(x, body):
    """Given a variable x and a term P possibly depending on x, return
    the term ?!x. P.

    """
    assert x.is_var(), "mk_exists1"
    exists1_t = Const("exists1", TFun(TFun(x.T, boolT), boolT))
    return exists1_t(Term.mk_abs(x, body))

def is_the(t):
    """Whether t is of the form THE x. P x."""
    return t.is_comb() and t.fun.is_const_name("The") and t.arg.is_abs()

def mk_the(x, body):
    """Given a variable x and a term P possibly depending on x, return
    the term THE x. P.

    """
    assert x.is_var(), "mk_the"
    the_t = Const("The", TFun(TFun(x.T, boolT), x.T))
    return the_t(Term.mk_abs(x, body))

def subst_norm(t, instsp):
    """Substitute using the given instantiation, then normalize with
    respect to beta-conversion.

    """
    tyinst, inst = instsp
    return t.subst_type(tyinst).subst(inst).beta_norm()

def if_t(T):
    return Const("IF", TFun(boolT, T, T, T))

def is_if(t):
    """Whether t is of the form if P then x else y."""
    f, args = t.strip_comb()
    return f.is_const_name("IF") and len(args) == 3

def mk_if(P, x, y):
    """Obtain the term if P then x else y."""
    return if_t(x.get_type())(P, x, y)

def get_forall_names(t, svar=True):
    """Given a term of the form

    !x_1 ... x_k. A_1 --> ... --> A_n --> C.

    return the names x_1, ... x_k.

    """
    def helper(t):
        if Term.is_all(t):
            return [t.arg.var_name] + helper(t.arg.body)
        else:
            return []
    old_names = []
    if not svar:
        old_names = [v.name for v in term.get_vars(t)]
    return name.get_variant_names(helper(t), old_names)

def strip_all_implies(t, names, svar=True):
    """Given a term of the form

    !x_1 ... x_k. A_1 --> ... --> A_n --> C.

    Return the triple ([v_1, ..., v_k], [A_1, ... A_n], C), where
    v_1, ..., v_k are new variables with the given names, and
    A_1, ..., A_n, C are the body of the input term, with bound variables
    substituted for v_1, ..., v_k.

    """
    if Term.is_all(t):
        assert len(names) > 0, "strip_all_implies: not enough names input."
        assert isinstance(names[0], str), "strip_all_implies: names must be strings."
        if svar:
            v = SVar(names[0], t.arg.var_T)
        else:
            v = Var(names[0], t.arg.var_T)
        vars, As, C = strip_all_implies(t.arg.subst_bound(v), names[1:], svar=svar)
        return ([v] + vars, As, C)
    else:
        assert len(names) == 0, "strip_all_implies: too many names input."
        As, C = t.strip_implies()
        return ([], As, C)

def strip_exists(t, names):
    """Given a term of the form

    ?x_1 ... x_k. C

    Return the pair ([v_1, ..., v_k], C), where C is the body of the
    input term, with bound variables substituted for v_1, ..., v_k.

    """
    if is_exists(t):
        assert len(names) > 0, "strip_exists: not enough names input."
        assert isinstance(names[0], str), "strip_exists: names must be strings."
        v = Var(names[0], t.arg.var_T)
        vars, body = strip_exists(t.arg.subst_bound(v), names[1:])
        return ([v] + vars, body)
    else:
        return ([], t)

"""Normalization rules for logic."""

class norm_bool_expr(Conv):
    """Normalize a boolean expression."""
    def get_proof_term(self, thy, t):
        if is_neg(t):
            if t.arg == true:
                return rewr_conv("not_true").get_proof_term(thy, t)
            elif t.arg == false:
                return rewr_conv("not_false").get_proof_term(thy, t)
            else:
                return refl(t)
        else:
            return refl(t)

class norm_conj_assoc_clauses(Conv):
    """Normalize (A_1 & ... & A_n) & (B_1 & ... & B_n)."""
    def get_proof_term(self, thy, t):
        if is_conj(t.arg1):
            return then_conv(
                rewr_conv("conj_assoc", sym=True),
                arg_conv(norm_conj_assoc_clauses())
            ).get_proof_term(thy, t)
        else:
            return all_conv().get_proof_term(thy, t)

class norm_conj_assoc(Conv):
    """Normalize conjunction with respect to associativity."""
    def get_proof_term(self, thy, t):
        if is_conj(t):
            return then_conv(
                binop_conv(norm_conj_assoc()),
                norm_conj_assoc_clauses()
            ).get_proof_term(thy, t)
        else:
            return all_conv().get_proof_term(thy, t)

"""Standard macros in logic."""

class beta_norm_macro(ProofTermMacro):
    """Given theorem th, return the normalization of th."""
    def __init__(self):
        self.level = 1
        self.sig = None
        self.limit = None

    def eval(self, thy, args, ths):
        assert args is None, "beta_norm_macro"
        cv = top_conv(beta_conv())
        eq_th = cv.eval(thy, ths[0].prop)
        return Thm(ths[0].hyps, eq_th.prop.arg)

    def get_proof_term(self, thy, args, pts):
        assert args is None, "beta_norm_macro"
        return top_conv(beta_conv()).apply_to_pt(thy, pts[0])

class intros_macro(ProofTermMacro):
    """Introduce assumptions and variables."""
    def __init__(self):
        self.level = 1
        self.sig = List[Term]
        self.limit = None

    def get_proof_term(self, thy, args, prevs):
        assert len(prevs) >= 1, "intros_macro"
        if args is None:
            args = []
        pt, intros = prevs[-1], prevs[:-1]
        if len(prevs) == 1:
            return apply_theorem(thy, 'trivial', pt)

        for intro in reversed(intros):
            if intro.th.prop.is_VAR():  # variable case
                pt = ProofTerm.forall_intr(intro.prop.arg, pt)
            elif len(args) > 0 and intro.th.prop == args[0]:  # exists case
                assert is_exists(intro.prop), "intros_macro"
                pt = apply_theorem(thy, 'exE', intro, pt)
                args = args[1:]
            else:  # assume case
                assert len(intro.th.hyps) == 1 and intro.th.hyps[0] == intro.th.prop, \
                    "intros_macro"
                pt = ProofTerm.implies_intr(intro.prop, pt)
        return pt

class apply_theorem_macro(ProofTermMacro):
    """Apply existing theorem in the theory to a list of current
    results in the proof.

    If with_inst is set, the signature is (th_name, tyinst, inst),
    where th_name is the name of the theorem, and tyinst, inst are
    the instantiations of type and term variables.

    If with_inst is not set, the signature is th_name, where th_name
    is the name of the theorem.

    """
    def __init__(self, *, with_inst=False):
        self.level = 1
        self.with_inst = with_inst
        self.sig = Tuple[str, macro.TyInst, macro.Inst] if with_inst else str
        self.limit = None

    def eval(self, thy, args, prevs):
        tyinst, inst = dict(), dict()
        if self.with_inst:
            name, tyinst, inst = args
        else:
            name = args
        th = thy.get_theorem(name, svar=True)
        As, C = th.prop.strip_implies()

        assert len(prevs) <= len(As), "apply_theorem: too many prevs."

        pats = As[:len(prevs)]
        ts = [prev_th.prop for prev_th in prevs]
        matcher.first_order_match_list_incr(pats, ts, (tyinst, inst))

        As, C = subst_norm(th.prop, (tyinst, inst)).strip_implies()
        new_prop = Term.mk_implies(*(As[len(prevs):] + [C]))

        prev_hyps = sum([prev.hyps for prev in prevs], ())
        th = Thm(th.hyps + prev_hyps, new_prop)

        assert len(term.get_stvars(new_prop)) == 0, "apply_theorem: unmatched type variables."
        vars = term.get_svars(new_prop)
        for v in reversed(vars):
            th = Thm.forall_intr(v, th)
        return th

    def get_proof_term(self, thy, args, pts):
        tyinst, inst = dict(), dict()
        if self.with_inst:
            name, tyinst, inst = args
        else:
            name = args
        th = thy.get_theorem(name, svar=True)
        As, C = th.prop.strip_implies()

        assert len(pts) <= len(As), "apply_theorem: too many prevs."

        pats = As[:len(pts)]
        ts = [pt.prop for pt in pts]
        matcher.first_order_match_list_incr(pats, ts, (tyinst, inst))

        pt = ProofTerm.theorem(thy, name)
        if tyinst:
            pt = ProofTerm.subst_type(tyinst, pt)
        if inst:
            pt = ProofTerm.substitution(inst, pt)
        if pt.prop.beta_norm() != pt.prop:
            pt = top_conv(beta_conv()).apply_to_pt(thy, pt)
        for prev_pt in pts:
            pt = ProofTerm.implies_elim(pt, prev_pt)

        assert len(term.get_stvars(pt.prop)) == 0, "apply_theorem: unmatched type variables."
        vars = term.get_svars(pt.prop)
        for v in reversed(vars):
            pt = ProofTerm.forall_intr(v, pt)

        return pt

class apply_fact_macro(ProofTermMacro):
    """Apply a given fact to a list of facts. The first input fact is
    in the forall-implies form. Apply this fact to the remaining
    input facts. If with_inst is set, use the given sequence of terms
    as the instantiation.
    
    """
    def __init__(self, *, with_inst=False):
        self.level = 1
        self.with_inst = with_inst
        self.sig = List[Term] if with_inst else None
        self.limit = None

    def get_proof_term(self, thy, args, pts):
        if not self.with_inst:
            assert len(pts) >= 2, "apply fact: too few prevs"

        pt, pt_prevs = pts[0], pts[1:]

        # First, obtain the patterns
        new_names = get_forall_names(pt.prop)

        new_vars, As, C = strip_all_implies(pt.prop, new_names)
        assert len(pt_prevs) <= len(As), "apply_fact: too many prevs"

        if self.with_inst:
            assert len(args) == len(new_names), "apply_fact_macro: wrong number of args."
            tyinst, inst = {}, {nm: v for nm, v in zip(new_names, args)}
        else:
            tyinst, inst = dict(), dict()
            for idx, pt_prev in enumerate(pt_prevs):
                matcher.first_order_match_incr(As[idx], pt_prev.prop, (tyinst, inst))

        if tyinst:
            pt = ProofTerm.subst_type(tyinst, pt)
        for new_var in new_vars:
            if new_var.name in inst:
                pt = ProofTerm.forall_elim(inst[new_var.name], pt)
            else:
                pt = ProofTerm.forall_elim(new_var, pt)
        if pt.prop.beta_norm() != pt.prop:
            pt = top_conv(beta_conv()).apply_to_pt(thy, pt)
        for prev_pt in pt_prevs:
            if prev_pt.prop != pt.assums[0]:
                prev_pt = top_conv(beta_conv()).apply_to_pt(thy, prev_pt)
            pt = ProofTerm.implies_elim(pt, prev_pt)
        for new_var in new_vars:
            if new_var.name not in inst:
                pt = ProofTerm.forall_intr(new_var, pt)

        return pt

class rewrite_goal_macro(ProofTermMacro):
    """Apply an existing equality theorem to rewrite a goal.

    The signature is (name, goal), where name is the name of the
    equality theorem. Goal is the statement of the goal.

    Rewrite the goal using the equality theorem. The result must
    be equal to prev[0].

    The remainder of prev are theorems to be used to discharge
    assumptions in conversion.
    
    sym - whether to apply the given equality in the backward direction.

    """
    def __init__(self, *, sym=False):
        self.level = 1
        self.sym = sym
        self.sig = Tuple[str, Term]
        self.limit = None

    def eval(self, thy, args, ths):
        assert isinstance(args, tuple) and len(args) == 2 and \
               isinstance(args[0], str) and isinstance(args[1], Term), "rewrite_goal: signature"

        # Simply produce the goal
        _, goal = args
        return Thm(sum([th.hyps for th in ths], ()), goal)

    def get_proof_term(self, thy, args, pts):
        assert isinstance(args, tuple) and len(args) == 2 and \
               isinstance(args[0], str) and isinstance(args[1], Term), "rewrite_goal: signature"

        name, goal = args
        eq_pt = ProofTerm.theorem(thy, name)

        if len(pts) == len(eq_pt.assums):
            rewr_cv = rewr_conv(eq_pt, sym=self.sym, conds=pts)
        else:
            assert len(pts) == len(eq_pt.assums) + 1, "rewrite_goal: wrong number of prevs"
            rewr_cv = rewr_conv(eq_pt, sym=self.sym, conds=pts[1:])

        cv = then_conv(top_sweep_conv(rewr_cv),
                       top_conv(beta_conv()))
        pt = cv.get_proof_term(thy, goal)  # goal = th.prop
        pt = ProofTerm.symmetric(pt)  # th.prop = goal
        if Term.is_equals(pt.prop.lhs) and pt.prop.lhs.lhs == pt.prop.lhs.rhs:
            pt = ProofTerm.equal_elim(pt, ProofTerm.reflexive(pt.prop.lhs.lhs))
        else:
            pt = ProofTerm.equal_elim(pt, pts[0])  # goal

        return pt

class rewrite_fact_macro(ProofTermMacro):
    """Rewrite a fact in the proof using a theorem."""
    def __init__(self, *, sym=False):
        self.level = 1
        self.sym = sym
        self.sig = str
        self.limit = None

    def get_proof_term(self, thy, args, pts):
        assert isinstance(args, str), "rewrite_fact_macro: signature"

        th_name = args
        eq_pt = ProofTerm.theorem(thy, th_name)

        assert len(pts) == len(eq_pt.assums) + 1, "rewrite_fact_macro: signature"

        # Check rewriting using the theorem has an effect
        assert has_rewrite(thy, th_name, pts[0].prop, sym=self.sym, conds=pts[1:]), "rewrite_fact"

        cv = then_conv(top_sweep_conv(rewr_conv(eq_pt, sym=self.sym, conds=pts[1:])),
                       top_conv(beta_conv()))
        return pts[0].on_prop(thy, cv)

class rewrite_goal_with_prev_macro(ProofTermMacro):
    """Given an input equality theorem and a goal, the macro rewrites
    the goal to a new form. The new goal, if it is not a reflexivity, is
    resolved using the second input theorem. The remaining input theorems
    are used to resolve conditions that arise when applying the equality.

    """
    def __init__(self, *, sym=False):
        self.level = 1
        self.sym = sym
        self.sig = Term
        self.limit = None

    def get_proof_term(self, thy, args, pts):
        assert isinstance(args, Term), "rewrite_goal_macro: signature"

        goal = args
        eq_pt = pts[0]

        new_names = get_forall_names(eq_pt.prop)
        new_vars, _, _ = strip_all_implies(eq_pt.prop, new_names)

        for new_var in new_vars:
            eq_pt = ProofTerm.forall_elim(new_var, eq_pt)

        pts = pts[1:]

        cv = then_conv(top_sweep_conv(rewr_conv(eq_pt, sym=self.sym)),
                       top_conv(beta_conv()))
        pt = cv.get_proof_term(thy, goal)  # goal = th.prop
        pt = ProofTerm.symmetric(pt)  # th.prop = goal
        if pt.prop.lhs.is_reflexive():
            pt = ProofTerm.equal_elim(pt, ProofTerm.reflexive(pt.prop.lhs.rhs))
        else:
            pt = ProofTerm.equal_elim(pt, pts[0])
            pts = pts[1:]

        for A in pts:
            pt = ProofTerm.implies_elim(ProofTerm.implies_intr(A.prop, pt), A)
        return pt

class rewrite_fact_with_prev_macro(ProofTermMacro):
    """This macro is provided with two input theorems. The first input
    theorem is an equality, which is used to rewrite the second input
    theorem.

    """
    def __init__(self):
        self.level = 1
        self.sig = None
        self.limit = None

    def get_proof_term(self, thy, args, pts):
        assert len(pts) == 2, "rewrite_fact_with_prev"

        eq_pt, pt = pts

        # In general, we assume eq_pt has forall quantification
        # First, obtain the patterns
        new_names = get_forall_names(eq_pt.prop)
        new_vars, eq_As, eq_C = strip_all_implies(eq_pt.prop, new_names)

        # First fact must be an equality
        assert len(eq_As) == 0 and eq_C.is_equals(), "rewrite_fact_with_prev"

        for new_var in new_vars:
            eq_pt = ProofTerm.forall_elim(new_var, eq_pt)

        # Check rewriting using eq_pt has an effect
        cv1 = top_sweep_conv(rewr_conv(eq_pt))
        assert not cv1.eval(thy, pt.prop).is_reflexive(), "rewrite_fact_with_prev"

        cv = then_conv(cv1, top_conv(beta_conv()))
        return pt.on_prop(thy, cv)

class trivial_macro(ProofTermMacro):
    """Prove a proposition of the form A_1 --> ... --> A_n --> B, where
    B agrees with one of A_i.

    """
    def __init__(self):
        self.level = 1
        self.sig = Term
        self.limit = None

    def can_eval(self, thy, args):
        new_names = get_forall_names(args)
        vars, As, C = strip_all_implies(args, new_names)
        return C in As

    def get_proof_term(self, thy, args, pts):
        new_names = get_forall_names(args)
        vars, As, C = strip_all_implies(args, new_names)
        assert C in As, "trivial_macro"

        pt = ProofTerm.assume(C)
        for A in reversed(As):
            pt = ProofTerm.implies_intr(A, pt)
        for v in reversed(vars):
            pt = ProofTerm.forall_intr(v, pt)
        return pt

class resolve_theorem_macro(ProofTermMacro):
    """Given a theorem of the form ~A, and a fact A, prove any goal."""
    def __init__(self):
        self.level = 1
        self.sig = Tuple[str, Term]
        self.limit = None

    def get_proof_term(self, thy, args, pts):
        th_name, goal = args
        pt = ProofTerm.theorem(thy, th_name)
        assert is_neg(pt.prop), "resolve_theorem_macro"

        # Match for variables in pt.
        tyinst, inst = matcher.first_order_match(pt.prop.arg, pts[0].prop)
        if tyinst:
            pt = ProofTerm.subst_type(tyinst, pt)
        if inst:
            pt = ProofTerm.substitution(inst, pt)

        pt = apply_theorem(thy, 'negE', pt, pts[0])  # false
        return apply_theorem(thy, 'falseE', pt, concl=goal)


def apply_theorem(thy, th_name, *pts, concl=None, tyinst=None, inst=None):
    """Wrapper for apply_theorem and apply_theorem_for macros.

    The function takes optional arguments concl, tyinst, and inst. Matching
    always starts with tyinst and inst. If conclusion is specified, it is
    matched next. Finally, the assumptions are matched.

    """
    typecheck.checkinstance('apply_theorem', pts, [ProofTerm])
    if concl is None and tyinst is None and inst is None:
        # Normal case, can use apply_theorem
        return ProofTermDeriv("apply_theorem", thy, th_name, pts)
    else:
        pt = ProofTerm.theorem(thy, th_name)
        if tyinst is None:
            tyinst = dict()
        if inst is None:
            inst = dict()
        if concl is not None:
            matcher.first_order_match_incr(pt.concl, concl, (tyinst, inst))
        for i, prev in enumerate(pts):
            matcher.first_order_match_incr(pt.assums[i], prev.prop, (tyinst, inst))
        return ProofTermDeriv("apply_theorem_for", thy, (th_name, tyinst, inst), pts)

def conj_thms(thy, *pts):
    assert len(pts) > 0, 'conj_thms: input list is empty.'
    if len(pts) == 1:
        return pts[0]
    else:
        return apply_theorem(thy, 'conjI', pts[0], conj_thms(thy, *pts[1:]))


class imp_conj_macro(ProofTermMacro):
    def __init__(self):
        self.level = 1
        self.sig = Term
        self.limit = None

    def eval(self, thy, args, ths):
        def strip(t):
            if is_conj(t):
                return strip(t.arg1).union(strip(t.arg))
            else:
                return {t}

        As, C = args.strip_implies()
        assert len(As) == 1, 'imp_conj_macro'
        assert strip(C).issubset(strip(As[0])), 'imp_conj_macro'
        return Thm([], args)

    def get_proof_term(self, thy, args, pts):
        dct = dict()

        def traverse_A(pt):
            # Given proof term showing a conjunction, put proof terms
            # showing atoms of the conjunction in dct.
            if is_conj(pt.prop):
                traverse_A(apply_theorem(thy, 'conjD1', pt))
                traverse_A(apply_theorem(thy, 'conjD2', pt))
            else:
                dct[pt.prop] = pt

        def traverse_C(t):
            # Return proof term with conclusion t
            if is_conj(t):
                left = traverse_C(t.arg1)
                right = traverse_C(t.arg)
                return apply_theorem(thy, 'conjI', left, right)
            else:
                assert t in dct.keys(), 'imp_conj_macro'
                return dct[t]

        As, C = args.strip_implies()
        assert len(As) == 1, 'imp_conj_macro'
        A = As[0]

        traverse_A(ProofTerm.assume(A))
        concl = traverse_C(C)
        return ProofTerm.implies_intr(A, concl)


macro.global_macros.update({
    "beta_norm": beta_norm_macro(),
    "intros": intros_macro(),
    "apply_theorem": apply_theorem_macro(),
    "apply_theorem_for": apply_theorem_macro(with_inst=True),
    "resolve_theorem": resolve_theorem_macro(),
    "apply_fact": apply_fact_macro(),
    "apply_fact_for": apply_fact_macro(with_inst=True),
    "rewrite_goal": rewrite_goal_macro(),
    "rewrite_goal_sym": rewrite_goal_macro(sym=True),
    "rewrite_goal_with_prev": rewrite_goal_with_prev_macro(),
    "rewrite_goal_with_prev_sym": rewrite_goal_with_prev_macro(sym=True),
    "rewrite_fact": rewrite_fact_macro(),
    "rewrite_fact_sym": rewrite_fact_macro(sym=True),
    "rewrite_fact_with_prev": rewrite_fact_with_prev_macro(),
    "trivial": trivial_macro(),
    "imp_conj": imp_conj_macro(),
})
