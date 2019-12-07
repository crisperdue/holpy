"""Expressions in geometry prover."""

import itertools, copy

POINT, LINE, PonL, SEG, TRI, CIRC, CYCL = range(7)


def get_arg_type_by_fact(fact):
    """Obtain the type of arguments for the given fact.

    This is determined by the pred_name of the fact, as well as
    upper/lower case of the arguments.

    Return the argument type.

    """
    pred_name = fact.pred_name

    if pred_name in ("para", "perp", "eqangle"):
        if fact.args[0].isupper():
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
    elif pred_name == "simtri":
        return TRI
    else:
        raise NotImplementedError


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

    def __init__(self, pred_name, args, *, updated=False, lemma=None, cond=None):
        assert isinstance(pred_name, str)
        assert isinstance(args, list) and all(isinstance(arg, str) for arg in args)
        self.pred_name = pred_name
        self.args = args
        self.updated = updated
        self.lemma = lemma
        if cond is None:
            cond = []
        self.cond = cond

        # Changed during proof
        self.combined = False

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
        else:
            return "%s(%s)" % (self.pred_name, ",".join(self.args))

    def __repr__(self):
        return str(self)


class Line:
    """Represent a line contains more than one point."""
    def __init__(self, args, source=None):
        assert isinstance(args, list)
        assert len(args) > 1
        assert all(isinstance(arg, str) for arg in args)
        self.args = set(args)
        self.source = source

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
    def __init__(self, args, center=None, source=None):
        assert isinstance(args, list)
        assert len(args) >= 3
        assert all(isinstance(arg, str) for arg in args)
        self.args = set(args)
        self.source = source
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
    def __init__(self, assums, concl):
        assert isinstance(assums, list) and all(isinstance(assum, Fact) for assum in assums)
        assert isinstance(concl, Fact)
        self.assums = assums
        self.concl = concl

    def __eq__(self, other):
        return isinstance(other, Rule) and self.assums == other.assums and self.concl == other.concl

    def __str__(self):
        return "%s :- %s" % (str(self.concl), ", ".join(str(assum) for assum in self.assums))


class MatchException(Exception):
    pass


def get_line(lines, pair):
    """Return a line from lines containing the given pair of points, if
    it exists. Otherwise return a line containing the pair.
    
    Examples:

    get_line([Line(P,Q,R)], (P, Q)) -> Line(P,Q,R)
    get_line([Line(P,Q,R)], (O, P)) -> Line(O,P)

    """
    assert isinstance(lines, list) and all(isinstance(line, Line) for line in lines)
    assert isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(p, str) for p in pair)

    new_line = Line(list(pair))
    for line in lines:
        if line.is_same_line(new_line):
            return line

    return new_line


def get_circle(circles, points, center=None):
    """Return a circle from circles containing the given points and center (optional),
    if it exists. Otherwise return a circle containing the points and center (optional).

    """
    assert isinstance(circles, list) and all(isinstance(circle, Circle) for circle in circles)
    assert isinstance(points, list) and len(points) >= 3 and all(isinstance(p, str) for p in points)
    if center:
        assert isinstance(center, str)

    new_circle = Circle(points, center=center)
    for circle in circles:
        if new_circle.is_same_circle(circle):
            return circle

    return new_circle


