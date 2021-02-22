"""Deciding inequalities."""

import math

from kernel.type import RealType
from kernel import term
from kernel.term import Term, Var, Lambda, Inst, Nat, Real, Eq
from kernel.thm import Thm
from kernel.proofterm import ProofTerm, TacticException
from kernel.macro import Macro
from kernel.theory import register_macro
from logic.conv import Conv, ConvException, then_conv, binop_conv, arg_conv, arg1_conv, rewr_conv
from logic.logic import apply_theorem
from data import nat
from data import real
from data import set as hol_set
from logic import auto
from integral import expr


LESS, EQUAL, GREATER = range(3)

def eval_hol_expr(t):
    """Evaluate an HOL term of type real.

    First try the exact evaluation with real_eval. If that fails, fall back
    to approximate evaluation with real_approx_eval.

    """
    try:
        res = real.real_eval(t)
    except ConvException:
        res = real.real_approx_eval(t)
    
    return res

def eval_expr(e):
    t = expr.expr_to_holpy(e)
    return eval_hol_expr(t)

def eval_inequality_expr(t):
    """Evaluate inequality."""
    if t.is_equals():
        return eval_hol_expr(t.arg1) == eval_hol_expr(t.arg)
    elif t.is_not() and t.arg.is_equals():
        return eval_hol_expr(t.arg.arg1) != eval_hol_expr(t.arg.arg)
    elif t.is_greater_eq():
        return eval_hol_expr(t.arg1) >= eval_hol_expr(t.arg)
    elif t.is_greater():
        return eval_hol_expr(t.arg1) > eval_hol_expr(t.arg)
    elif t.is_less_eq():
        return eval_hol_expr(t.arg1) <= eval_hol_expr(t.arg)
    elif t.is_less():
        return eval_hol_expr(t.arg1) < eval_hol_expr(t.arg)
    else:
        raise NotImplementedError


def expr_compare(expr1, expr2):
    """Comparison between two expressions according to their value."""
    assert isinstance(expr1, expr.Expr) and isinstance(expr2, expr.Expr), \
        "expr_compare: wrong type of arguments."

    t1 = expr.expr_to_holpy(expr1)
    t2 = expr.expr_to_holpy(expr2)
    try:
        e1 = real_eval(t1)
        e2 = real_eval(t2)
    except ConvException:
        raise TacticException

    if e1 < e2:
        return LESS
    elif e1 > e2:
        return GREATER
    else:
        return EQUAL

def expr_min(*exprs):
    """Minimum of a list of expressions."""
    assert len(exprs) > 1, "expr_min: empty argument"
    if len(exprs) == 1:
        return exprs[0]
    else:
        min_rest = expr_min(*(exprs[1:]))
        if expr_compare(exprs[0], min_rest) == LESS:
            return exprs[0]
        else:
            return min_rest

def expr_max(*exprs):
    """Maximum of a list of expressions."""
    assert len(exprs) > 1, "expr_max: empty argument"
    if len(exprs) == 1:
        return exprs[0]
    else:
        max_rest = expr_max(*(exprs[1:]))
        if expr_compare(exprs[0], max_rest) == GREATER:
            return exprs[0]
        else:
            return max_rest


