# Author: Bohua Zhan

from kernel.type import Type, TFun
from kernel.term import Term, Const

"""Utility functions for natural number arithmetic."""

natT = Type("nat")
zero = Const("zero", natT)
Suc = Const("Suc", TFun(natT, natT))
one = Suc(zero)
plus = Const("plus", TFun(natT, natT, natT))
times = Const("times", TFun(natT, natT, natT))

def mk_plus(*args):
    if not args:
        return zero
    elif len(args) == 1:
        return args[0]
    else:
        return plus(mk_plus(*args[:-1]), args[-1])

def mk_times(*args):
    if not args:
        return one
    elif len(args) == 1:
        return args[0]
    else:
        return times(mk_times(*args[:-1]), args[-1])

bit0 = Const("bit0", TFun(natT, natT))
bit1 = Const("bit1", TFun(natT, natT))
    
def to_binary(n):
    """Convert integer n to binary form."""
    if n == 0:
        return zero
    elif n == 1:
        return one
    elif n % 2 == 0:
        return bit0(to_binary(n // 2))
    else:
        return bit1(to_binary(n // 2))

def is_binary(t):
    """Whether the term t is in standard binary form."""
    head = t.get_head()
    if t == zero or t == one:
        return True
    elif t.ty != Term.COMB:
        return False
    elif head == bit0 or head == bit1:
        return is_binary(t.arg)
    else:
        return False

def from_binary(t):
    """Convert binary form to integer."""
    head = t.get_head()
    if head == zero:
        return 0
    elif head == one:
        return 1
    elif head == bit0:
        return 2 * from_binary(t.arg)
    else:
        return 2 * from_binary(t.arg) + 1
