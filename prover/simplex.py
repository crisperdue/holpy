"""
Implementation of Simplex-based quantifier-free linear arithmetic solver.

Reference: 
Bruno Dutertre and Leonardo de Moura. A Fast Linear-Arithmetic Solver for DPLL(T) 
"""

from kernel.term import Term, Var, Inst, greater_eq, Real, Eq, less_eq, minus
from kernel.type import RealType
from kernel.proofterm import ProofTerm
from kernel.theory import register_macro, Thm
from kernel.macro import Macro
from logic.logic import apply_theorem
from logic import basic, matcher
from data.real import real_eval, real_norm_conv
from logic.conv import Conv, ConvException, rewr_conv, top_conv
from collections import namedtuple
import math
import numbers
import string
from fractions import Fraction

basic.load_theory('real')

SAT, UNSAT = range(2)

geq_atom = namedtuple("geq_atom", ["var_name", "lower"])
leq_atom = namedtuple("leq_atom", ["var_name", "upper"])

class AssertUpperException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class UNSATException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class AssertLowerException(Exception):
    def __init__(self, *args, **kwargs):
        self.msg = msg

    def __str__(self):
        return self.msg

class Jar:
    """A pair (coeff, name), represent a coeff * var term."""
    def __init__(self, coeff, var):
        assert(isinstance(coeff, numbers.Number))
        assert(isinstance(var, str))
        self.coeff = coeff
        self.var = var

    def __str__(self):
        return "%s * %s" % (str(self.coeff), self.var)

    def __repr__(self):
        return "Jar(%s, %s)" % (str(self.coeff), self.var)

    def __eq__(self, value):
        return type(value) == Jar and self.coeff == value.coeff and self.var == value.var


class Bound:
    def __init__(self, lower, upper):
        assert isinstance(lower, numbers.Number) and isinstance(upper, numbers.Number)
        self.lower = lower
        self.upper = upper

    def __str__(self):
        return "[%s, %s]" % (str(self.lower), str(self.upper))

class Equation:
    """Each equation contains a dependent variable, and several independent variables."""
    def __init__(self, dept, indepts):
        assert isinstance(dept, Jar)
        assert all(isinstance(idt, Jar) for idt in indepts)
        self.dept = dept
        self.indepts = indepts

class InEquation:
    pass

class GreaterEq(InEquation):
    """Represent a greater equality term."""
    def __init__(self, jars, lower_bound):
        assert(all(isinstance(j, Jar) for j in jars))
        assert(isinstance(lower_bound, numbers.Number))
        self.jars = jars
        self.lower_bound = lower_bound

    def __str__(self):
        return " + ".join([str(jar) for jar in self.jars]) + " >= " + str(self.lower_bound)
        


class LessEq(InEquation):
    """Represent a greater equality term."""
    def __init__(self, jars, upper_bound):
        assert(all(isinstance(j, Jar) for j in jars))
        assert(isinstance(upper_bound, numbers.Number))
        self.jars = jars
        self.upper_bound = upper_bound

    def __str__(self):
        return " + ".join([str(jar) for jar in self.jars]) + " <= " + str(self.upper_bound)

class Tableau:
    """A tableau is a list of equalities.
    """
    def __init__(self, eqs):
        assert all(isinstance(eq, Equation) for eq in eqs)
        self.eqs = eqs

    def __len__(self):
        return len(self.eqs)

    def __getitem__(self, pos):
        return self.eqs[pos]

def collect_vars_from_ineq(ineq):
    """Give an inequation, return a set in which are the _vars."""
    assert isinstance(ineq, InEquation)
    _vars = set()
    for jar in ineq.jars:
        _vars.add(jar.var)

    return _vars

def find_coeff(v, jars):
    """Give a list of jars, return the jar whose variable is v,
    otherwise, return None
    """
    for i, j in enumerate(jars):
        if j.var == v:
            return (i, j)
    
    return (None, None)
    