class Interval:
    """Specifies an interval. Each side can be either open or closed."""
    def __init__(self, start, end, left_open, right_open):
        self.start = start
        self.end = end
        self.left_open = left_open
        self.right_open = right_open

    def __str__(self):
        left = '(' if self.left_open else '['
        right = ')' if self.right_open else ']'
        return left + str(self.start) + ', ' + str(self.end) + right

    @staticmethod
    def closed(start, end):
        return Interval(start, end, left_open=False, right_open=False)

    @staticmethod
    def open(start, end):
        return Interval(start, end, left_open=True, right_open=True)

    @staticmethod
    def lopen(start, end):
        return Interval(start, end, left_open=True, right_open=False)

    @staticmethod
    def ropen(start, end):
        return Interval(start, end, left_open=False, right_open=True)

    @staticmethod
    def point(val):
        return Interval.closed(val, val)

    def is_closed(self):
        return not self.left_open and not self.right_open

    def is_open(self):
        return self.left_oepn and self.right_open

    def __add__(self, other):
        """Addition in interval arithmetic."""
        return Interval((self.start + other.start).normalize_constant(),
                        (self.end + other.end).normalize_constant(),
                        self.left_open or other.left_open,
                        self.right_open or other.right_open)

    def __neg__(self):
        """Negation (unitary minus) of an interval."""
        return Interval(-self.end, -self.start, self.right_open, self.left_open)

    def __sub__(self, other):
        """Subtraction in interval arithmetic."""
        return self + (-other)

    def __mul__(self, other):
        """Product in interval arithmetic."""
        bounds = [
            (self.start * other.start, self.left_open or other.left_open),
            (self.start * other.end, self.left_open or other.right_open),
            (self.end * other.start, self.right_open or other.left_open),
            (self.end * other.end, self.right_open or other.right_open)
        ]

        start, left_open = min(bounds, key=lambda p: (eval_expr(p[0]), p[1]))
        end, right_open = max(bounds, key=lambda p: (eval_expr(p[0]), p[1]))
        return Interval(start.normalize_constant(), end.normalize_constant(), left_open, right_open)

    def inverse(self):
        """Inverse of an interval."""
        return Interval((1 / self.end).normalize_constant(),
                        (1 / self.start).normalize_constant(),
                        self.right_open, self.left_open)

    def __truediv__(self, other):
        """Quotient in interval arithmetic."""
        return self * other.inverse()

    def __pow__(self, other):
        """Power in interval arithmetic."""
        if eval_expr(other.start) >= 0:
            return Interval(self.start ** other.start, self.end ** other.end,
                            self.left_open or other.left_open,
                            self.right_open or other.right_open)
        elif eval_expr(other.end) <= 0:
            return Interval(self.end ** other.end, self.start ** other.start,
                            self.right_open or other.right_open,
                            self.left_open or other.left_open)
        else:
            raise NotImplementedError

    def less(self, other):
        """Whether self is strictly less than other."""
        if eval_expr(self.end) < eval_expr(other.start):
            return True
        elif eval_expr(self.end) <= eval_expr(other.start):
            return self.right_open or other.left_open
        else:
            return False

    def less_eq(self, other):
        """Whether self is less than or equal to other."""
        return eval_expr(self.end) <= eval_expr(other.start)

    def greater(self, other):
        return other.less(self)

    def greater_eq(self, other):
        return other.less_eq(self)

    def not_eq(self, other):
        return self.less(other) or self.greater(other)

    def contained_in(self, other):
        if eval_expr(self.start) < eval_expr(other.start):
            return False
        if eval_expr(self.start) == eval_expr(other.start) and \
            (not self.left_open) and other.left_open:
            return False
        if eval_expr(self.end) > eval_expr(other.end):
            return False
        if eval_expr(self.end) == eval_expr(other.end) and \
            (not self.right_open) and other.right_open:
            return False
        return True

    def sqrt(self):
        """Square root of interval."""
        return Interval(expr.Fun('sqrt', self.start).normalize_constant(),
                        expr.Fun('sqrt', self.end).normalize_constant(),
                        self.left_open, self.right_open)

    def exp(self):
        """Exp function of an interval."""
        return Interval(expr.Fun('exp', self.start).normalize_constant(),
                        expr.Fun('exp', self.end).normalize_constant(),
                        self.left_open, self.right_open)

    def log(self):
        """Log function of an interval."""
        return Interval(expr.Fun('log', self.start).normalize_constant(),
                        expr.Fun('log', self.end).normalize_constant(),
                        self.left_open, self.right_open)

    def sin(self):
        """Sin function of an interval."""
        if self.contained_in(Interval(-(expr.pi / 2), expr.pi / 2, False, False)):
            return Interval(expr.Fun('sin', self.start).normalize_constant(),
                            expr.Fun('sin', self.end).normalize_constant(),
                            self.left_open, self.right_open)
        elif self.contained_in(Interval(expr.Const(0), expr.pi, False, False)):
            return Interval(expr.Const(0), expr.Const(1), False, False)
        else:
            raise NotImplementedError

    def cos(self):
        """Cos function of an interval."""
        if self.contained_in(Interval(expr.Const(0), expr.pi, False, False)):
            return Interval(expr.Fun('cos', self.end).normalize_constant(),
                            expr.Fun('cos', self.start).normalize_constant(),
                            self.right_open, self.left_open)
        elif self.contained_in(Interval(-(expr.pi / 2), expr.pi / 2, False, False)):
            return Interval(expr.Const(0), expr.Const(1), False, False)
        else:
            raise NotImplementedError


def interval_to_holpy(i):
    """Convert interval to HOL term.
    
    Currently only support open and closed intervals.

    """
    e1, e2 = expr.expr_to_holpy(i.start), expr.expr_to_holpy(i.end)
    if i.left_open and i.right_open:
        return real.open_interval(e1, e2)
    elif not i.left_open and not i.right_open:
        return real.closed_interval(e1, e2)
    elif i.left_open and not i.right_open:
        return real.lopen_interval(e1, e2)
    elif not i.left_open and i.right_open:
        return real.ropen_interval(e1, e2)
    else:
        raise NotImplementedError


