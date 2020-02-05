# Author: Bohua Zhan

from kernel.type import TyInst
from kernel import term
from kernel.term import Term, Implies, Not, Lambda, Inst
from kernel.thm import Thm
from kernel import theory
from logic import logic
from logic import matcher
from logic.conv import then_conv, top_conv, rewr_conv, beta_conv, beta_norm_conv, \
    top_sweep_conv, has_rewrite
from kernel.proofterm import ProofTerm, ProofTermDeriv
from logic.logic import apply_theorem


class Tactic:
    """Represents a tactic function.

    A tactic takes a target theorem, and returns a proof term
    containing zero or more sorries. Tactics can be combined in the
    usual manner.

    get_proof_term can be supplied with two more arguments: args
    for extra data provided to the tactic, and prevs for the list
    of existing facts to use.

    """
    def get_proof_term(self, goal, *, args=None, prevs=None):
        raise NotImplementedError


class MacroTactic(Tactic):
    """Construct a tactic from a macro.
    
    The name of the macro is provided at initialization. The first
    argument of the macro must be the goal statement. The remaining
    arguments are supplied by the tactic.
    
    """
    def __init__(self, macro):
        self.macro = macro

    def get_proof_term(self, goal, *, args=None, prevs=None):
        assert isinstance(goal, Thm), "MacroTactic"
        if prevs is None:
            prevs = []

        if args is None:
            args = goal.prop
        else:
            args = (goal.prop,) + args

        return ProofTermDeriv(self.macro, args, prevs)

class rule(Tactic):
    """Apply a theorem in the backward direction.
    
    args is either a pair of theorem name and instantiation, or the
    theorem name alone.

    """
    def get_proof_term(self, goal, *, args=None, prevs=None):
        if isinstance(args, tuple):
            th_name, inst = args
        else:
            th_name, inst = args, None
        assert isinstance(th_name, str), "rule: theorem name must be a string"

        if prevs is None:
            prevs = []
        
        th = theory.get_theorem(th_name)
        As, C = th.assums, th.concl

        # Length of prevs is at most length of As
        assert len(prevs) <= len(As), "rule: too many previous facts"
        if inst is None:
            inst = Inst()

        # Match the conclusion and assumptions. Either the conclusion
        # or the list of assumptions must be a first-order pattern.
        if matcher.is_pattern(C, []):
            matcher.first_order_match_incr(C, goal.prop, inst)
            for pat, prev in zip(As, prevs):
                matcher.first_order_match_incr(pat, prev.prop, inst)
        else:
            for pat, prev in zip(As, prevs):
                matcher.first_order_match_incr(pat, prev.prop, inst)
            matcher.first_order_match_incr(C, goal.prop, inst)

        # Check that every variable in the theorem has an instantiation.
        unmatched_vars = [v.name for v in term.get_svars(As + [C]) if v.name not in inst]
        if unmatched_vars:
            raise theory.ParameterQueryException(list("param_" + name for name in unmatched_vars))

        # Substitute and normalize
        As, _ = th.prop.subst_norm(inst).strip_implies()
        goal_Alen = len(goal.assums)
        if goal_Alen > 0:
            As = As[:-goal_Alen]

        pts = prevs + [ProofTerm.sorry(Thm(goal.hyps, A)) for A in As[len(prevs):]]

        # Determine whether it is necessary to provide instantiation
        # to apply_theorem.
        if set(term.get_svars(th.assums)) != set(term.get_svars(th.prop)) or \
           set(term.get_stvars(th.assums)) != set(term.get_stvars(th.prop)) or \
           not matcher.is_pattern_list(th.assums, []):
            return apply_theorem(th_name, *pts, inst=inst)
        else:
            return apply_theorem(th_name, *pts)

class resolve(Tactic):
    """Given any goal, a theorem of the form ~A, and an existing fact A,
    solve the goal.
    
    """
    def get_proof_term(self, goal, args, prevs):
        assert isinstance(args, str) and len(prevs) == 1, "resolve: type"
        th_name = args
        th = theory.get_theorem(th_name)

        assert th.prop.is_not(), "resolve: prop is not a negation"

        # Checking that the theorem matches the fact is done here.
        return ProofTermDeriv('resolve_theorem', (args, goal.prop), prevs)

class intros(Tactic):
    """Given a goal of form !x_1 ... x_n. A_1 --> ... --> A_n --> C,
    introduce variables for x_1, ..., x_n and assumptions for A_1, ..., A_n.
    
    """
    def get_proof_term(self, goal, *, args=None, prevs=None):
        if args is None:
            var_names = []
        else:
            var_names = args

        vars, As, C = logic.strip_all_implies(goal.prop, var_names, svar=False)
        
        pt = ProofTerm.sorry(Thm(list(goal.hyps) + As, C))
        ptAs = [ProofTerm.assume(A) for A in As]
        ptVars = [ProofTerm.variable(var.name, var.T) for var in vars]
        return ProofTermDeriv('intros', None, ptVars + ptAs + [pt])

class var_induct(Tactic):
    """Apply induction rule on a variable."""
    def get_proof_term(self, goal, *, args=None, prevs=None):
        th_name, var = args
        P = Lambda(var, goal.prop)
        th = theory.get_theorem(th_name)
        f, args = th.concl.strip_comb()
        if len(args) != 1:
            raise NotImplementedError
        inst = matcher.first_order_match(args[0], var)
        inst[f.name] = P
        return rule().get_proof_term(goal, args=(th_name, inst))