def reduce_pairs(ps):
    """
    Same as the implementation in integral.poly. Reduce a list of pairs bycollecting 
    into groups according to first components, and adding the second component for each group.

    e.g. [("x", 1), ("y", 2), ("x", 3)] => [("x", 4), ("y", 2)]
    """
    res = {}
    for p in ps:
        v, c = p.var, p.coeff
        if v in res:
            res[v] += c
        else:
            res[v] = c
    
    pair = tuple(sorted((k, v) for k, v in res.items()))
    jars = [Jar(v, k) for k, v in pair]
    return jars

def delete_key(d, key):
    """delete a item in dict"""
    r = dict(d)
    del r[key]
    return r

def delete_elem(s, elem):
    """delete a item in set"""
    r = set(s)
    r.remove(elem)
    return r

class Simplex:
    """"""
    def __init__(self):
        # table represents the solver current tableau(state)
        self.equality = dict()

        # elementary atoms: y ⋈ b
        self.lower_atom = [] # y >= b
        self.upper_atom = [] # y <= b
        self.atom = []
        
        # mapping is the assignment for each variable
        self.mapping =  dict()
        
        # basic are the basic variables
        self.basic = set()
        
        # non_baic are the non-basic variables
        self.non_basic = set()
        
        # index for new introduced variable
        self.index = 0
        
        # bounds is a dict, key is the var_name, value is a pair: (lower_bound, upper_bound)
        self.bound = dict()

        # key is non-basic variable, value are the basic variables corresponding to it
        self.nbasic_basic = dict()

        # orignial inequalities inserted into solver
        self.orginal = []

        # basic variable that can't find a suitable value
        self.wrong_var = None

        # Restore the pivot trace: ((xi, xj), aij, nbasic[xj]) each time call check()
        self.trace = []

    def __str__(self):
        s = "Original inequlities: \n"
        for ineq in self.orginal:
            s += "\t %s\n" % str(ineq) 

        s += "Equality:\n"
        for lhs, rhs in self.equality.items():
            s += "\t %s := " % str(lhs) + " + ".join(str(jar) for jar in rhs) + "\n"

        s += "\nlower_atom:\n"
        for lhs, rhs in self.lower_atom:
            s += "\t %s >= %s\n" % (str(lhs), str(rhs))

        s += "\nupper_atom:\n"
        for lhs, rhs in self.upper_atom:
            s += "\t %s <= %s\n" % (str(lhs), str(rhs))

        s += "\nAssignments:\n"

        for key, value in self.mapping.items():
            s += "\t %s := %s\n" % (str(key), str(value))

        s += "\nBasic Variables:\n"
        for b in self.basic:
            s += "\t" + b + "\n"

        s += "\nNon-basic Variables:\n"
        for b in self.non_basic:
            s += "\t" + b + "\n"

        s += "\nBounds:\n"
        for key, (lower, upper) in self.bound.items():
            s += "\t %s: [%s, %s]\n" % (key, str(lower), str(upper))

        s += "\nRelation between non-basic variables and corresponding basic variables\n"
        for key, value in self.nbasic_basic.items():
            s += "\t %s: " % str(key) + ", ".join(str(v) for v in value) + "\n"
        return s

    def add_ineq(self, ineq):
        """
        Add an inequality to the current solver, and update relevant states.
        """
        assert isinstance(ineq, InEquation)
        self.orginal.append(ineq)
        if isinstance(ineq, GreaterEq):
            if len(ineq.jars) == 1: # a * x >= b
                jar = ineq.jars[0]
                coeff, var_name, lower_bound = jar.coeff, jar.var, ineq.lower_bound
                if coeff == 1: # x >= b (atom)
                    self.lower_atom.append((var_name, lower_bound))
                    self.atom.append(geq_atom(var_name, lower_bound))
                    if var_name not in self.mapping:
                        self.mapping[var_name] = 0
                    self.non_basic.add(var_name)
                    if var_name not in self.bound.keys():
                        self.bound[var_name] = (-math.inf, math.inf)

                elif coeff != 0: # a * x >= b
                    s = "$" + string.ascii_lowercase[self.index] + "$"
                    self.index += 1
                    self.lower_atom.append((s, lower_bound))
                    self.atom.append(geq_atom(s, lower_bound))
                    self.equality[s] = ineq.jars
                    self.basic.add(s)
                    self.non_basic.add(var_name)
                    if var_name not in self.nbasic_basic:
                        self.nbasic_basic[var_name] = {s}
                    else:
                        self.nbasic_basic[var_name].add(s)        
            
                    if var_name not in self.mapping:
                        self.mapping.update({var_name : 0, s : 0})
                    self.bound[s] = (-math.inf, math.inf)
                    if var_name not in self.bound:
                        self.bound[var_name] = (-math.inf, math.inf)

            else: # a * x + b * y + ... >= c
                _vars = collect_vars_from_ineq(ineq)
                # push all variables in lhs into solver
                for v in _vars:
                    if v not in self.mapping.keys():
                        self.mapping.update({v: 0})
                    if v not in self.non_basic:
                        self.non_basic.add(v)
                    if v not in self.bound.keys():
                        self.bound[v] = (-math.inf, math.inf) 

                lower_bound = ineq.lower_bound
                s = "$" + string.ascii_lowercase[self.index] + "$"
                self.index += 1
                self.equality[s] = ineq.jars
                self.lower_atom.append((s, lower_bound))
                self.atom.append(geq_atom(s, lower_bound))
                self.mapping[s] = 0
                for jar in ineq.jars:
                    if jar.var not in self.nbasic_basic:
                        self.nbasic_basic[jar.var] = {s}
                    else:
                        self.nbasic_basic[jar.var].add(s)
                
                self.basic.add(s)
                self.bound[s] = (-math.inf, math.inf)

        elif isinstance(ineq, LessEq):
            if len(ineq.jars) == 1: # a * x <= b
                jar = ineq.jars[0]
                coeff, var_name, upper_bound = jar.coeff, jar.var, ineq.upper_bound
                if coeff == 1: # x <= b (atom)
                    self.upper_atom.append((var_name, upper_bound))
                    self.atom.append(leq_atom(var_name, upper_bound))
                    if var_name not in self.mapping:
                        self.mapping[var_name] = 0
                    self.non_basic.add(var_name)
                    if var_name not in self.bound.keys():
                        self.bound[var_name] = (-math.inf, math.inf)

                elif coeff != 0: # a * x <= b
                    s = "$" + string.ascii_lowercase[self.index] + "$"
                    self.index += 1
                    self.upper_atom.append((s, upper_bound))
                    self.atom.append(leq_atom(s, upper_bound))
                    self.equality[s] = ineq.jars
                    self.basic.add(s)
                    self.non_basic.add(var_name)
                    if var_name not in self.mapping:
                        self.mapping.update({var_name : 0, s : 0})
                    self.bound[s] = (-math.inf, math.inf)
                    if var_name not in self.nbasic_basic:
                        self.nbasic_basic[var_name] = {s}
                    else:
                        self.nbasic_basic[var_name].add(s)
                    if var_name not in self.bound.keys():
                        self.bound[var_name] = (-math.inf, math.inf)

            else: # a * x + b * y + ... <= c
                _vars = collect_vars_from_ineq(ineq)
                # push all variables in lhs into solver
                for v in _vars:
                    if v not in self.mapping.keys():
                        self.mapping.update({v: 0})
                    if v not in self.non_basic:
                        self.non_basic.add(v)
                    if v not in self.bound.keys():
                        self.bound[v] = (-math.inf, math.inf)

                upper_bound = ineq.upper_bound
                s = "$" + string.ascii_lowercase[self.index] + "$"
                self.index += 1
                self.equality[s] = ineq.jars
                self.upper_atom.append((s, upper_bound))
                self.atom.append(leq_atom(s, upper_bound))
                self.mapping[s] = 0
                for jar in ineq.jars:
                    if jar.var not in self.nbasic_basic:
                        self.nbasic_basic[jar.var] = {s}
                    else:
                        self.nbasic_basic[jar.var].add(s)

                self.basic.add(s)
                self.bound[s] = (-math.inf, math.inf)

    def preprocess(self):
        """
        Simplify the constraints Ax = 0 by Gauss elimination.
        Remove any variable xi that does not occur in any elementary atom of inequalities.
        Introduce a new variable when elimination is done.
        """
        pass

    def aij(self, xi, xj):
        """
        xi is a basic variable, xj is a non_basic variable.
        return the aij in the equation of xi = ... + aij * xj + ...
        """
        assert xi in self.basic and xj in self.non_basic
        jars = self.equality[xi]
        _, res =  find_coeff(xj, jars)
        return res.coeff if res is not None else 0
    
    def update(self, x, v):
        assert x in self.non_basic
        rlt = self.nbasic_basic[x]
        for b in rlt:
            a = self.aij(b, x)
            self.mapping[b] += a * (v - self.mapping[x])
        
        self.mapping[x] = v

    def pivot(self, xi, xj):
        """
        xi is a basic variable, xj is a non-basic variable.
        Delete xi from basic sets, delete xj from non-basic sets
        Suppose the original equality is:
                        xi = ... + aij * xj + ...
        then we could the representation of xj:
                        xj = 1/aij * xi + -...
        After get the representation, we find other equalities which use xj,
        substitute xj with the above equality's rhs and normalize it.
        """
        assert xi in self.basic and xj in self.non_basic
        a = self.aij(xi, xj)
        # get the equality
        jars = self.equality[xi]
        xj_repr_jars = [Jar(Fraction(1, a), xi)] + [Jar(-Fraction(1, a) * Fraction(jar.coeff), jar.var) for jar in jars if jar.var != xj]
        xj_repr_jars = reduce_pairs(xj_repr_jars)
        # update the state
        
        # update equality, delete the previous xi = ...
        # add new term xj = ... 
        # for the other equalities which use xj, try to substitute xj
        # by xj_repr_jars
        self.equality = delete_key(self.equality, xi)
        self.equality[xj] = xj_repr_jars
        equlity_has_xj = []
        for x in self.nbasic_basic[xj]:
            if x != xi:
                rhs = self.equality[x]
                _, xj_jar = find_coeff(xj, rhs)
                rhs_without_xj = reduce_pairs([j for j in rhs if j != xj_jar] + [Jar(xj_jar.coeff * v.coeff, v.var) for v in xj_repr_jars])
                self.equality[x] = rhs_without_xj

        # update basic and non_basic variables
        self.basic = delete_elem(self.basic, xi)
        self.non_basic = delete_elem(self.non_basic, xj)
        self.basic.add(xj)
        self.non_basic.add(xi)

        # update nbasic_basic
        self.nbasic_basic = dict()
        for key, value in self.equality.items():
            for v in value:
                if v.var in self.nbasic_basic:
                    self.nbasic_basic[v.var].add(key)
                else:
                    self.nbasic_basic[v.var] = {key}

    def pivotAndUpdate(self, xi, xj, v):
        assert xi in self.basic and xj in self.non_basic
        a = self.aij(xi, xj)
        theta = Fraction(v - self.mapping[xi], a)
        self.mapping[xi] = v
        self.mapping[xj] = self.mapping[xi] + theta
        for xk in self.basic:
            if xk != xi:
                k = self.aij(xk, xj)
                self.mapping[xk] += k * theta

        self.pivot(xi, xj)

    def assert_upper(self, x, c):
        assert x in self.bound, "No such variable in solver"
        l, u = self.bound[x]
        if c >= u:
            return
        elif c < l:
            raise AssertUpperException("%s's lower bound %s is larger than %s" % (x, str(l), str(c)))
        
        self.bound[x] = (l, c)
        if x in self.non_basic and self.mapping[x] > c:
            self.update(x, c)

    def assert_lower(self, x, c):
        assert x in self.bound, "No such variable in solver"
        l, u = self.bound[x]
        if c <= l:
            return
        elif c > u:
            raise AssertUpperException("%s's lower bound %s is larger than c" % (x, str(l), str(c)))
        
        self.bound[x] = (c, u)
        if x in self.non_basic and self.mapping[x] < c:
            self.update(x, c)

    def check(self):
        self.wrong_var = None
        self.pivot_trace = []
        while True:
            basic_vars = sorted(list(self.basic))
            flag = False
            for v in basic_vars:
                if self.bound[v][0] > self.mapping[v] or self.bound[v][1] < self.mapping[v]:
                    xi = v
                    flag = True
            if not flag:
                return SAT
            
            if self.mapping[xi] < self.bound[xi][0]:
                flag = False
                rhs_jars = reduce_pairs(self.equality[xi])
                for j in rhs_jars:
                    coeff, xj = j.coeff, j.var
                    if coeff > 0 and self.mapping[xj] < self.bound[xj][1] or\
                        coeff < 0 and self.mapping[xj] > self.bound[xj][0]:
                        self.trace.append(((xi, xj), coeff, self.nbasic_basic[xj]))
                        self.pivotAndUpdate(xi, xj, self.bound[xi][0])
                        flag = True
                        break
                if not flag:
                    self.wrong_var = xi
                    return UNSAT

            if self.mapping[xi] > self.bound[xi][1]:
                flag = False
                rhs_jars = reduce_pairs(self.equality[xi])
                for j in rhs_jars:
                    coeff, xj = j.coeff, j.var
                    if coeff < 0 and self.mapping[xj] < self.bound[xj][1] or\
                        coeff > 0 and self.mapping[xj] > self.bound[xj][0]:
                        self.trace.append(((xi, xj), coeff, self.nbasic_basic[xj]))
                        self.pivotAndUpdate(xi, xj, self.bound[xi][1])
                        flag = True
                        break
                
                if not flag:
                    self.wrong_var = xi
                    return UNSAT

    def handle_assertion(self):
        for assertion in self.atom:
            if isinstance(assertion, leq_atom):
                self.assert_upper(assertion.var_name, assertion.upper)
                
            else:
                self.assert_lower(assertion.var_name, assertion.lower)

            if assertion.var_name in self.basic:
                res = self.check()
                if res == UNSAT:
                    raise UNSATException("variable %s is wrong." % str(self.wrong_var))

    def explaination(self, xi):
        """
        When a conflict occurs, return the minimal clause.

        There are two main reasons for inconsistency:

        1) A basic variable xi such that β(xi) < li and for all non-basic variable we have
        aij > 0 --> β(xj) ≥ uj and aij < 0 --> β(xj) ≤ lj.

        2) A basic variable xj such that β(xj) > uj and for all non-basic variable we have
        aij > 0 --> β(xj) ≤ lj and aij < 0 --> β(xj) ≥ uj.

        For 1), the clause is
            Γ  = {xj ≤ uj | j ∈ N+} ∪ {xj ≥ lj | j ∈ N-} ∪ {xi ≥ li}

        For 2), the clause is
            Γ  = {xj ≥ lj | j ∈ N+} ∪ {xj ≤ uj | j ∈ N-} ∪ {xj ≤ ui}
        """
        explain = [] # store the atoms
        if self.mapping[xi] < self.bound[xi][0]: # reason 1
            for jar in self.equality[xi]:
                if jar.coeff > 0:
                    upper = self.bound[jar.var][1]
                    explain.append(leq_atom(jar.var, upper))
                else:
                    lower = self.bound[jar.var][0]
                    explain.append(geq_atom(jar.var, lower))
            explain.append(geq_atom(xi, self.bound[xi][0]))

        else:
            for jar in self.equality[xi]:
                if jar.coeff > 0:
                    lower = self.bound[jar.var][0]
                    explain.append(geq_atom(jar.var, lower))
                else:
                    upper = self.bound[jar.var][1]
                    explain.append(leq_atom(jar.var, upper))
            explain.append(leq_atom(xi, self.bound[xi][1]))    

        return explain