def get_bounds(e, var_range):
    """Obtain the range of expression e as a variable.

    e - expr.Expr, an expression.
    var_range - dict(str, Interval): mapping from variables to intervals.

    Returns Interval: an overapproximation of the values of e.

    """
    if e.ty == expr.VAR:
        assert e.name in var_range, "get_bounds: variable %s not found" % e.name
        return var_range[e.name]

    elif e.ty == expr.CONST:
        return Interval.closed(e, e)

    elif e.ty == expr.OP:
        if e.is_plus():
            return get_bounds(e.args[0], var_range) + get_bounds(e.args[1], var_range)
        elif e.is_uminus():
            return -get_bounds(e.args[0], var_range)
        elif e.is_minus():
            return get_bounds(e.args[0], var_range) - get_bounds(e.args[1], var_range)
        elif e.is_times():
            return get_bounds(e.args[0], var_range) * get_bounds(e.args[1], var_range)
        elif e.is_divides():
            return get_bounds(e.args[0], var_range) / get_bounds(e.args[1], var_range)
        elif e.is_power():
            return get_bounds(e.args[0], var_range) ** get_bounds(e.args[1], var_range)
        else:
            raise NotImplementedError

    elif e.ty == expr.FUN:
        if e.func_name == 'sqrt':
            return get_bounds(e.args[0], var_range).sqrt()
        elif e.func_name == 'exp':
            return get_bounds(e.args[0], var_range).exp()
        elif e.func_name == 'log':
            return get_bounds(e.args[0], var_range).log()
        elif e.func_name == 'sin':
            return get_bounds(e.args[0], var_range).sin()
        elif e.func_name == 'cos':
            return get_bounds(e.args[0], var_range).cos()
        else:
            raise NotImplementedError

    else:
        raise NotImplementedError

def convert_interval(t):
    """Convert HOL term to an interval."""
    if t.is_comb('real_closed_interval', 2):
        return Interval(expr.holpy_to_expr(t.arg1), expr.holpy_to_expr(t.arg), False, False)
    elif t.is_comb('real_open_interval', 2):
        return Interval(expr.holpy_to_expr(t.arg1), expr.holpy_to_expr(t.arg), True, True)
    else:
        raise NotImplementedError

def solve_with_interval(goal, cond):
    """Solving a goal with variable in a certain interval."""
    if not (hol_set.is_mem(cond) and cond.arg1.is_var() and 
            (cond.arg.is_comb("real_closed_interval", 2) or
             cond.arg.is_comb("real_open_interval", 2))):
        return False

    var = cond.arg1.name
    interval = convert_interval(cond.arg)
    if goal.is_greater_eq():
        lhs, rhs = expr.holpy_to_expr(goal.arg1), expr.holpy_to_expr(goal.arg)
        lhs_interval = get_bounds(lhs, {var: interval})
        rhs_interval = get_bounds(rhs, {var: interval})
        return lhs_interval.greater_eq(rhs_interval)
    elif goal.is_greater():
        lhs, rhs = expr.holpy_to_expr(goal.arg1), expr.holpy_to_expr(goal.arg)
        lhs_interval = get_bounds(lhs, {var: interval})
        rhs_interval = get_bounds(rhs, {var: interval})
        return lhs_interval.greater(rhs_interval)
    elif goal.is_less_eq():
        lhs, rhs = expr.holpy_to_expr(goal.arg1), expr.holpy_to_expr(goal.arg)
        lhs_interval = get_bounds(lhs, {var: interval})
        rhs_interval = get_bounds(rhs, {var: interval})
        return lhs_interval.less_eq(rhs_interval)
    elif goal.is_less():
        lhs, rhs = expr.holpy_to_expr(goal.arg1), expr.holpy_to_expr(goal.arg)
        lhs_interval = get_bounds(lhs, {var: interval})
        rhs_interval = get_bounds(rhs, {var: interval})
        return lhs_interval.less(rhs_interval)
    elif goal.is_not() and goal.arg.is_equals():
        lhs, rhs = expr.holpy_to_expr(goal.arg.arg1), expr.holpy_to_expr(goal.arg.arg)
        lhs_interval = get_bounds(lhs, {var: interval})
        rhs_interval = get_bounds(rhs, {var: interval})
        return lhs_interval.not_eq(rhs_interval)
    else:
        raise NotImplementedError

def is_closed_interval(t):
    return t.is_comb('real_closed_interval', 2)

def is_open_interval(t):
    return t.is_comb('real_open_interval', 2)

def is_lopen_interval(t):
    return t.is_comb('real_lopen_interval', 2)

def is_ropen_interval(t):
    return t.is_comb('real_ropen_interval', 2)

def is_mem_closed(pt):
    """Whether pt is membership in closed interval."""
    return is_closed_interval(pt.prop.arg)

def is_mem_open(pt):
    """Whether pt is membership in open interval."""
    return is_open_interval(pt.prop.arg)

def is_mem_lopen(pt):
    """Whether pt is membership in lopen interval."""
    return is_lopen_interval(pt.prop.arg)

def is_mem_ropen(pt):
    """Whether pt is membership in ropen interval."""
    return is_ropen_interval(pt.prop.arg)

def get_mem_bounds(pt):
    """Given pt is membership in an interval, return as Python numerals
    the two bounds in pt.

    """
    interval = pt.prop.arg
    return interval.arg1, interval.arg

def norm_mem_interval(pt):
    """Normalize membership in interval."""
    return pt.on_prop(arg_conv(binop_conv(auto.auto_conv())))

def real_pos(a):
    return real.greater(a, Real(0))

def real_nonneg(a):
    return real.greater_eq(a, Real(0))

def real_neg(a):
    return real.less(a, Real(0))

def real_nonpos(a):
    return real.less_eq(a, Real(0))

