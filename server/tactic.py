# Author: Bohua Zhan

import io

from kernel import term
from kernel.term import Term, Var
from kernel.thm import Thm
from kernel.proof import ProofItem, Proof, id_force_tuple
from kernel import report
from logic import logic, matcher
from logic.proofterm import ProofTerm
from logic.conv import top_conv, rewr_conv_thm
from syntax import parser, printer


class TacticException(Exception):
    pass

# Helper functions

def incr_id(id, start, n):
    """Increment the given id by n, with the starting integer index given
    by start.

    """
    if id[0] >= start:
        return (id[0] + n,) + id[1:]
    else:
        return id

def incr_proof_item(item, start, n):
    """Increment all ids in the given proof item."""
    item.id = incr_id(item.id, start, n)
    item.prevs = [incr_id(id, start, n) for id in item.prevs]

def decr_id(id, id_remove):
    """Decrement a single id, with the aim of closing the gap at id_remove."""
    if id[0] > id_remove:
        return (id[0] - 1,) + id[1:]
    else:
        return id

def decr_proof_item(item, id_remove):
    """Decrement all ids in the given proof item."""
    item.id = decr_id(item.id, id_remove)
    item.prevs = [decr_id(id, id_remove) for id in item.prevs]

def strip_all_implies(t, names):
    """Given a term of the form

    !x_1 ... x_k. A_1 --> ... --> A_n --> C.

    Return the triple ([v_1, ..., v_k], [A_1, ... A_n], C), where
    v_1, ..., v_k are new variables with the given names, and
    A_1, ..., A_n, C are the body of the input term, with bound variables
    substituted for v_1, ..., v_k.

    """
    if Term.is_all(t):
        assert len(names) > 0, "strip_all_implies: not enough names input."
        v = Var(names[0], t.arg.var_T)
        vars, As, C = strip_all_implies(t.arg.subst_bound(v), names[1:])
        return ([v] + vars, As, C)
    else:
        assert len(names) == 0, "strip_all_implies: too many names input."
        As, C = t.strip_implies()
        return ([], As, C)