def dest_plus(tm):
    """tm is of form x + y, return (x, y)"""
    if not tm.is_plus():
        return (tm,)
    if not tm.arg1.is_plus():
        return (tm.arg1, tm.arg)
    else:
        return dest_plus(tm.arg1) + (tm.arg,)

def add_atom(d, key, atom):
    """
    d is a dict, add an atom to list d[key] 
    """
    if key not in d:
        d[key] = (atom, )
    else:
        d[key] = tuple(d[key] + (atom, ))
    
    return d  

def is_ineq(tm):
    """check if tm is an ineq term."""
    return tm.is_greater() or tm.is_greater_eq() or tm.is_less() or tm.is_less_eq()

@register_macro('real_compare')
class RealCompareMacro(Macro):
    """
    Compare two real numbers.
    """
    def __init__(self):
        self.level = 0
        self.sig = Term
        self.limit = None

    def eval(self, goal, prevs=[]):
        assert is_ineq(goal), "real_compare_macro: Should be an inequality term"
        lhs, rhs = real_eval(goal.arg1), real_eval(goal.arg)
        if goal.is_less():
            assert lhs < rhs, "%f !< %f" % (lhs, rhs)
        elif goal.is_less_eq():
            assert lhs <= rhs, "%f !<= %f" % (lhs, rhs)
        elif goal.is_greater():
            assert lhs > rhs, "%f !> %f" % (lhs, rhs)
        elif goal.is_greater_eq():
            assert lhs >= rhs, "%f !>= %f" % (lhs, rhs)
        
        return Thm([], goal)