def get_mem_bounds_pt(pt):
    """Given pt is membership in an interval, return the left and right
    inequalities.

    """
    if is_mem_closed(pt):
        pt = pt.on_prop(rewr_conv('in_real_closed_interval'))
        return apply_theorem('conjD1', pt), apply_theorem('conjD2', pt)
    elif is_mem_open(pt):
        pt = pt.on_prop(rewr_conv('in_real_open_interval'))
        return apply_theorem('conjD1', pt), apply_theorem('conjD2', pt)
    elif is_mem_lopen(pt):
        pt = pt.on_prop(rewr_conv('in_real_lopen_interval'))
        return apply_theorem('conjD1', pt), apply_theorem('conjD2', pt)
    elif is_mem_ropen(pt):
        pt = pt.on_prop(rewr_conv('in_real_ropen_interval'))
        return apply_theorem('conjD1', pt), apply_theorem('conjD2', pt)
    else:
        raise NotImplementedError

@register_macro('const_inequality')
class ConstInequalityMacro(Macro):
    """Solve inequality between constants using real_eval and real_approx_eval."""
    def __init__(self):
        self.level = 0  # No expand implemented.
        self.sig = Term
        self.limit = None

    def can_eval(self, goal, prevs):
        if len(prevs) == 0:
            res = eval_inequality_expr(goal)
            return res
        else:
            return False

    def eval(self, goal, prevs):
        assert self.can_eval(goal, prevs), "const_inequality: not solved."
        return Thm([], goal)

class const_min_conv(Conv):
    """Evaluate min(a, b), where a and b are constants."""
    def get_proof_term(self, t):
        if eval_hol_expr(t.arg1) <= eval_hol_expr(t.arg):
            return apply_theorem('real_min_eq_left', auto.auto_solve(real.less_eq(t.arg1, t.arg)))
        else:
            return apply_theorem('real_min_eq_right', auto.auto_solve(real.greater(t.arg1, t.arg)))

class const_max_conv(Conv):
    """Evaluate max(a, b), where a and b are constants."""
    def get_proof_term(self, t):
        if eval_hol_expr(t.arg1) <= eval_hol_expr(t.arg):
            return apply_theorem('real_max_eq_right', auto.auto_solve(real.less_eq(t.arg1, t.arg)))
        else:
            return apply_theorem('real_max_eq_left', auto.auto_solve(real.greater(t.arg1, t.arg)))

def inequality_trans(pt1, pt2):
    """Given two inequalities of the form x </<= y and y </<= z, combine
    to form x </<= z.

    """
    if pt1.prop.is_less_eq() and pt2.prop.is_less_eq():
        return apply_theorem('real_le_trans', pt1, pt2)
    elif pt1.prop.is_less_eq() and pt2.prop.is_less():
        return apply_theorem('real_let_trans', pt1, pt2)
    elif pt1.prop.is_less() and pt2.prop.is_less_eq():
        return apply_theorem('real_lte_trans', pt1, pt2)
    elif pt1.prop.is_less() and pt2.prop.is_less():
        return apply_theorem('real_lt_trans', pt1, pt2)
    else:
        raise AssertionError("inequality_trans")

def combine_mem_bounds(pt1, pt2):
    """Given two inequalities of the form x </<= a and b </<= y, where
    a and b are constants, attempt to form the theorem x </<= y.

    """
    assert pt1.prop.is_less_eq() or pt1.prop.is_less(), "combine_mem_bounds"
    assert pt2.prop.is_less_eq() or pt2.prop.is_less(), "combine_mem_bounds"

    x, a = pt1.prop.args
    b, y = pt2.prop.args

    # First obtain the comparison between a and b
    if eval_hol_expr(a) < eval_hol_expr(b):
        pt_ab = ProofTerm('const_inequality', real.less(a, b))
    elif eval_hol_expr(a) <= eval_hol_expr(b):
        pt_ab = ProofTerm('const_inequality', real.less_eq(a, b))
    else:
        raise TacticException

    # Next, successively combine the inequalities
    pt = inequality_trans(inequality_trans(pt1, pt_ab), pt2)
    return pt

def combine_interval_bounds(pt1, pt2):
    """Given two membership in intervals pt1 and pt2, where interval in
    pt1 lies to the left of interval in pt2, return an inequality between
    the two terms.
    
    """
    _, pt_a = get_mem_bounds_pt(pt1)
    pt_b, _ = get_mem_bounds_pt(pt2)
    return combine_mem_bounds(pt_a, pt_b)

def reverse_inequality(pt):
    """Convert an inequality of the form x </<= y to y >/>= x, and vice versa."""
    if pt.prop.is_less_eq():
        return pt.on_prop(rewr_conv('real_geq_to_leq', sym=True))
    elif pt.prop.is_less():
        return pt.on_prop(rewr_conv('real_ge_to_le', sym=True))
    elif pt.prop.is_greater_eq():
        return pt.on_prop(rewr_conv('real_geq_to_leq'))
    elif pt.prop.is_greater():
        return pt.on_prop(rewr_conv('real_ge_to_le'))
    else:
        raise AssertionError('reverse_inequality')

