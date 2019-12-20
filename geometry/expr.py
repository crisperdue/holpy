"""Expressions in geometry prover."""

import itertools, copy
from typing import Tuple, Sequence, Optional, List, Dict

POINT, LINE, PonL, SEG, TRI, CIRC, CYCL = range(7)


class Fact:
    """Represent a fact in geometry prover, e.g.:

    coll(A, C, B) is Fact("coll", ["A", "C", "B"]).

    updated: Whether this fact is generated by prover or not.
    lemma: An integer that record which rule is it required to obtain this fact (its place in ruleset).
            None represents no requirement.
    cond: A list of integers that record what facts (their place in fact list) are required to obtain this fact.
            Use "default" when initializing.
            number -1 represents no requirement.
    """

    def __init__(self, pred_name: str, args: Sequence[str], *, updated=False, lemma=None, cond=None):
        self.pred_name = pred_name
        self.args = args
        self.updated = updated
        self.lemma = lemma
        if cond is None:
            cond = []
        self.cond = cond

        # Whether a fact is shadowed by another
        self.shadowed = False

        # For facts combined from other facts, mapping from indices in self
        # to indices to the left / right condition.
        self.left_map = None
        self.right_map = None

    def __hash__(self):
        return hash(("Fact", self.pred_name, tuple(self.args)))

    def __eq__(self, other):
        if isinstance(other, Fact) and self.pred_name == other.pred_name:
            if self.pred_name == 'circle':
                return self.args[0] == other.args[0] and set(self.args[1:]) == set(other.args[1:])
            elif self.pred_name in ('coll', 'cyclic'):
                return set(self.args) == set(other.args)
            else:
                return self.args == other.args

    def __str__(self):
        if self.pred_name == 'eqangle' and self.args[0].isupper():
            return " = ".join("∠[%s%s,%s%s]" % tuple(self.args[4*i:4*i+4]) for i in range(len(self.args) // 4))
        elif self.pred_name == 'contri':
            return " ≌ ".join("△%s%s%s" % tuple(self.args[3*i:3*i+3]) for i in range(len(self.args) // 3))
        else:
            return "%s(%s)" % (self.pred_name, ",".join(self.args))

    def __repr__(self):
        return str(self)

    def get_subfact(self, indices):
        if self.lemma != 'combine':
            return self
        # return self

        if all(i in self.left_map for i in indices):
            new_indices = list(self.left_map[i] for i in indices)
            return self.cond[0].get_subfact(new_indices)
        elif all(i in self.right_map for i in indices):
            new_indices = list(self.right_map[i] for i in indices)
            return self.cond[1].get_subfact(new_indices)
        else:
            return self

    def get_arg_type(self):
        """Obtain the type of arguments for the given fact.

        This is determined by the pred_name of the fact, as well as
        upper/lower case of the arguments.

        Return the argument type.

        """
        pred_name = self.pred_name

        if pred_name in ("para", "perp", "eqangle"):
            if self.args[0].isupper():
                return PonL
            else:
                return LINE
        elif pred_name in ("coll", "midp"):
            return POINT
        elif pred_name in ("eqratio", "cong"):
            return SEG
        elif pred_name == "cyclic":
            return CYCL
        elif pred_name == "circle":
            return CIRC
        elif pred_name in ("simtri", "contri"):
            return TRI
        else:
            raise NotImplementedError


class Line:
    """Represent a line contains more than one point."""
    def __init__(self, args: Sequence[str]):
        assert len(args) > 1
        self.args = set(args)

    def __hash__(self):
        return hash(("line", tuple(sorted(self.args))))

    def __eq__(self, other):
        return isinstance(other, Line) and self.args == other.args

    def __str__(self):
        return "Line(%s)" % (",".join(self.args))

    def __repr__(self):
        return str(self)

    def is_same_line(self, other):
        # Two lines are same if they have at least 2 identical points.
        return isinstance(other, Line) and len(self.args.intersection(other.args)) >= 2

    def combine(self, other):
        # If the other line refers to the same line of this line,
        # add the points of other line that are not in this line.
        assert self.is_same_line(other), "combine line"
        if self.args != other.args:
            self.args = self.args.union(other.args)


class Circle:
    """Represent a circle."""
    def __init__(self, args: Sequence[str], center=None):
        self.args = set(args)
        self.center = center

    def __hash__(self):
        return hash(("circle", self.center, tuple(sorted(self.args))))

    def __eq__(self, other):
        if self.center and other.center and self.center != other.center:
            return False
        return isinstance(other, Circle) and self.args == other.args

    def __str__(self):
        return "Circle(%s,%s)" % (self.center, ",".join(self.args))

    def __repr__(self):
        return str(self)

    def is_same_circle(self, other):
        """Two circles are the same if they have 3 or more identical points.
        If both circles have center and they have 3 or more identical points
        then two centers must be the same.
        """
        if isinstance(other, Circle) and len(self.args.intersection(other.args)) >= 3:
            if self.center and other.center:
                return self.center == other.center
            else:
                return True
        else:
            return False

    def combine(self, other):
        # If the other circle refers to the same as this circle,
        # add the points of other circle that are not in this circle.
        assert self.is_same_circle(other), "combine circle"
        if self.args != other.args:
            self.args = self.args.union(other.args)
        if other.center and not self.center:
            self.center = other.center


class Rule:
    """Represent a rule in geometry prover, e.g.:

    coll(A, C, B) :- coll(A, B, C) is
    Rule([coll(A, B, C)], coll(A, C, B))

    """
    def __init__(self, assums: Sequence[Fact], concl: Fact):
        self.assums = assums
        self.concl = concl

    def __eq__(self, other):
        return isinstance(other, Rule) and self.assums == other.assums and self.concl == other.concl

    def __str__(self):
        return "%s :- %s" % (str(self.concl), ", ".join(str(assum) for assum in self.assums))


def make_pairs(args, pair_len=2):
    """Divide input list args into groups of length pair_len (default 2)."""
    assert len(args) % pair_len == 0
    return [tuple(args[pair_len*i : pair_len*(i+1)]) for i in range(len(args) // pair_len)]


class Prover:
    def __init__(self, ruleset:Dict, hyps:Optional[List[Fact]]=None, concl:Fact=None, lines=None, circles=None):
        self.ruleset = ruleset
        if hyps is None:
            hyps = []
        self.hyps = hyps
        self.concl = concl
        if lines is None:
            lines = []
        self.lines = lines
        if circles is None:
            circles = []
        self.circles = circles

    def equal_pair(self, p1, p2) -> bool:
        return p1 == p2 or p1 == (p2[1], p2[0])

    def equal_line(self, p1, p2) -> bool:
        return self.get_line(p1) == self.get_line(p2)

    def equal_angle(self, a1, a2) -> bool:
        p1, p2 = a1[0:2], a1[2:4]
        q1, q2 = a2[0:2], a2[2:4]
        return self.get_line(p1) == self.get_line(q1) and self.get_line(p2) == self.get_line(q2)

    def equal_triangle(self, t1, t2) -> bool:
        return set(t1) == set(t2)


    def get_line(self, pair: Tuple[str]) -> Line:
        """Return a line from lines containing the given pair of points, if
        it exists. Otherwise return a line containing the pair.
        
        Examples:

        get_line([Line(P,Q,R)], (P, Q)) -> Line(P,Q,R)
        get_line([Line(P,Q,R)], (O, P)) -> Line(O,P)

        """
        assert len(pair) == 2

        new_line = Line(list(pair))
        for line in self.lines:
            if line.is_same_line(new_line):
                return line

        return new_line

    def get_circle(self, points: Sequence[str], center:Optional[str]=None) -> Circle:
        """Return a circle from circles containing the given points and center (optional),
        if it exists. Otherwise return a circle containing the points and center (optional).

        """
        new_circle = Circle(points, center=center)
        for circle in self.circles:
            if new_circle.is_same_circle(circle):
                return circle

        return new_circle

    def match_expr(self, pat: Fact, f: Fact, inst) -> List[Tuple[Dict, Fact]]:
        """Match pattern with f, return a list of result(s).

        inst is a dictionary that assigns point variables to points,
        and line variables to pairs of points.

        lines: list of currently known lines.

        Multiple results will be generated if a line and two points on it
        need to be matched simultaneously.

        Example:

        match(coll(A, B, C), coll(P, Q, R), {}) -> [{A: P, B: Q, C: R}].
        match(coll(A, B, C), coll(P, Q, R), {A: P}) -> [{A: P, B: Q, C: R}].
        match(coll(A, B, C), coll(P, Q, R), {A: Q}) -> [].
        match(coll(A, B, C), para(P, Q, R, S), {}) -> [].

        match(perp(l, m), perp(P, Q, R, S), {}) -> [{l: (P, Q), m: (R, S)}]
        match(perp(l, m), perp(P, Q, R, S), {l: (Q, P)}) -> [{l: (Q, P), m: (R, S)}]
        match(perp(l, m), perp(P, Q, R, S), {l: (O, P)}, lines=[Line(O, P, Q)]) -> [{l: (O, P), m: (R, S)}]
        match(perp(l, m), perp(P, Q, R, S), {l: (O, P)}) -> [].

        """

        def match_PonL(cs):
            t_insts = [inst]
            i = 0
            while i < len(pat.args) // 2:
                ts = []
                for t_inst in t_insts:
                    l = self.get_line(cs[i])
                    pat_a, pat_b = pat.args[i * 2: i * 2 + 2]
                    if pat_a in t_inst:
                        if t_inst[pat_a] in l.args:
                            a = [t_inst[pat_a]]
                        else:
                            a = []
                    else:
                        a = list(l.args)
                    if pat_b in t_inst:
                        if t_inst[pat_b] in l.args:
                            b = [t_inst[pat_b]]
                        else:
                            b = []
                    else:
                        b = list(l.args)
                    perms = [[x, y] for x in a for y in b if x != y]
                    for a, b in perms:
                        t = copy.copy(t_inst)  # t is one result
                        t[pat_a], t[pat_b] = a, b
                        ts.append(t)
                i += 1
                t_insts = ts
            return t_insts

        def match_c(pat_args, f_args, c_args, flag):
            """Identical part of the processing for circ and cycl cases.
            
            flag -- whether the matching has already failed.

            """
            fixed = []  # arguments in pattern that are also in inst.
            same_args = list(set(pat_args).intersection(set(inst.keys())))
            for same_arg in same_args:
                if inst[same_arg] in c_args:
                    fixed.append(same_arg)
                else:
                    flag = True
            if not flag:  # start matching
                for_comb = sorted(list(c_args - set(inst.values())))
                if len(f_args) - len(fixed) > 0:
                    # Order is not considered.
                    comb = itertools.permutations(range(len(for_comb)), len(f_args) - len(fixed))
                    for c_nums in comb:
                        item = [for_comb[num] for num in c_nums]
                        p = 0
                        for i in range(len(pat_args)):
                            if pat_args[i] in fixed:
                                continue
                            inst[pat_args[i]] = item[p]
                            p += 1
                        new_insts.append((copy.copy(inst), f))
                else:  # remain previous insts and sources
                    new_insts.append((inst, f))

        if pat.pred_name != f.pred_name:
            return []

        arg_ty = pat.get_arg_type()
        new_insts = []

        if arg_ty == POINT:
            # coll or midp case
            # Generating all possible combinations from long fact:
            comb = itertools.combinations(range(len(f.args)), len(pat.args))
            for c_nums in comb:
                c = [f.args[num] for num in c_nums]
                t_inst = copy.copy(inst)
                flag = False
                for p_arg, t_arg in zip(pat.args, c):
                    if p_arg in t_inst:
                        if t_arg != t_inst[p_arg]:
                            flag = True
                    else:
                        t_inst[p_arg] = t_arg
                if not flag:
                    new_insts.append((t_inst, f.get_subfact(c_nums)))

        elif arg_ty == LINE:
            # para, perp, or eqangle case, matching lines
            if f.pred_name == "eqangle":
                groups = make_pairs(f.args, pair_len=4)
                comb = itertools.combinations(range(len(groups)), len(pat.args) // 2)  # all possibilities
            else:
                groups = make_pairs(f.args)
                comb = itertools.permutations(range(len(groups)), len(pat.args))

            for c_nums in comb:
                if f.pred_name == "eqangle":
                    cs = [groups[c_nums[0]][0:2], groups[c_nums[0]][2:4], groups[c_nums[1]][0:2], groups[c_nums[1]][2:4]]
                else:
                    cs = [groups[num] for num in c_nums]
                t_inst = copy.copy(inst)
                flag = False
                for p_arg, t_args in zip(pat.args, cs):
                    if p_arg in t_inst:
                        l1 = self.get_line(t_inst[p_arg])
                        l2 = self.get_line(t_args)
                        if l1 != l2:
                            flag = True
                    else:
                        t_inst[p_arg] = t_args
                if not flag:
                        new_insts.append((t_inst, f.get_subfact(c_nums)))



        elif arg_ty == SEG:
            # eqratio or cong case
            # Possible to assign t_inst[pat] to arg
            def can_assign(pat, arg):
                return pat not in t_inst or t_inst[pat] == arg

            new_insts = []
            groups = make_pairs(f.args)
            comb = itertools.combinations(range(len(groups)), len(pat.args) // 2)
            for c_nums in comb:
                c = [groups[num] for num in c_nums]
                t_insts = [inst]
                for i in range(len(pat.args) // 2):
                    ts = []
                    for t_inst in t_insts:
                        pat_a, pat_b = pat.args[2*i: 2*i+2]
                        if can_assign(pat_a, c[i][0]) and can_assign(pat_b, c[i][1]):
                            t = copy.copy(t_inst)
                            t[pat_a] = c[i][0]
                            t[pat_b] = c[i][1]
                            ts.append(t)
                        if can_assign(pat_a, c[i][1]) and can_assign(pat_b, c[i][0]):
                            t = copy.copy(t_inst)
                            t[pat_a] = c[i][1]
                            t[pat_b] = c[i][0]
                            ts.append(t)
                    t_insts = ts
                if t_insts:
                    subfact = f.get_subfact(c_nums)
                for t_inst in t_insts:
                    new_insts.append((t_inst, subfact))

        elif arg_ty == TRI:
            # contri case
            #
            groups = make_pairs(f.args, pair_len=3)
            comb = itertools.combinations(range(len(groups)), len(pat.args) // 3)
            # indices: assign which char in the group to assign to pattern.
            # E.g.
            # indices:  0,  2,  1
            # pat.args: A,  B,  C
            #           ↓    ↙ ↘ 　
            # group:    E,  F,  G
            # matched:  {A: E, B: F, C: G}
            #
            indices_list = [[0, 1, 2], [0, 2, 1], [1, 2, 0]]
            new_insts = []
            for c_nums in comb:
                cs = [groups[num] for num in c_nums]
                for indices in indices_list:
                    flag = False
                    t_inst = copy.copy(inst)
                    for i in range(len(cs)):
                        for j in range(3):
                            if pat.args[i * 3 + j] in t_inst:
                                if cs[i][indices[j]] != t_inst[pat.args[i * 3 + j]]:
                                    flag = True
                            else:
                                t_inst[pat.args[i * 3 + j]] = cs[i][indices[j]]
                    if not flag:
                        new_insts.append((t_inst, f.get_subfact(c_nums)))

        elif arg_ty == PonL:
            # para, perp, or eqangle, matching points
            # Generate possible lines selections (two lines in one selection).
            if f.pred_name == "eqangle":
                groups = make_pairs(f.args, pair_len=4)
                comb = itertools.combinations(range(len(groups)), len(pat.args) // 4)
            else:
                groups = make_pairs(f.args)
                comb = itertools.combinations(range(len(groups)), len(pat.args) // 2)

            for c_nums in comb:
                if f.pred_name == "eqangle":
                    cs = [groups[c_nums[0]][0:2], groups[c_nums[0]][2:4], groups[c_nums[1]][0:2], groups[c_nums[1]][2:4]]
                else:
                    cs = [groups[num] for num in c_nums]

                t_insts = match_PonL(cs)

                if t_insts:
                    subfact = f.get_subfact(c_nums)
                for t_inst in t_insts:
                    new_insts.append((t_inst, subfact))

        elif arg_ty == CYCL:
            circle = self.get_circle(list(f.args))
            flag = False
            match_c(pat.args, f.args, circle.args, flag)

        elif arg_ty == CIRC:
            circle = self.get_circle(f.args[1:], f.args[0])
            flag = False
            if pat.args[0] in inst and inst[pat.args[0]] != f.args[0]:
                flag = True
            else:
                inst[pat.args[0]] = f.args[0]
            match_c(pat.args[1:], f.args[1:], circle.args, flag)

        # TODO: Support more types.
        else:
            raise NotImplementedError

        return new_insts

    def apply_rule(self, rule_name:str, facts:Sequence[Fact]) -> None:
        """Apply given rule to the list of facts.

        If param facts is a list of integers: these integers represents the positions in hyps. In this case,
        hyps must be a list of facts. The new facts generated by this function will combine to hyps
        automatically. Function returns nothing.

        If param facts is a list of facts: New facts will be returned.

        Example:
        apply_rule(
            Rule([para(A, B, C, D), para(C, D, E, F)], para(A, B, E, F)),
                [para(P, Q, R, S), para(R, S, U, V)])
        -> para(P, Q, U, V).

        apply_rule(
            Rule([coll(A, B, C)], coll(A, C, B)),
                [para(A, B, D, C)])
        -> [].
        """
        rule = self.ruleset[rule_name]
        assert len(facts) == len(rule.assums)

        # TODO: flip
        # When trying to obtain contri or simtri from eqangles,
        # There exists the scenario that we need to "flip" one triangle to make its shape as same as
        # another triangle. But the full-angle of the triangle will be changed when "flipping".
        # (The conventional angle will not be changed after "flipping")
        # E.g.
        # Original: eqangle(A, B, C, D, E, F, G, H)
        # Flipped:  eqangle(C, D, A, B, E, F, G, H)

        # instantiation and list of subfacts used
        insts = [(dict(), [])]  # type: List[Tuple[Dict, List[Fact]]]
        for assum, fact in zip(rule.assums, facts):  # match the arguments recursively
            new_insts = []
            # flip = fact.pred_name == 'eqangle' and rule.concl.pred_name in ('simtri', 'contri')
            for inst, subfacts in insts:
                news = self.match_expr(assum, fact, inst)
                for i, subfact in news:
                    new_insts.append((i, subfacts + [subfact]))
            insts = new_insts

        # Rule D40 requires more points in conclusion than in assumption. Add points from lines as supplement.
        if rule_name in ("D40") and insts:
            prev_insts = copy.copy(insts)
            insts = []
            if any(i not in prev_insts[0][0].keys() for i in rule.concl.args):
                for inst, subfacts in prev_insts:
                    not_match = set(rule.concl.args) - set(inst.keys())
                    for line in self.lines:
                        extended_t_inst = copy.copy(inst)
                        for i, ch in enumerate(not_match):
                            extended_t_inst[ch] = (list(line.args)[i], list(line.args)[i+1])
                        insts.append((extended_t_inst, subfacts))

        for inst, subfacts in insts:  # An inst represents one matching result of match_expr
            if rule.concl.args[0].islower():
                concl_args = []  # type: List[str]

                for i in rule.concl.args:
                    concl_args.extend((inst[i][0], inst[i][1]))
            else:
                concl_args = [inst[i] for i in rule.concl.args]
            fact = Fact(rule.concl.pred_name, concl_args, updated=True, lemma=rule_name, cond=subfacts)
            # print(fact, fact.cond)

            # Check if fact is trivial
            if self.check_trivial(fact):
                continue

            # Check if fact is redundant
            exists = False
            for hyp in self.hyps:
                if not hyp.shadowed and self.check_imply(hyp, fact):
                    exists = True
            if exists:
                continue

            new_facts = [fact]
            for target in self.hyps:
                if not target.shadowed and self.check_imply(fact, target):
                    target.shadowed = True

                if not target.shadowed:
                    new_fact = self.combine_facts(fact, target)
                    if new_fact:
                        fact.shadowed = True
                        target.shadowed = True
                        fact = new_fact
                        new_facts.append(new_fact)

            # for new_fact in new_facts:
            #     print(new_fact.lemma, new_fact)
            self.hyps.extend(new_facts)

    def compute_lines(self):
        self.lines = []
        for hyp in self.hyps:
            if not hyp.shadowed and hyp.pred_name == 'coll':
                self.lines.append(Line(hyp.args))

    def compute_circles(self):
        self.circles = []
        for hyp in self.hyps:
            if not hyp.shadowed:
                if hyp.pred_name == 'cyclic':
                    self.circles.append(Circle(hyp.args))
                elif hyp.pred_name == 'circle':
                    self.circles.append(Circle(hyp.args[1:], center=hyp.args[0]))

    def search_step(self, only_updated=False) -> None:
        """One step of searching fixpoint.

        Apply given ruleset to a list of hypotheses to obtain new facts.
        If collinear facts are included in hypotheses, new lines can be
        automatically generated, these new lines might be used when
        applying rules to hypotheses.

        """
        self.compute_lines()
        self.compute_circles()

        avail_hyps = [hyp for hyp in self.hyps if not hyp.shadowed]
        for rule_name, rule in self.ruleset.items():
            for facts in itertools.permutations(avail_hyps, len(rule.assums)):
                if any(fact.shadowed for fact in facts):
                    continue
                if only_updated and all(not fact.updated for fact in facts):
                    continue
                self.apply_rule(rule_name, facts)

    def search_fixpoint(self) -> Optional[Fact]:
        """Recursively apply given ruleset to a list of hypotheses to
        obtain new facts. Recursion exits when new fact is not able
        to be generated, or conclusion is in the list of facts.
        Return the list of facts.
        """
        prev_len = len(self.hyps)
        self.search_step()
        steps = 0
        while prev_len != len(self.hyps) and steps < 10:
            steps += 1
            print("Step", steps)
            # print(list(hyp for hyp in hyps if not hyp.shadowed))
            prev_len = len(self.hyps)
            self.search_step(only_updated=True)
            for fact in self.hyps:
                if self.check_imply(fact, self.concl):
                    return fact
        print("Last updated lines:", self.lines)
        print("Last updated hyps: ", self.hyps)
        assert False, "Fixpoint reached without proving goal."
        return None

    def combine_facts(self, fact, goal) -> Optional[Fact]:
        """
        Combine this fact to other fact.
        Return a combined long fact if succeed.

        """
        if fact.pred_name != goal.pred_name:
            return None

        def get_indices(l, l_comb, comp=None):
            res = dict()
            for i, p in enumerate(l):
                found = False
                for j, q in enumerate(l_comb):
                    if (comp is None and p == q) or (comp is not None and comp(p, q)):
                        res[j] = i
                        found = True
                        break
                assert found
            return res

        if fact.pred_name == 'perp':
            # No combination
            return None

        elif fact.pred_name == 'coll':
            l1, l2 = Line(fact.args), Line(goal.args)
            if l1.is_same_line(l2):
                l1.combine(l2)
                f = Fact('coll', list(l1.args), updated=True, lemma='combine', cond=[fact, goal])
                f.left_map = get_indices(l1.args, f.args)
                f.right_map = get_indices(l2.args, f.args)
                return f
            else:
                return None

        elif fact.pred_name == 'circle':
            c1, c2 = Circle(fact.args[1:], center=fact.args[0]), Circle(goal.args[1:], center=fact.args[0])

            if c1.is_same_circle(c2):
                c1.combine(c2)
                f = Fact('circle', [c1.center] + list(c1.args), updated=True, lemma='combine', cond=[fact, goal])
                f.left_map = get_indices(c1.args, f.args)
                f.right_map = get_indices(c2.args, f.args)
                return f
            else:
                return None

        elif fact.pred_name == 'cyclic':
            c1, c2 = Circle(fact.args), Circle(goal.args)

            if c1.is_same_circle(c2):
                c1.combine(c2)
                f = Fact('cyclic', list(c1.args), updated=True, lemma='combine', cond=[fact, goal])
                f.left_map = get_indices(c1.args, f.args)
                f.right_map = get_indices(c2.args, f.args)
                return f
            else:
                return None

        elif fact.pred_name == 'cong':
            # Check if any pair of points in fact and goal are the same
            # (exchange is allowed)
            can_combine = False
            f_pairs = make_pairs(fact.args)
            g_pairs = make_pairs(goal.args)
            if any(self.equal_pair(p1, p2) for p1 in f_pairs for p2 in g_pairs):
                new_args = []  # type: List[str]
                for p1 in f_pairs:
                    new_args.extend(p1)
                for p2 in g_pairs:
                    if not any(self.equal_pair(p1, p2) for p1 in f_pairs):
                        new_args.extend(p2)
                f = Fact('cong', new_args, updated=True, lemma="combine", cond=[fact, goal])
                p_comb = make_pairs(new_args)
                f.left_map = get_indices(f_pairs, p_comb, self.equal_pair)
                f.right_map = get_indices(g_pairs, p_comb, self.equal_pair)
                return f
            else:
                return None

        elif fact.pred_name == 'para':
            # Check if any pair of points in fact and goal denote the same line
            can_combine = False
            f_pairs = make_pairs(fact.args)
            g_pairs = make_pairs(goal.args)
            if any(self.equal_line(p1, p2) for p1 in f_pairs for p2 in g_pairs):
                new_args = []
                for p1 in f_pairs:
                    new_args.extend(p1)
                for p2 in g_pairs:
                    if not any(self.equal_line(p1, p2) for p1 in f_pairs):
                        new_args.extend(p2)
                f = Fact('para', new_args, updated=True, lemma="combine", cond=[fact, goal])
                p_comb = make_pairs(new_args)
                f.left_map = get_indices(f_pairs, p_comb, self.equal_line)
                f.right_map = get_indices(g_pairs, p_comb, self.equal_line)
                return f
            else:
                return None

        elif fact.pred_name == 'eqangle':
            # Check if any 4-tuple of points in fact and goal denote the same angle
            can_combine = False
            f_angles = make_pairs(fact.args, pair_len=4)
            g_angles = make_pairs(goal.args, pair_len=4)
            if any(self.equal_angle(a1, a2) for a1 in f_angles for a2 in g_angles):
                new_args = []
                for a1 in f_angles:
                    new_args.extend(a1)
                for a2 in g_angles:
                    if not any(self.equal_angle(a1, a2) for a1 in f_angles):
                        new_args.extend(a2)
                f = Fact('eqangle', new_args, updated=True, lemma="combine", cond=[fact, goal])
                p_comb = make_pairs(new_args, pair_len=4)
                f.left_map = get_indices(f_angles, p_comb, self.equal_angle)
                f.right_map = get_indices(g_angles, p_comb, self.equal_angle)
                return f
            else:
                return None

        elif fact.pred_name in ('simtri', 'contri'):
            return None

        else:
            raise NotImplementedError

    def check_trivial(self, fact) -> bool:
        """Check whether the given fact is trivial."""
        if fact.pred_name == 'cong':
            pairs = make_pairs(fact.args)
            for p1, p2 in itertools.permutations(pairs, 2):
                if self.equal_pair(p1, p2):
                    return True
            return False

        elif fact.pred_name == 'para':
            pairs = make_pairs(fact.args)
            for p1, p2 in itertools.permutations(pairs, 2):
                if self.equal_line(p1, p2):
                    return True
            return False

        elif fact.pred_name == 'eqangle':
            angles = make_pairs(fact.args, pair_len=4)
            for a1, a2 in itertools.permutations(angles, 2):
                if self.equal_angle(a1, a2):
                    return True
            return False

        return False

    def check_imply(self, fact, goal) -> bool:
        """Check whether the given fact is able to imply the given goal."""
        if fact.pred_name != goal.pred_name:
            return False

        if fact.pred_name == "perp":
            # Check the two lines are the same
            f1, f2 = make_pairs(fact.args)
            g1, g2 = make_pairs(goal.args)
            return self.equal_line(f1, g1) and self.equal_line(f2, g2)

        elif fact.pred_name == 'coll':
            # Whether points in goal is a subset of points in fact
            return set(goal.args).issubset(set(fact.args))

        elif fact.pred_name == 'circle':
            # Whether the centers are the same, and other points in goal
            # is a subset of points in fact
            return fact.args[0] == goal.args[0] and set(goal.args[1:]).issubset(set(fact.args[1:]))

        elif fact.pred_name == 'cyclic':
            # Whether points in goal is a subset of points in fact
            return set(goal.args).issubset(set(fact.args))

        elif fact.pred_name == 'cong':
            # Check whether both segments in goal are in fact.
            f_pairs = make_pairs(fact.args)
            g_pairs = make_pairs(goal.args)
            return all(any(self.equal_pair(f, g) for f in f_pairs) for g in g_pairs)

        elif fact.pred_name == 'para':
            # Check whether both lines in goal are in fact.
            f_pairs = make_pairs(fact.args)
            g_pairs = make_pairs(goal.args)
            return all(any(self.equal_line(f, g) for f in f_pairs) for g in g_pairs)

        elif fact.pred_name == "eqangle":
            # Check whether both angles in goal are in fact.
            f_angles = make_pairs(fact.args, pair_len=4)
            g_angles = make_pairs(goal.args, pair_len=4)
            return all(any(self.equal_angle(f, g) for f in f_angles) for g in g_angles)

        elif fact.pred_name in ("simtri", "contri"):
            # Check whether both triangles in goal are in fact.
            f_tris = make_pairs(fact.args, pair_len=3)
            g_tris = make_pairs(goal.args, pair_len=3)
            return all(any(self.equal_triangle(f, g) for f in f_tris) for g in g_tris)

        else:
            print(fact.pred_name)
            raise NotImplementedError

    def print_search(self, res) -> None:
        """Print the process of searching fixpoint.
        The given list of facts must contains all the deduce procedures
        (as parameters of facts in the list). Using a given ruleset to
        find out the name of rules used in deduce procedures.

        """
        print_list = []  # type: List[Fact]
        def rec(fact):
            if fact in print_list:
                return

            for cond in fact.cond:
                rec(cond)
            print_list.append(fact)

        rec(res)

        for fact in print_list:
            if fact.lemma == 'combine':
                print('combine', fact)
            elif fact.lemma:
                print('(' + str(self.ruleset[fact.lemma]) + ')', fact, ':-', ', '.join(str(cond) for cond in fact.cond))