class replace_conv(Conv):
    def __init__(self, pt):
        self.pt = pt

    def get_proof_term(self, t):
        if t == self.pt.prop.lhs:
            return self.pt
        else:
            raise ConvException

class SimplexHOLWrapper:
    """
    Wrapper for simplex method in higher-order logic. 
    """
    def __init__(self):
        # core data structure
        self.simplex = Simplex()
        
        # # proofterms for input inequlities, key is the HOL lhs
        self.ineq_pts = dict()

        # proofterms for equalities, key is the new introduced variable
        self.eq_pts = dict()

        # proofterm for atom inequalities, used in assertion procedure
        self.atom_ineq_pts = dict()

        # proofterms for bounds, key is variable.
        self.lower_bound_pts = dict()
        self.upper_bound_pts = dict()

        # Unsatisfiable proof, key is variable which leads to inconsistency
        self.unsat = dict()

    def __str__(self):
        s = "Inequality ProofTerms: \n"
        for _, pt in self.ineq_pts.items():
            s += "\t %s \n" % str(pt)
        
        s += "\nEquality ProofTerms: \n"
        for _, pt in self.eq_pts.items():
            s += "\t %s \n" % str(pt)
        
        s +="\nInequality atom ProofTerms:\n"
        for _, pt in self.atom_ineq_pts.items():
            s += "\t %s \n" % str(pt)

        s += "\nLower Bound ProofTerms:\n"
        for _, pt in self.lower_bound_pts.items():
            s += "\t %s \n" % str(pt)

        s += "\nUpper Bound ProofTerms:\n"
        for _, pt in self.upper_bound_pts.items():
            s += "\t %s \n" % str(pt)

        return s

    def add_ineq(self, ineq):
        """
        Take an inequation, convert it higher-order logic terms.
        Add the inequation to ineq_pts.
        If necessary, introduce new variables to construct elemenatry atoms, and also
        add equality proofterm to eq_pts.
        """
        assert isinstance(ineq, InEquation)
        lhs_atoms = [Real(j.coeff) * Var(j.var, RealType) for j in ineq.jars]
        lhs = sum(lhs_atoms[1:], lhs_atoms[0])
        if isinstance(ineq, GreaterEq): # a * x + b * y + ... ≥ c    
            rhs = Real(ineq.lower_bound)
            hol_ineq = greater_eq(RealType)(lhs, rhs)
            self.ineq_pts[hol_ineq] = ProofTerm.assume(hol_ineq)
        else: # a * x + b * y + ... ≤ c
            rhs = Real(ineq.upper_bound)
            hol_ineq = less_eq(RealType)(lhs, rhs)
            self.ineq_pts[hol_ineq] = ProofTerm.assume(hol_ineq)
        
        # Add the inequation to the simplex solver.
        self.simplex.add_ineq(ineq)
        
        # Check the necessity to introduce new variables
        if not (len(ineq.jars) == 1 and ineq.jars[0].coeff == 1): # need to introduce a new variable
            s = Var('$'+string.ascii_lowercase[self.simplex.index - 1]+'$', RealType)
            s_eq_pt = ProofTerm.assume(Eq(s, lhs))
            self.eq_pts[s] = s_eq_pt
            # construct the inequlity proofterm for x
            s_ineq_pt = ProofTerm.assume(hol_ineq).on_prop(top_conv(replace_conv(s_eq_pt.symmetric())))
            self.atom_ineq_pts = add_atom(self.atom_ineq_pts, s, s_ineq_pt)
        else: # directly add x ⋈ c into atom_ineq_pts 
            x = lhs.arg
            # prove 1 * x = x
            pt_x = real_norm_conv().get_proof_term(1 * x)
            pt_atom = ProofTerm.assume(hol_ineq).on_prop(top_conv(replace_conv(pt_x)))
            self.atom_ineq_pts = add_atom(self.atom_ineq_pts, x, pt_atom)
            
    def assert_upper(self, x, upper_bound):
        """
        Assert x <= c. If there is already an assertion on x's upper bound,
        suppose it is d, if c <= d, then apply the new assertion, otherwise 
        still take the old assertion.
        If there is an assertion on x's lower bound, suppose it is e; If e > c,
        then we can derive a direct contradiction: x <= c and x >= e is inconsistency. 
        """
        upper_bound = real_eval(upper_bound)
        self.simplex.assert_upper(x.name, upper_bound)
        assertion = ProofTerm.assume(x <= upper_bound)
        if x in self.upper_bound_pts:
            old_assertion = self.upper_bound[x]
            old_upper_bound = real_eval(old_assertion.prop.arg)
            if old_upper_bound >= upper_bound:
                pt_less = ProofTerm('real_compare', upper_bound <= old_upper_bound)
                self.upper_bound_pts[x] = apply_theorem('real_geq_comp2', assertion, old_assertion, pt_less)
            new_upper_bound = upper_bound if (old_upper_bound >= upper_bound) else old_upper_bound
        else:
            self.upper_bound_pts[x] = assertion
            new_upper_bound = upper_bound
        

        # check consistency with x's lower bound
        if x in self.lower_bound_pts:
            lower_assertion = self.lower_bound[x]
            lower_bound = real_eval(lower_assertion.prop.arg)
            if lower_bound > new_upper_bound: # incosistency
                pt_up_less_low = ProofTerm('real_compare', new_upper_bound < lower_bound)
                pt_contr = apply_theorem('real_comp_contr', pt_up_less_low, lower_assertion, self.upper_bound_pts[x])
                self.unsat[x] = pt_contr
        
    def assert_lower(self, x, lower_bound):
        """
        Assert x >= c. If there is already an assertion on x's lower bound,
        suppose it is d, if c >= d, then apply the new assertion, otherwise 
        still take the old assertion.
        If there is an assertion on x's upper bound, suppose it is e: If e < c,
        then we can derive a direct contradiction: x >= c and x <= e is inconsistency. 
        """
        lower_bound = real_eval(lower_bound)
        self.simplex.assert_lower(x.name, lower_bound)
        assertion = ProofTerm.assume(x >= lower_bound)
        if x in self.lower_bound_pts:
            old_assertion = self.lower_bound[x]
            old_lower_bound = real_eval(old_assertion.prop.arg)
            if old_lower_bound <= lower_bound:
                pt_greater = ProofTerm('real_compare', lower_bound >= old_lower_bound)
                self.lower_bound_pts[x] = apply_theorem('real_geq_comp2', assertion, old_assertion, pt_greater)
            new_lower_bound = lower_bound if (old_lower_bound >= lower_bound) else old_lower_bound
        else:
            self.lower_bound_pts[x] = assertion
            new_lower_bound = lower_bound
        

        # check consistency with x's lower bound
        if x in self.upper_bound_pts:
            upper_assertion = self.upper_bound[x]
            upper_bound = real_eval(upper_assertion.prop.arg)
            if upper_bound < new_lower_bound: # incosistency
                pt_up_less_low = ProofTerm('real_compare', upper_bound < new_lower_bound)
                pt_contr = apply_theorem('real_comp_contr', pt_up_less_low, upper_assertion, self.lower_bound_pts[x])
                self.unsat[x] = pt_contr

    def pivot(self, xi, xj, basic_var, coeff):
        """
        Pivot basic variable xi and non-basic variable xj. 
        """

        # Find the xj occurrence in other equalities, try to substitute it by xj's rhs.
        basic_variable_xj_lhs = delete_elem(basic_var, xi.name)
        basic_variable_xj_lhs = [Var(v, RealType) for v in basic_variable_xj_lhs]
        a = coeff # aij
        
        # find the equation: xi = ... + aij * xj + ...
        # aij ≠ 0
        pt_eq = self.eq_pts[xi]
        # convert the equation to xj = ...
        # use theorem: real_sub_0, real_mul
        # xi - (... + aij * xj + ...) = 0
        pt_right_shift = pt_eq.on_prop(rewr_conv('real_sub_0', sym=True))
        # construct (xi - (... + aij * xj + ...)) * 1/aij = 0
        pt_divide_aij = real_norm_conv().get_proof_term(Fraction(1, a) * pt_right_shift.lhs)
        # normalize lhs
        pt_divide_aij_norm = pt_divide_aij.on_lhs(real_norm_conv())
        
        pt_eq_mul_coeff = apply_theorem('real_eq_zero_mul_const', pt_right_shift, inst=Inst(c = Real(Fraction(1, a))))
        pt_divide_aij_norm_0 = pt_divide_aij.symmetric().transitive(pt_eq_mul_coeff)
        # convert to ... + (-1) * xj = 0
        eq_lhs = pt_divide_aij_norm.lhs
        eq_lhs_dest = dest_plus(eq_lhs)
        pt_eq_lhs = real_norm_conv().get_proof_term(eq_lhs)
        adder_except_xj = [t if t.is_times() else 1 * t for t in eq_lhs_dest]
        adder_except_xj = [t for t in adder_except_xj if t.arg != xj]
        eq_lhs_xj_right = sum(adder_except_xj[1:], adder_except_xj[0]) + (-1) * xj
        pt_eq_lhs_xj_right = real_norm_conv().get_proof_term(eq_lhs_xj_right)
        pt_eq_comm = ProofTerm.transitive(pt_eq_lhs, pt_eq_lhs_xj_right.symmetric())
        pt_comm_eq_0 = pt_eq_comm.symmetric().transitive(pt_divide_aij_norm_0)

        # xj = ... + (1/aij) * xi + ... 
        pt_final = pt_comm_eq_0.on_prop(rewr_conv('real_add_uminus')).symmetric()
        self.eq_pts[xj] = pt_final
        self.eq_pts = delete_key(self.eq_pts, xi)

        # euqalities relevant to xj
        for _v in basic_variable_xj_lhs:
            v_lhs_eq_pt = self.eq_pts[_v]
            v_lhs_eq_pt_replace_norm = v_lhs_eq_pt.on_rhs(top_conv(replace_conv(pt_final)), real_norm_conv())
            self.eq_pts[_v] = v_lhs_eq_pt_replace_norm

    def explanation(self):
        pass

    def handle_assertion(self):
        """
        Assert each atom assertion, either get a bound or raise a contradiction.
        """
        for var, asts in self.atom_ineq_pts.items():
            for ast in asts:
                if ast.prop.is_less_eq():
                    self.assert_upper(var, ast.prop.arg)
                else:
                    self.assert_lower(var, ast.prop.arg)

            if var.name in self.simplex.basic:
                # check
                if self.simplex.check() == UNSAT:
                    trace = self.simplex.trace
                    for xij, coeff, basic_var in trace:
                        xi, xj = xij
                        self.pivot(Var(xi, RealType), Var(xj, RealType), basic_var, coeff)
                    self.explanation()