def nat_as_even(n):
    """Obtain theorem of form even n."""
    assert n % 2 == 0, "nat_as_even: n is not even"
    eq_pt = auto.auto_solve(Eq(Nat(2) * Nat(n // 2), Nat(n)))
    pt = apply_theorem('even_double', inst=Inst(n=Nat(n//2)))
    return pt.on_prop(arg_conv(rewr_conv(eq_pt)))

def nat_as_odd(n):
    """Obtain theorem of form odd n."""
    assert n % 2 == 1, "nat_as_odd: n is not odd"
    eq_pt = auto.auto_solve(Eq(nat.Suc(Nat(2) * Nat(n // 2)), Nat(n)))
    pt = apply_theorem('odd_double', inst=Inst(n=Nat(n//2)))
    return pt.on_prop(arg_conv(rewr_conv(eq_pt)))

def interval_union_subset(t):
    """Given t of the form I1 Un I2, return a theorem of the form
    I1 Un I2 SUB I.

    """
    assert t.is_comb('union', 2), "interval_union_subset"

    I1, I2 = t.args
    a, b = I1.args
    c, d = I2.args
    if is_closed_interval(I1) and is_closed_interval(I2):
        pt = apply_theorem('closed_interval_union', inst=Inst(a=a, b=b, c=c, d=d))
        return pt.on_prop(arg_conv(then_conv(arg1_conv(const_min_conv()),
                                             arg_conv(const_max_conv()))))
    elif is_open_interval(I1) and is_ropen_interval(I2):
        if eval_hol_expr(c) <= eval_hol_expr(a):
            pt = apply_theorem(
                'open_ropen_interval_union1', auto.auto_solve(real.less_eq(c, a)), inst=Inst(b=b, d=d))
        else:
            pt = apply_theorem(
                'open_ropen_interval_union2', auto.auto_solve(real.less(a, c)), inst=Inst(b=b, d=d))
        return pt.on_prop(arg_conv(arg_conv(const_max_conv())))
    else:
        raise NotImplementedError

    return pt

def get_nat_power_bounds(pt, n):
    """Given theorem of the form t Mem I, obtain a theorem of
    the form t ^ n Mem J.

    """
    a, b = get_mem_bounds(pt)
    if not n.is_number():
        raise NotImplementedError
    if eval_hol_expr(a) >= 0 and is_mem_closed(pt):
        pt = apply_theorem(
            'nat_power_interval_pos_closed', auto.auto_solve(real_nonneg(a)), pt, inst=Inst(n=n))
    elif eval_hol_expr(a) >= 0 and is_mem_open(pt):
        pt = apply_theorem(
            'nat_power_interval_pos_open', auto.auto_solve(real_nonneg(a)), pt, inst=Inst(n=n))
    elif eval_hol_expr(a) >= 0 and is_mem_lopen(pt):
        pt = apply_theorem(
            'nat_power_interval_pos_lopen', auto.auto_solve(real_nonneg(a)), pt, inst=Inst(n=n))
    elif eval_hol_expr(a) >= 0 and is_mem_ropen(pt):
        pt = apply_theorem(
            'nat_power_interval_pos_ropen', auto.auto_solve(real_nonneg(a)), pt, inst=Inst(n=n))
    elif eval_hol_expr(b) <= 0 and is_mem_closed(pt):
        int_n = n.dest_number()
        if int_n % 2 == 0:
            even_pt = nat_as_even(int_n)
            pt = apply_theorem(
                'nat_power_interval_neg_even_closed', auto.auto_solve(real_nonpos(b)), even_pt, pt)
        else:
            odd_pt = nat_as_odd(int_n)
            pt = apply_theorem(
                'nat_power_interval_neg_odd_closed', auto.auto_solve(real_nonpos(b)), odd_pt, pt)            
    elif eval_hol_expr(b) <= 0 and is_mem_open(pt):
        int_n = n.dest_number()
        if int_n % 2 == 0:
            even_pt = nat_as_even(int_n)
            pt = apply_theorem(
                'nat_power_interval_neg_even_open', auto.auto_solve(real_nonpos(b)), even_pt, pt)
        else:
            odd_pt = nat_as_odd(int_n)
            pt = apply_theorem(
                'nat_power_interval_neg_odd_open', auto.auto_solve(real_nonpos(b)), odd_pt, pt)
    elif is_mem_closed(pt):
        # Closed interval containing 0
        t = pt.prop.arg1
        assm1 = hol_set.mk_mem(t, real.closed_interval(a, Real(0)))
        assm2 = hol_set.mk_mem(t, real.closed_interval(Real(0), b))
        pt1 = get_nat_power_bounds(ProofTerm.assume(assm1), n).implies_intr(assm1)
        pt2 = get_nat_power_bounds(ProofTerm.assume(assm2), n).implies_intr(assm2)
        x = Var('x', RealType)
        pt = apply_theorem(
            'split_interval_closed', auto.auto_solve(real.less_eq(a, Real(0))),
            auto.auto_solve(real.less_eq(Real(0), b)), pt1, pt2, pt, inst=Inst(x=t, f=Lambda(x, x ** n)))
        subset_pt = interval_union_subset(pt.prop.arg)
        pt = apply_theorem('subsetE', subset_pt, pt)
    elif is_mem_open(pt):
        # Open interval containing 0
        t = pt.prop.arg1
        assm1 = hol_set.mk_mem(t, real.open_interval(a, Real(0)))
        assm2 = hol_set.mk_mem(t, real.ropen_interval(Real(0), b))
        pt1 = get_nat_power_bounds(ProofTerm.assume(assm1), n).implies_intr(assm1)
        pt2 = get_nat_power_bounds(ProofTerm.assume(assm2), n).implies_intr(assm2)
        x = Var('x', RealType)
        pt = apply_theorem(
            'split_interval_open', auto.auto_solve(real.less_eq(a, Real(0))),
            auto.auto_solve(real.less_eq(Real(0), b)), pt1, pt2, pt, inst=Inst(x=t, f=Lambda(x, x ** n)))
        subset_pt = interval_union_subset(pt.prop.arg)
        pt = apply_theorem('subsetE', subset_pt, pt)
    else:
        raise NotImplementedError
    return norm_mem_interval(pt)

def get_bounds_proof(t, var_range):
    """Given a term t and a mapping from variables to intervals,
    return a theorem for t belonging to an interval.

    t - Term, a HOL expression.
    var_range - dict(str, Thm): mapping from variables x to theorems of
        the form x Mem [a, b] or x Mem (a, b).

    Returns a theorem of the form t Mem [a, b] or t Mem (a, b).

    """
    if t.ty == Term.VAR:
        assert t.name in var_range, "get_bounds_proof: variable %s not found" % t.name
        return var_range[t.name]

    elif t.is_number():
        return apply_theorem('const_interval', inst=Inst(x=t))
    
    elif t.is_plus():
        pt1 = get_bounds_proof(t.arg1, var_range)
        pt2 = get_bounds_proof(t.arg, var_range)
        if is_mem_closed(pt1) and is_mem_closed(pt2):
            pt = apply_theorem('add_interval_closed', pt1, pt2)
        elif is_mem_open(pt1) and is_mem_open(pt2):
            pt = apply_theorem('add_interval_open', pt1, pt2)
        elif is_mem_open(pt1) and is_mem_closed(pt2):
            pt = apply_theorem('add_interval_open_closed', pt1, pt2)
        elif is_mem_closed(pt1) and is_mem_open(pt2):
            pt = apply_theorem('add_interval_closed_open', pt1, pt2)
        elif is_mem_closed(pt1) and is_mem_lopen(pt2):
            pt = apply_theorem('add_interval_closed_lopen', pt1, pt2)
        elif is_mem_closed(pt1) and is_mem_ropen(pt2):
            pt = apply_theorem('add_interval_closed_ropen', pt1, pt2)
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.is_uminus():
        pt = get_bounds_proof(t.arg, var_range)
        if is_mem_closed(pt):
            pt = apply_theorem('neg_interval_closed', pt)
        elif is_mem_open(pt):
            pt = apply_theorem('neg_interval_open', pt)
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.is_minus():
        rewr_t = t.arg1 + (-t.arg)
        pt = get_bounds_proof(rewr_t, var_range)
        return pt.on_prop(arg1_conv(rewr_conv('real_minus_def', sym=True)))

    elif t.is_real_inverse():
        pt = get_bounds_proof(t.arg, var_range)
        a, b = get_mem_bounds(pt)
        if eval_hol_expr(a) > 0 and is_mem_closed(pt):
            pt = apply_theorem('inverse_interval_pos_closed', auto.auto_solve(real_pos(a)), pt)
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.is_times():
        if t.arg1.has_var():
            pt1 = get_bounds_proof(t.arg1, var_range)
            pt2 = get_bounds_proof(t.arg, var_range)
            a, b = get_mem_bounds(pt1)
            c, d = get_mem_bounds(pt2)
            if eval_hol_expr(a) >= 0 and eval_hol_expr(c) >= 0 and is_mem_open(pt1) and is_mem_open(pt2):
                pt = apply_theorem(
                    'mult_interval_pos_pos_open', auto.auto_solve(real_nonneg(a)),
                    auto.auto_solve(real_nonneg(c)), pt1, pt2)
            else:
                raise NotImplementedError('get_bounds: %s, %s' % (pt1, pt2))
        else:
            pt = get_bounds_proof(t.arg, var_range)
            a, b = get_mem_bounds(pt)
            c = t.arg1
            nc = eval_hol_expr(c)
            if nc >= 0 and is_mem_closed(pt):
                pt = apply_theorem(
                    'mult_interval_pos_closed', auto.auto_solve(real_nonneg(c)), pt)
            elif nc >= 0 and is_mem_open(pt):
                pt = apply_theorem(
                    'mult_interval_pos_open', auto.auto_solve(real_nonneg(c)), pt)
            elif nc >= 0 and is_mem_lopen(pt):
                pt = apply_theorem(
                    'mult_interval_pos_lopen', auto.auto_solve(real_nonneg(c)), pt)
            elif nc >= 0 and is_mem_ropen(pt):
                pt = apply_theorem(
                    'mult_interval_pos_ropen', auto.auto_solve(real_nonneg(c)), pt)
            elif nc < 0 and is_mem_closed(pt):
                pt = apply_theorem(
                    'mult_interval_neg_closed', auto.auto_solve(real_neg(c)), pt)
            elif nc < 0 and is_mem_open(pt):
                pt = apply_theorem(
                    'mult_interval_neg_open', auto.auto_solve(real_neg(c)), pt)
            elif nc < 0 and is_mem_lopen(pt):
                pt = apply_theorem(
                    'mult_interval_neg_lopen', auto.auto_solve(real_neg(c)), pt)
            elif nc < 0 and is_mem_ropen(pt):
                pt = apply_theorem(
                    'mult_interval_neg_ropen', auto.auto_solve(real_neg(c)), pt)
            else:
                raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.is_divides():
        rewr_t = t.arg1 * (real.inverse(t.arg))
        pt = get_bounds_proof(rewr_t, var_range)
        return pt.on_prop(arg1_conv(rewr_conv('real_divide_def', sym=True)))

    elif t.is_nat_power():
        pt = get_bounds_proof(t.arg1, var_range)
        if not t.arg.is_number():
            raise NotImplementedError
        return get_nat_power_bounds(pt, t.arg)

    elif t.is_real_power():
        pt = get_bounds_proof(t.arg1, var_range)
        a, b = get_mem_bounds(pt)
        if not t.arg.is_number():
            raise NotImplementedError
        p = t.arg.dest_number()
        if p >= 0 and eval_hol_expr(a) >= 0:
            nonneg_p = auto.auto_solve(real_nonneg(t.arg))
            nonneg_a = auto.auto_solve(real_nonneg(a))
            if is_mem_closed(pt):
                pt = apply_theorem(
                    'real_power_interval_pos_closed', nonneg_p, nonneg_a, pt)
            elif is_mem_open(pt):
                pt = apply_theorem(
                    'real_power_interval_pos_open', nonneg_p, nonneg_a, pt)
            else:
                raise NotImplementedError
        elif p < 0:
            neg_p = auto.auto_solve(real_neg(t.arg))
            if is_mem_closed(pt) and eval_hol_expr(a) > 0:
                pos_a = auto.auto_solve(real_pos(a))
                pt = apply_theorem(
                    'real_power_interval_neg_closed', neg_p, pos_a, pt)
            elif is_mem_open(pt):
                nonneg_a = auto.auto_solve(real_nonneg(a))
                pt = apply_theorem(
                    'real_power_interval_neg_open', neg_p, nonneg_a, pt)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.head == real.log:
        pt = get_bounds_proof(t.arg, var_range)
        a, b = get_mem_bounds(pt)
        if eval_hol_expr(a) > 0 and is_mem_closed(pt):
            pt = apply_theorem(
                'log_interval_closed', auto.auto_solve(real_pos(a)), pt)
        elif eval_hol_expr(a) >= 0 and is_mem_open(pt):
            pt = apply_theorem(
                'log_interval_open', auto.auto_solve(real_nonneg(a)), pt)
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.head == real.exp:
        pt = get_bounds_proof(t.arg, var_range)
        if is_mem_closed(pt):
            pt = apply_theorem('exp_interval_closed', pt)
        elif is_mem_open(pt):
            pt = apply_theorem('exp_interval_open', pt)
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.head == real.sin:
        pt = get_bounds_proof(t.arg, var_range)
        a, b = get_mem_bounds(pt)
        if eval_hol_expr(a) >= -math.pi/2 and eval_hol_expr(b) <= math.pi/2:
            if is_mem_closed(pt):
                pt = apply_theorem(
                    'sin_interval_main_closed', auto.auto_solve(real.greater_eq(a, -real.pi / 2)),
                    auto.auto_solve(real.less_eq(b, real.pi / 2)), pt)
            elif is_mem_open(pt):
                pt = apply_theorem(
                    'sin_interval_main_open', auto.auto_solve(real.greater_eq(a, -real.pi / 2)),
                    auto.auto_solve(real.less_eq(b, real.pi / 2)), pt)
            else:
                raise NotImplementedError
        elif eval_hol_expr(a) >= 0 and eval_hol_expr(b) <= math.pi:
            if is_mem_closed(pt):
                pt = apply_theorem(
                    'sin_interval_pos_closed', auto.auto_solve(real_nonneg(a)),
                    auto.solve(real.less_eq(b, real.pi)), pt)
            elif is_mem_open(pt):
                pt = apply_theorem(
                    'sin_interval_pos_open', auto.auto_solve(real_nonneg(a)),
                    auto.solve(real.less_eq(b, real.pi)), pt)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    elif t.head == real.cos:
        pt = get_bounds_proof(t.arg, var_range)
        a, b = get_mem_bounds(pt)
        if eval_hol_expr(a) >= 0 and eval_hol_expr(b) <= math.pi:
            if is_mem_closed(pt):
                pt = apply_theorem(
                    'cos_interval_main_closed', auto.auto_solve(real_nonneg(a)),
                    auto.auto_solve(real.less_eq(b, real.pi)), pt)
            elif is_mem_open(pt):
                pt = apply_theorem(
                    'cos_interval_main_open', auto.auto_solve(real_nonneg(a)),
                    auto.auto_solve(real.less_eq(b, real.pi)), pt)
            else:
                raise NotImplementedError
        elif eval_hol_expr(a) >= -math.pi/2 and eval_hol_expr(b) <= math.pi/2:
            if is_mem_closed(pt):
                pt = apply_theorem(
                    'cos_interval_pos_closed', auto.auto_solve(real.greater_eq(a, -real.pi / 2)),
                        auto.auto_solve(real.less_eq(b, real.pi / 2)), pt)
            elif is_mem_open(pt):
                pt = apply_theorem(
                    'cos_interval_pos_open', auto.auto_solve(real.greater_eq(a, -real.pi / 2)),
                        auto.auto_solve(real.less_eq(b, real.pi / 2)), pt)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError
        return norm_mem_interval(pt)

    else:
        raise NotImplementedError


@register_macro('interval_inequality')
class IntervalInequalityMacro(Macro):
    """Solve inequality with one constraint."""
    def __init__(self):
        self.level = 1
        self.sig = Term
        self.limit = None

    # def can_eval(self, goal, prevs):
    #     if len(prevs) == 1:
    #         # print(goal, ',', prevs[0].prop)
    #         res = solve_with_interval(goal, prevs[0].prop)
    #         # print(res)
    #         return res
    #     else:
    #         return False

    # def eval(self, goal, prevs):
    #     assert self.can_eval(goal, prevs), "interval_inequality: not solved."

    #     return Thm(sum([th.hyps for th in prevs], ()), goal)

    def get_proof_term(self, goal, pts):
        assert len(pts) == 1 and hol_set.is_mem(pts[0].prop) and pts[0].prop.arg1.is_var(), \
            "interval_inequality"
        var_name = pts[0].prop.arg1.name
        var_range = {var_name: pts[0]}

        if goal.is_not() and goal.arg.is_equals():
            pt1 = get_bounds_proof(goal.arg.arg1, var_range)
            pt2 = get_bounds_proof(goal.arg.arg, var_range)
            try:
                pt = combine_interval_bounds(pt1, pt2)
                if pt.prop.is_less_eq():
                    raise TacticException
                pt = apply_theorem('real_lt_neq', pt)
            except TacticException:
                pt = combine_interval_bounds(pt2, pt1)
                if pt.prop.is_less_eq():
                    raise TacticException
                pt = apply_theorem('real_gt_neq', reverse_inequality(pt))
            return pt
        else:
            pt1 = get_bounds_proof(goal.arg1, var_range)
            pt2 = get_bounds_proof(goal.arg, var_range)
            if goal.is_less_eq():
                pt = combine_interval_bounds(pt1, pt2)
                if pt.prop.is_less():
                    pt = apply_theorem('real_lt_imp_le', pt)
                return pt
            elif goal.is_less():
                pt = combine_interval_bounds(pt1, pt2)
                if pt.prop.is_less_eq():
                    raise TacticException
                return pt
            elif goal.is_greater_eq():
                pt = combine_interval_bounds(pt2, pt1)
                if pt.prop.is_less():
                    pt = apply_theorem('real_lt_imp_le', pt)
                return reverse_inequality(pt)
            elif goal.is_greater():
                pt = combine_interval_bounds(pt2, pt1)
                if pt.prop.is_less_eq():
                    raise TacticException
                return reverse_inequality(pt)
            else:
                raise AssertionError('interval_inequality')

def inequality_solve(goal, pts):
    if pts is None:
        pts = []

    if len(pts) == 0:
        macro = ConstInequalityMacro()
        if macro.can_eval(goal, pts):
            th = macro.eval(goal, pts)
            return ProofTerm('const_inequality', args=goal, prevs=pts, th=th)
        else:
            raise TacticException
    elif len(pts) == 1:
        macro = IntervalInequalityMacro()
        try:
            return macro.get_proof_term(goal, pts)
        except ConvException:
            raise TacticException
        else:
            raise TacticException
    else:
        raise TacticException


auto.add_global_autos(real.greater_eq, inequality_solve)
auto.add_global_autos(real.greater, inequality_solve)
auto.add_global_autos(real.less_eq, inequality_solve)
auto.add_global_autos(real.less, inequality_solve)

auto.add_global_autos_neg(real.equals, inequality_solve)

auto.add_global_autos(nat.greater_eq, inequality_solve)
auto.add_global_autos(nat.greater, inequality_solve)
auto.add_global_autos(nat.less_eq, inequality_solve)
auto.add_global_autos(nat.less, inequality_solve)

auto.add_global_autos_neg(nat.equals, inequality_solve)