class ProofState():
    """Represents proof state on the server side."""

    def __init__(self, thy):
        """Empty proof state."""
        self.thy = thy
        self.vars = []
        self.prf = Proof()

    def get_ctxt(self):
        ctxt = {}
        for v in self.vars:
            ctxt[v.name] = v.T
        return ctxt

    def __str__(self):
        vars = sorted(self.vars, key = lambda v: v.name)
        lines = "\n".join('var ' + v.name + ' :: ' + str(v.T) for v in vars)
        return lines + "\n" + str(self.prf)

    @staticmethod
    def init_state(thy, vars, assums, concl):
        """Construct initial partial proof for the given assumptions and
        conclusion.

        assums - assumptions A1, ... An.
        concl - conclusion C.
        
        Constructs:

        0: assume A1
        ...
        n-1: assume An
        n: C by sorry
        n+1: An --> C by implies_intr n-1 from n
        ...
        2n: A1 --> ... --> An --> C by implies_intr 0 from 2n-1.

        """
        state = ProofState(thy)

        state.vars = vars
        state.prf = Proof(*assums)
        n = len(assums)
        state.prf.add_item(n, "sorry", th=Thm(assums, concl))
        for i, assum in enumerate(reversed(assums), 0):
            state.prf.add_item(n + i + 1, "implies_intr", args=assum, prevs=[n - i])
        state.check_proof(compute_only=True)
        return state

    @staticmethod
    def parse_init_state(thy, data):
        """Given data for a theorem statement, construct the initial partial proof.
        
        data['vars']: list of variables.
        data['prop']: proposition to be proved. In the form A1 --> ... --> An --> C.

        """
        ctxt = {}
        vars = []
        for name, str_T in data['vars'].items():
            T = parser.parse_type(thy, str_T)
            vars.append(Var(name, T))
            ctxt[name] = T
        prop = parser.parse_term(thy, ctxt, data['prop'])
        assums, concl = prop.strip_implies()

        return ProofState.init_state(thy, vars, assums, concl)

    def json_data(self):
        """Export proof in json format."""
        self.check_proof()
        return {
            "vars": [{'name': v.name, 'T': str(v.T)} for v in self.vars],
            "proof": [printer.export_proof_item(self.thy, item, unicode=True, highlight=True)
                      for item in self.prf.items],
            "report": self.rpt.json_data()
        }

    @staticmethod
    def parse_proof(thy, data):
        """Obtain proof from json format."""
        ctxt = {}
        state = ProofState(thy)
        for name, str_T in data['vars'].items():
            T = parser.parse_type(thy, str_T)
            state.vars.append(Var(name, T))
            ctxt[name] = T
        state.prf = Proof()
        for line in data['proof']:
            state.prf.items.append(parser.parse_proof_rule_from_data(thy, ctxt, line))

        state.check_proof(compute_only=True)
        return state

    def check_proof(self, *, no_gaps=False, compute_only=False):
        """Check the given proof. Report is stored in rpt."""
        self.rpt = report.ProofReport()
        return self.thy.check_proof(self.prf, rpt=self.rpt, no_gaps=no_gaps, compute_only=compute_only)

    def add_line_after(self, id):
        """Add given line after the given id."""
        id = id_force_tuple(id)
        start = id[0] + 1
        new_id = (id[0] + 1,) + id[1:]
        self.prf.items = self.prf.items[:id[0]+1] + [ProofItem(new_id, "")] + self.prf.items[id[0]+1:]
        for item in self.prf.items[id[0]+2:]:
            incr_proof_item(item, start, 1)

        self.check_proof(compute_only=True)

    def add_line_before(self, id, n):
        """Add n lines before the given id."""
        id = id_force_tuple(id)
        start = id[0]
        new_items = [ProofItem((id[0] + i,) + id[1:], "") for i in range(n)]
        self.prf.items = self.prf.items[:id[0]] + new_items + self.prf.items[id[0]:]
        for item in self.prf.items[id[0]+n:]:
            incr_proof_item(item, start, n)

        self.check_proof(compute_only=True)

    def remove_line(self, id):
        """Remove line with the given id."""
        id = id_force_tuple(id)
        to_remove = id[0]
        self.prf.items = self.prf.items[:id[0]] + self.prf.items[id[0]+1:]
        for item in self.prf.items[id[0]:]:
            decr_proof_item(item, to_remove)

        self.check_proof(compute_only=True)

    def set_line(self, id, rule, *, args=None, prevs=None, th=None):
        """Set the item with the given id to the following data."""
        id = id_force_tuple(id)
        self.prf.items[id[0]] = ProofItem(id, rule, args=args, prevs=prevs, th=th)
        self.check_proof(compute_only=True)

    def get_proof_item(self, id):
        """Obtain the proof item with the given id."""
        return self.prf.items[id[0]]

    def replace_id(self, old_id, new_id):
        """Replace old_id with new_id in prevs."""
        for item in self.prf.items:
            item.prevs = [new_id if id == old_id else id for id in item.prevs]

        self.remove_line(old_id)

    def find_goal(self, concl, upto_id):
        """Determine if the given conclusion is already proved. Search up to
        the given id.

        """
        for item in self.prf.items:
            if item.id == upto_id:
                return None
            if item.th is not None and item.th.can_prove(concl):
                return item.id

        # upto_id not found
        raise TacticException()

    def apply_backward_step_thms(self, id, prevs=None):
        """Return the list of theorems that can be used for applying
        backward step.

        This is done by first matching each of the prevs against the
        assumptions in order, then match the conclusion.

        """
        id = id_force_tuple(id)
        prevs = [id_force_tuple(prev) for prev in prevs] if prevs else []
        prevs = [self.get_proof_item(id) for id in prevs]

        # Obtain the statement to be proved.
        cur_item = self.get_proof_item(id)
        if cur_item.rule != "sorry":
            return []

        results = []
        for name, th in self.thy.get_data("theorems").items():
            inst = dict()
            As, C = th.concl.strip_implies()
            # Only process those theorems where C and the matched As
            # contain all of the variables.
            if set(term.get_vars(As[:len(prevs)] + [C])) != set(term.get_vars(As + [C])):
                continue

            # When there is no assumptions to match, only process those
            # theorems where C contains at least a constant (skip falseE,
            # induction theorems, etc).
            if not prevs and term.get_consts(C) == []:
                continue

            try:
                for pat, prev in zip(As, prevs):
                    matcher.first_order_match_incr(pat, prev.th.concl, inst)
                matcher.first_order_match_incr(C, cur_item.th.concl, inst)
            except matcher.MatchException:
                continue

            # All matches succeed
            results.append((name, th))
        return sorted(results)

    def apply_backward_step(self, id, th_name, *, prevs=None, inst=None):
        """Apply backward step using the given theorem.
        
        prevs - list of previous proved facts to use.
        inst - existing instantiation.

        """
        id = id_force_tuple(id)
        prevs = [id_force_tuple(prev) for prev in prevs] if prevs else []

        # Obtain the statement to be proved.
        cur_item = self.get_proof_item(id)
        assert cur_item.rule == "sorry", "apply_backward_step: id is not a gap"

        # Instantiate the given theorem.
        th = self.thy.get_theorem(th_name)

        if inst is None:
            inst = dict()
            As, C = logic.subst_norm(th.concl, inst).strip_implies()
            for pat, prev in zip(As, prevs):
                item = self.get_proof_item(prev)
                matcher.first_order_match_incr(pat, item.th.concl, inst)
            matcher.first_order_match_incr(C, cur_item.th.concl, inst)

        As, _ = logic.subst_norm(th.concl, inst).strip_implies()

        num_goal = len(As) - len(prevs)
        self.add_line_before(id, num_goal)
        start = id
        all_ids = [incr_id(start, 0, i - len(prevs)) for i in range(len(prevs), len(As))]
        for goal_id, A in zip(all_ids, As[len(prevs):]):
            self.set_line(goal_id, "sorry", th=Thm(cur_item.th.assums, A))

        self.set_line(incr_id(start, 0, num_goal), "apply_theorem_for",
                      args=(th_name, inst), prevs=prevs + all_ids, th=cur_item.th)

        # Test if the goals are already proved:
        for goal_id, A in reversed(list(zip(all_ids, As[len(prevs):]))):
            goal = Thm(cur_item.th.assums, A)
            new_id = self.find_goal(goal, goal_id)
            if new_id is not None:
                self.replace_id(goal_id, new_id)

    def introduction(self, id, names=None):
        """Introduce assumptions for a goal of the form

        !x_1 ... x_k. A_1 --> ... --> A_n --> C.

        Argument names specifies list of variable names.
        
        """
        id = id_force_tuple(id)
        cur_item = self.get_proof_item(id)
        assert cur_item.rule == "sorry", "introduction: id is not a gap"

        if names is None:
            names = []

        vars, As, C = strip_all_implies(cur_item.th.concl, names)

        # Add necessary variables
        for var in vars:
            if var not in self.vars:
                self.vars.append(var)

        # len(As) lines for the assumptions, one line for the sorry,
        # len(vars) lines for forall_intr, len(As) lines for implies_intr,
        # one line already available.
        self.add_line_before(id, len(vars) + 2 * len(As))

        # Starting id number
        start = id

        # Assumptions
        for i, A in enumerate(As):
            new_id = incr_id(start, 0, i)
            self.set_line(new_id, "assume", args=A, th=Thm([A], A))

        # Goal
        goal_id = incr_id(start, 0, len(As))
        goal = Thm(list(cur_item.th.assums) + As, C)
        self.set_line(goal_id, "sorry", th=goal)

        # implies_intr invocations
        for i, A in enumerate(reversed(As)):
            prev_id = incr_id(start, 0, len(As) + i)
            new_id = incr_id(start, 0, len(As) + i + 1)
            self.set_line(new_id, "implies_intr", args=A, prevs=[prev_id])

        # forall_intr invocations
        for i, var in enumerate(reversed(vars)):
            prev_id = incr_id(start, 0, 2 * len(As) + i)
            new_id = incr_id(start, 0, 2 * len(As) + i + 1)
            self.set_line(new_id, "forall_intr", args=var, prevs=[prev_id])

        # Test if the goal is already proved
        new_id = self.find_goal(goal, goal_id)
        if new_id is not None:
            self.replace_id(goal_id, new_id)

    def apply_induction(self, id, th_name, var):
        """Apply induction using the given theorem and on the given
        variable.
        
        """
        id = id_force_tuple(id)
        cur_item = self.get_proof_item(id)
        assert cur_item.rule == "sorry", "apply_induction: id is not a gap"

        # Find variable
        assert isinstance(var, str), "apply_induction: input must be a string"
        for v in self.vars:
            if v.name == var:
                var = v
                break

        assert not isinstance(var, str), "apply_induction: variable not found"

        # Current goal
        concl = cur_item.th.concl

        # Instantiation for P
        P = Term.mk_abs(var, concl)
        inst = {"P": P, "x": var}
        self.apply_backward_step(id, th_name, inst=inst)

    def rewrite_goal_thms(self, id):
        """Find list of theorems on which rewrite_goal can be applied."""

        id = id_force_tuple(id)
        cur_item = self.get_proof_item(id)
        if cur_item.rule != "sorry":
            return []

        results = []
        goal = cur_item.th.concl
        for th_name, th in self.thy.get_data("theorems").items():
            if th.concl.is_equals():
                cv = top_conv(rewr_conv_thm(self.thy, th_name))
                _, new_goal = cv(goal).concl.dest_binop()
                if goal != new_goal:
                    results.append((th_name, new_goal))

        return sorted(results)

    def rewrite_goal(self, id, th_name, *, backward=False):
        """Apply an existing equality theorem to the given goal."""

        id = id_force_tuple(id)
        cur_item = self.get_proof_item(id)
        assert cur_item.rule == "sorry", "rewrite_goal: id is not a gap"

        goal = cur_item.th.concl
        cv = top_conv(rewr_conv_thm(self.thy, th_name))
        _, new_goal = cv(goal).concl.dest_binop()

        self.add_line_before(id, 1)
        self.set_line(id, "sorry", th=Thm(cur_item.th.assums, new_goal))
        self.set_line(incr_id(id, 0, 1), "rewrite_goal", args=(th_name, goal), prevs=[id])

        # Test if the goal is already proved
        new_id = self.find_goal(Thm(cur_item.th.assums, new_goal), id)
        if new_id is not None:
            self.replace_id(id, new_id)