def make_pairs(args, pair_len=2):
    """Divide input list args into groups of length pair_len (default 2)."""
    assert len(args) % pair_len == 0
    return [tuple(args[pair_len*i : pair_len*(i+1)]) for i in range(len(args) // pair_len)]


def match_expr(pat, f, inst, *, lines=None, circles=None):
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

    def c_process(flag):
        """Identical part of the processing for circ and cycl cases.
        
        flag -- whether the matching has already failed.

        """
        fixed = []  # arguments in pattern that are also in inst.
        same_args = list(set(pat.args).intersection(set(inst.keys())))
        for same_arg in same_args:
            if inst[same_arg] in c.args:
                fixed.append(same_arg)
            else:
                flag = True
        if not flag:  # start matching
            for_comb = sorted(list(c.args - set(inst.values())))
            if len(f.args) - len(fixed) > 0:
                # Order is not considered.
                comb = list(itertools.permutations(range(len(for_comb)), len(f.args) - len(fixed)))
                for c_nums in comb:
                    item = [for_comb[num] for num in c_nums]
                    p = 0
                    for i in range(len(pat.args)):
                        if pat.args[i] in fixed:
                            continue
                        inst[pat.args[i]] = item[p]
                        p += 1
                    new_insts.append(copy.copy(inst))
            else:  # remain previous insts and sources
                new_insts.append(inst)

    assert isinstance(pat, Fact) and isinstance(f, Fact)
    if lines is None:
        lines = []
    else:
        assert isinstance(lines, list) and all(isinstance(line, Line) for line in lines)

    if pat.pred_name != f.pred_name:
        return []

    arg_ty = get_arg_type_by_fact(pat)
    new_insts = []

    if arg_ty == POINT:
        # coll or midp case
        # Generating all possible combinations from long fact:
        comb = list(itertools.combinations(range(len(f.args)), len(pat.args)))
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
                new_insts.append(t_inst)

    elif arg_ty == LINE:
        # para, perp, or eqangle case, matching lines
        if f.pred_name == "eqangle":
            groups = make_pairs(f.args, pair_len=4)
            comb = list(itertools.combinations(range(len(groups)), 2))  # all possibilities
        else:
            groups = make_pairs(f.args)
            comb = list(itertools.permutations(range(len(groups)), len(pat.args)))

        for c_nums in comb:
            if f.pred_name == "eqangle":
                c = ((groups[c_nums[0]][0], groups[c_nums[0]][1]), (groups[c_nums[0]][2], groups[c_nums[0]][3]),
                     (groups[c_nums[1]][0], groups[c_nums[1]][1]), (groups[c_nums[1]][2], groups[c_nums[1]][3]))
            else:
                c = [groups[num] for num in c_nums]
            t_inst = copy.copy(inst)
            flag = False
            for p_arg, t_arg in zip(pat.args, c):
                if p_arg in t_inst:
                    l1 = get_line(lines, t_inst[p_arg])
                    l2 = get_line(lines, t_arg)
                    if l1 != l2:
                        flag = True
                else:
                    t_inst[p_arg] = t_arg
            if not flag:
                new_insts.append(t_inst)

    elif arg_ty == SEG:
        # eqratio or cong case
        # Possible to assign t_inst[pat] to arg
        def can_assign(pat, arg):
            return pat not in t_inst or t_inst[pat] == arg

        new_insts = []
        groups = make_pairs(f.args)
        comb = list(itertools.combinations(range(len(groups)), len(pat.args) // 2))
        for c_nums in comb:
            c = [groups[num] for num in c_nums]
            t_insts = [copy.copy(inst)]
            for i in range(len(pat.args) // 2):
                ts = []
                for t_inst in t_insts:
                    pat_a, pat_b = pat.args[2*i : 2*i+2]
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
            new_insts.extend(t_insts)

    elif arg_ty == PonL:
        # para, perp, or eqangle, matching points
        # Generate possible lines selections (two lines in one selection).
        if f.pred_name == "eqangle":
            groups = make_pairs(f.args, pair_len=4)
            comb = list(itertools.combinations(range(len(groups)), len(pat.args) // 4))
        else:
            groups = make_pairs(f.args)
            comb = list(itertools.combinations(range(len(groups)), len(pat.args) // 2))
        base_inst = copy.copy(inst)

        for c_nums in comb:
            if f.pred_name == "eqangle":
                c = ((groups[c_nums[0]][0], groups[c_nums[0]][1]), (groups[c_nums[0]][2], groups[c_nums[0]][3]),
                     (groups[c_nums[1]][0], groups[c_nums[1]][1]), (groups[c_nums[1]][2], groups[c_nums[1]][3]))
            else:
                c = [groups[num] for num in c_nums]
            t_insts = [copy.copy(inst)]
            for i in range(len(pat.args) // 2):
                ts = []
                for t_inst in t_insts:
                    l = get_line(lines, c[i])
                    removed = copy.copy(l.args)
                    removed = removed - set(t_inst.values())
                    pat_a, pat_b = pat.args[i*2 : i*2+2]

                    if pat_a in t_inst:
                        if t_inst[pat_a] in l.args:
                            a = [t_inst[pat_a]]
                        else:
                            a = []
                    else:
                        a = removed

                    if pat_b in t_inst:
                        if t_inst[pat_b] in l.args:
                            b = [t_inst[pat_b]]
                        else:
                            b = []
                    else:
                        b = removed

                    perms = [[x, y] for x in a for y in b if x != y]
                    for a, b in perms:
                        t = copy.copy(t_inst)
                        t[pat_a], t[pat_b] = a, b
                        ts.append(t)
                t_insts = ts
            new_insts.extend(t_insts)  # t_insts is a empty list if nothing new generated

    elif arg_ty == CYCL:
        c = get_circle(circles, list(f.args))
        flag = False
        c_process(flag)

    elif arg_ty == CIRC:
        c = get_circle(circles, f.args[1:], f.args[0])
        flag = False
        if pat.args[0] in inst and inst[pat.args[0]] != f.args[0]:
            flag = True
        else:
            inst[pat.args[0]] = f.args[0]
        del f.args[0]
        del pat.args[0]
        c_process(flag)

    # TODO: Support more types.
    elif arg_ty == TRI:
        raise NotImplementedError

    else:
        raise NotImplementedError

    return new_insts


def make_new_lines(facts, lines):
    """Construct new lines from a list of given facts.

    The arguments of collinear facts will be used to construct new lines.
    Points in a new line will be merged into one of given lines,
    if the new line and the given line is the same line.
    The given list of lines will be updated.

    """
    assert isinstance(facts, list)
    assert all(isinstance(fact, Fact) for fact in facts)
    assert isinstance(lines, list)
    assert all(isinstance(line, Line) for line in lines)

    for fact in facts:
        if fact.pred_name == "coll":
            new_line = Line(fact.args)
            same = [l for l in lines if new_line.is_same_line(l)]
            for l in same:
                new_line.combine(l)
                lines.remove(l)
            lines.append(new_line)


def make_new_circles(facts, circles):
    """
    Construct new circles from a list of given facts.
    The arguments of cyclic and circle facts will be used to construct new circles.
    Points in a new line will be merged into one of given circles,
    if the new circle and the given circle is the same circle.
    The given list of circles will be updated.
    """
    assert isinstance(facts, list) and all(isinstance(fact, Fact) for fact in facts)
    assert isinstance(circles, list) and all(isinstance(circle, Circle) for circle in circles)

    for fact in facts:
        if fact.pred_name in ("cyclic", "circle"):
            if fact.pred_name == "cyclic":
                new_circle = Circle(list(fact.args))
            if fact.pred_name == "circle":
                new_circle = Circle(list(fact.args[1:]), center=fact.args[0])
            same = [c for c in circles if new_circle.is_same_circle(c)]
            for c in same:
                new_circle.combine(c)
                circles.remove(c)
            circles.append(new_circle)


def apply_rule(rule, facts, *, lines=None, circles=None, ruleset=None, hyps):
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
    assert isinstance(facts, (tuple, list))
    assert all(isinstance(fact, Fact) for fact in facts)
    assert all(isinstance(fact, Fact) for fact in hyps)
    assert isinstance(ruleset, dict)
    assert isinstance(rule, str)

    rule_name = copy.copy(rule)
    rule = ruleset[rule]

    assert len(facts) == len(rule.assums)

    insts = [dict()]
    sources = [[]]
    for assum, fact in zip(rule.assums, facts):  # match the arguments recursively
        new_insts = []
        for i in range(len(insts)):
            news = match_expr(assum, fact, insts[i], lines=lines, circles=circles)
            new_insts.extend(news)
        insts = new_insts

    for inst in insts:  # An inst represents one matching result of match_expr().
        if rule.concl.args[0].islower():
            concl_args = []
            for i in rule.concl.args:
                concl_args.extend((inst[i][0], inst[i][1]))
        else:
            concl_args = [inst[i] for i in rule.concl.args]

        fact = Fact(rule.concl.pred_name, concl_args, updated=True, lemma=rule_name, cond=facts)

        exists = False
        for hyp in hyps:
            if not hyp.combined and check_imply(hyp, fact, lines, circles):
                # fact already exists
                exists = True
        if exists:
            continue

        new_facts = [fact]
        for target in hyps:
            if not target.combined and check_imply(fact, target, lines, circles):
                target.combined = True
            
            if not target.combined:
                new_fact = combine_facts(fact, target, lines, circles)
                if new_fact:
                    fact.combined = True
                    target.combined = True
                    fact = new_fact
                    new_facts.append(new_fact)

        # print(new_facts)
        hyps.extend(new_facts)


def search_step(ruleset, hyps, only_updated=False, lines=None, circles=None):
    """One step of searching fixpoint.

    Apply given ruleset to a list of hypotheses to obtain new facts.
    If collinear facts are included in hypotheses, new lines can be
    automatically generated, these new lines might be used when
    applying rules to hypotheses.

    """
    # Update the list of lines.
    make_new_lines(hyps, lines)
    make_new_circles(hyps, circles)

    avail_hyps = [hyp for hyp in hyps if not hyp.combined]
    for rule_name, rule in ruleset.items():
        for facts in itertools.permutations(avail_hyps, len(rule.assums)):
            if any(fact.combined for fact in facts):
                continue
            if only_updated and all(not fact.updated for fact in facts):
                continue
            apply_rule(rule_name, facts, lines=lines, circles=circles, ruleset=ruleset, hyps=hyps)


def search_fixpoint(ruleset, hyps, lines, circles, concl):
    """Recursively apply given ruleset to a list of hypotheses to
    obtain new facts. Recursion exits when new fact is not able
    to be generated, or conclusion is in the list of facts.
    Return the list of facts.
    """
    search_step(ruleset, hyps, lines=lines, circles=circles)
    prev_hyps = []
    prev_lines = []
    prev_circles = []
    steps = 0
    while hyps != prev_hyps or lines != prev_lines or circles != prev_circles:
        steps += 1
        print("Step", steps)
        if steps > 10:
            break
        prev_hyps = copy.copy(hyps)
        prev_lines = copy.copy(lines)
        prev_circles = copy.copy(circles)
        # print(list(hyp for hyp in hyps if hyp.combined == False))
        search_step(ruleset, hyps, only_updated=True, lines=lines, circles=circles)
        for fact in hyps:
            if check_imply(fact, concl, lines, circles):
                return fact

    assert False, "Fixpoint reached without proving goal."
    return None


def combine_facts(fact, goal, lines, circles):
    """
    Combine this fact to other fact.
    Return a combined long fact if succeed.

    """
    if fact.pred_name != goal.pred_name:
        return None

    def equal_pair(p1, p2):
        return p1 == p2 or p1 == (p2[1], p2[0])

    def equal_line(p1, p2):
        return get_line(lines, p1) == get_line(lines, p2)

    def equal_angle(a1, a2):
        p1, p2 = a1[0:2], a1[2:4]
        q1, q2 = a2[0:2], a2[2:4]
        return get_line(lines, p1) == get_line(lines, q1) and get_line(lines, p2) == get_line(lines, q2)

    if fact.pred_name == 'perp':
        # No combination
        return None

    elif fact.pred_name == 'coll':
        l1, l2 = Line(fact.args), Line(goal.args)
        if l1.is_same_line(l2):
            l1.combine(l2)
            return Fact('coll', list(l1.args), updated=True, lemma='combine', cond=[fact, goal])
        else:
            return None

    elif fact.pred_name == 'circle':
        c1, c2 = Circle(fact.args[1:], center=fact.args[0]), Circle(goal.args[1:], center=fact.args[0])

        if c1.is_same_circle(c2):
            c1.combine(c2)
            return Fact('circle', [c1.center] + list(c1.args), updated=True, lemma='combine', cond=[fact, goal])
        else:
            return None

    elif fact.pred_name == 'cyclic':
        c1, c2 = Circle(fact.args), Circle(goal.args)

        if c1.is_same_circle(c2):
            c1.combine(c2)
            return Fact('cyclic', list(c1.args), updated=True, lemma='combine', cond=[fact, goal])
        else:
            return None

    elif fact.pred_name == 'cong':
        # Check if any pair of points in fact and goal are the same
        # (exchange is allowed)
        can_combine = False
        f_pairs = make_pairs(fact.args)
        g_pairs = make_pairs(goal.args)
        if any(equal_pair(p1, p2) for p1 in f_pairs for p2 in g_pairs):
            new_args = []
            for p1 in f_pairs:
                new_args.extend(p1)
            for p2 in g_pairs:
                if not any(equal_pair(p1, p2) for p1 in f_pairs):
                    new_args.extend(p2)
            return Fact('cong', new_args, updated=True, lemma="combine", cond=[fact, goal])
        else:
            return None

    elif fact.pred_name == 'para':
        # Check if any pair of points in fact and goal denote the same line
        can_combine = False
        f_pairs = make_pairs(fact.args)
        g_pairs = make_pairs(goal.args)
        if any(equal_line(p1, p2) for p1 in f_pairs for p2 in g_pairs):
            new_args = []
            for p1 in f_pairs:
                new_args.extend(p1)
            for p2 in g_pairs:
                if not any(equal_line(p1, p2) for p1 in f_pairs):
                    new_args.extend(p2)
            return Fact('para', new_args, updated=True, lemma="combine", cond=[fact, goal])
        else:
            return None

    elif fact.pred_name == 'eqangle':
        # Check if any 4-tuple of points in fact and goal denote the same angle
        can_combine = False
        f_angles = make_pairs(fact.args, pair_len=4)
        g_angles = make_pairs(goal.args, pair_len=4)
        if any(equal_angle(a1, a2) for a1 in f_angles for a2 in g_angles):
            new_args = []
            for a1 in f_angles:
                new_args.extend(a1)
            for a2 in g_angles:
                if not any(equal_angle(a1, a2) for a1 in f_angles):
                    new_args.extend(a2)
            return Fact('eqangle', new_args, updated=True, lemma="combine", cond=[fact, goal])
        else:
            return None

    else:
        raise NotImplementedError


def check_imply(fact, goal, lines, circles):
    """Check whether the given fact is able to imply the given goal."""
    if fact.pred_name != goal.pred_name:
        return False

    def equal_pair(p1, p2):
        return p1 == p2 or p1 == (p2[1], p2[0])

    def equal_line(p1, p2):
        return get_line(lines, p1) == get_line(lines, p2)

    def equal_angle(a1, a2):
        p1, p2 = a1[0:2], a1[2:4]
        q1, q2 = a2[0:2], a2[2:4]
        return get_line(lines, p1) == get_line(lines, q1) and get_line(lines, p2) == get_line(lines, q2)

    if fact.pred_name == "perp":
        # Check the two lines are the same
        f1, f2 = make_pairs(fact.args)
        g1, g2 = make_pairs(goal.args)
        return equal_line(f1, g1) and equal_line(f2, g2)

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
        return all(any(equal_pair(f, g) for f in f_pairs) for g in g_pairs)

    elif fact.pred_name == 'para':
        # Check whether both lines in goal are in fact.
        f_pairs = make_pairs(fact.args)
        g_pairs = make_pairs(goal.args)
        return all(any(equal_line(f, g) for f in f_pairs) for g in g_pairs)

    elif fact.pred_name == "eqangle":
        # Check whether both angles in goal are in fact.
        f_angles = make_pairs(fact.args, pair_len=4)
        g_angles = make_pairs(goal.args, pair_len=4)
        return all(any(equal_angle(f, g) for f in f_angles) for g in g_angles)

    else:
        raise NotImplementedError

separators = {
    "eqangle": " = ",
    "default": ","
}


def print_search(ruleset, concl):
    """Print the process of searching fixpoint.
    The given list of facts must contains all the deduce procedures
    (as parameters of facts in the list). Using a given ruleset to
    find out the name of rules used in deduce procedures.

    """
    print_list = []
    def rec(fact):
        if fact in print_list:
            return

        for cond in fact.cond:
            rec(cond)
        print_list.append(fact)

    rec(concl)

    for fact in print_list:
        if fact.lemma == 'combine':
            print('combine', fact, ':-', ', '.join(str(cond) for cond in fact.cond))
        elif fact.lemma:
            print('(' + str(ruleset[fact.lemma]) + ')', fact, ':-', ', '.join(str(cond) for cond in fact.cond))