class rewrite_goal(Tactic):
    """Rewrite the goal using a theorem."""
    def __init__(self, *, sym=False):
        self.sym = sym

    def get_proof_term(self, goal, *, args=None, prevs=None):
        th_name = args
        C = goal.prop

        # Check whether rewriting using the theorem has an effect
        assert has_rewrite(th_name, C, sym=self.sym, conds=prevs), \
            "rewrite: unable to apply theorem."

        cv = then_conv(top_sweep_conv(rewr_conv(th_name, sym=self.sym, conds=prevs)),
                       beta_norm_conv())
        eq_th = cv.eval(C)
        new_goal = eq_th.prop.rhs

        if self.sym:
            macro_name = 'rewrite_goal_sym'
        else:
            macro_name = 'rewrite_goal'
        if new_goal.is_equals() and new_goal.lhs == new_goal.rhs:
            return ProofTermDeriv(macro_name, args=(th_name, C), prevs=prevs)
        else:
            new_goal = ProofTerm.sorry(Thm(goal.hyps, new_goal))
            assert new_goal.prop != goal.prop, "rewrite: unable to apply theorem"
            return ProofTermDeriv(macro_name, args=(th_name, C), prevs=[new_goal] + prevs)

class rewrite_goal_with_prev(Tactic):
    def get_proof_term(self, goal, *, args=None, prevs=None):
        assert isinstance(prevs, list) and len(prevs) == 1, "rewrite_goal_with_prev"
        pt = prevs[0]
        C = goal.prop

        # In general, we assume pt.th has forall quantification.
        # First, obtain the patterns
        new_names = logic.get_forall_names(pt.prop)
        new_vars, prev_As, prev_C = logic.strip_all_implies(pt.prop, new_names)

        # Fact used must be an equality
        assert len(prev_As) == 0 and prev_C.is_equals(), "rewrite_goal_with_prev"

        for new_var in new_vars:
            pt = pt.forall_elim(new_var)

        # Check whether rewriting using the theorem has an effect
        assert has_rewrite(pt.th, C), "rewrite_goal_with_prev"

        cv = then_conv(top_sweep_conv(rewr_conv(pt)),
                       beta_norm_conv())
        eq_th = cv.eval(C)
        new_goal = eq_th.prop.rhs

        prevs = list(prevs)
        if not new_goal.is_reflexive():
            prevs.append(ProofTerm.sorry(Thm(goal.hyps, new_goal)))
        return ProofTermDeriv('rewrite_goal_with_prev', args=C, prevs=prevs)

class apply_prev(Tactic):
    """Applies an existing fact in the backward direction."""
    def get_proof_term(self, goal, *, args=None, prevs=None):
        assert isinstance(prevs, list) and len(prevs) >= 1, "apply_prev"
        pt, prev_pts = prevs[0], prevs[1:]

        # First, obtain the patterns
        new_names = logic.get_forall_names(pt.prop)
        new_vars, As, C = logic.strip_all_implies(pt.prop, new_names)
        assert len(prev_pts) <= len(As), "apply_prev: too many prev_pts"

        inst = Inst()
        matcher.first_order_match_incr(C, goal.prop, inst)
        for idx, prev_pt in enumerate(prev_pts):
            matcher.first_order_match_incr(As[idx], prev_pt.prop, inst)

        unmatched_vars = [v for v in new_names if v not in inst]
        if unmatched_vars:
            raise theory.ParameterQueryException(list("param_" + name for name in unmatched_vars))

        pt = pt.subst_type(inst.tyinst)
        for new_name in new_names:
            pt = pt.forall_elim(inst[new_name])
        if pt.prop.beta_norm() != pt.prop:
            pt = beta_norm_conv().apply_to_pt(pt)
        inst_As, inst_C = pt.prop.strip_implies()

        inst_arg = [inst[new_name] for new_name in new_names]
        new_goals = [ProofTerm.sorry(Thm(goal.hyps, A)) for A in inst_As[len(prev_pts):]]
        if set(new_names).issubset({v.name for v in term.get_vars(As)}) and \
           matcher.is_pattern_list(As, []):
            return ProofTermDeriv('apply_fact', args=None, prevs=prevs + new_goals)
        else:
            return ProofTermDeriv('apply_fact_for', args=inst_arg, prevs=prevs + new_goals)

class cases(Tactic):
    """Case checking on an expression."""
    def get_proof_term(self, goal, *, args=None, prevs=None):
        assert isinstance(args, Term), "cases"

        As = goal.hyps
        C = goal.prop
        goal1 = ProofTerm.sorry(Thm(goal.hyps, Implies(args, C)))
        goal2 = ProofTerm.sorry(Thm(goal.hyps, Implies(Not(args), C)))
        return apply_theorem('classical_cases', goal1, goal2)

class inst_exists_goal(Tactic):
    """Instantiate an exists goal."""
    def get_proof_term(self, goal, *, args=None, prevs=None):
        assert isinstance(args, Term), "inst_exists_goal"

        C = goal.prop
        assert C.is_exists(), "inst_exists_goal: goal is not exists statement"
        argT = args.get_type()
        assert C.arg.var_T == argT, "inst_exists_goal: incorrect type: expect %s, given %s" % (
            str(C.arg.var_T), str(argT)
        )

        return rule().get_proof_term(goal, args=('exI', Inst(P=C.arg, a=args)))
