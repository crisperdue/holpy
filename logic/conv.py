# Author: Bohua Zhan

import abc

from kernel.term import *
from kernel.thm import *
from logic.proofterm import *

class ConvException(Exception):
    pass

class Conv(abc.ABC):
    """A conversion is a function for rewriting a term.

    A Conv object has two main methods:
    eval - function to obtain the equality from the term.
    get_proof_term - function to obtain the proof term for the equality.

    """
    @abc.abstractmethod
    def eval(self, t):
        pass

    @abc.abstractmethod
    def get_proof_term(self, t):
        pass

class all_conv(Conv):
    """Returns the trivial equality t = t."""
    def eval(self, t):
        return Thm.reflexive(t)

    def get_proof_term(self, t):
        return ProofTerm.reflexive(t)

class no_conv(Conv):
    """Always fails."""
    def eval(self, t):
        raise ConvException()

    def get_proof_term(self, t):
        raise ConvException()

class combination_conv(Conv):
    """Apply cv1 to the function and cv2 to the argument."""
    def __init__(self, cv1, cv2):
        assert isinstance(cv1, Conv) and isinstance(cv2, Conv), "combination_conv: argument"
        self.cv1 = cv1
        self.cv2 = cv2

    def eval(self, t):
        if t.ty != Term.COMB:
            raise ConvException()
        return Thm.combination(self.cv1.eval(t.fun), self.cv2.eval(t.arg))

    def get_proof_term(self, t):
        if t.ty != Term.COMB:
            raise ConvException()
        return ProofTerm.combination(self.cv1.get_proof_term(t.fun), self.cv2.get_proof_term(t.arg))

class then_conv(Conv):
    """Applies cv1, followed by cv2."""
    def __init__(self, cv1, cv2):
        assert isinstance(cv1, Conv) and isinstance(cv2, Conv), "then_conv: argument"
        self.cv1 = cv1
        self.cv2 = cv2

    def eval(self, t):
        th1 = self.cv1.eval(t)
        (_, t2) = th1.concl.dest_binop()
        th2 = self.cv2.eval(t2)
        return Thm.transitive(th1, th2)

    def get_proof_term(self, t):
        pt1 = self.cv1.get_proof_term(t)
        (_, t2) = pt1.th.concl.dest_binop()
        pt2 = self.cv2.get_proof_term(t2)
        
        # Obtain some savings if one of pt1 and pt2 is reflexivity:
        (_, t3) = pt2.th.concl.dest_binop()
        if t == t2:
            return pt2
        elif t2 == t3:
            return pt1
        else:
            return ProofTerm.transitive(pt1, pt2)

class else_conv(Conv):
    """Applies cv1, if fails, apply cv2."""
    def __init__(self, cv1, cv2):
        assert isinstance(cv1, Conv) and isinstance(cv2, Conv), "else_conv: argument"
        self.cv1 = cv1
        self.cv2 = cv2

    def eval(self, t):
        try:
            return self.cv1.eval(t)
        except ConvException:
            return self.cv2.eval(t)

    def get_proof_term(self, t):
        try:
            return self.cv1.get_proof_term(t)
        except ConvException:
            return self.cv2.get_proof_term(t)

class beta_conv(Conv):
    """Applies beta-conversion."""
    def eval(self, t):
        try:
            return Thm.beta_conv(t)
        except InvalidDerivationException:
            raise ConvException()

    def get_proof_term(self, t):
        try:
            return ProofTerm.beta_conv(t)
        except InvalidDerivationException:
            raise ConvException()

def try_conv(cv):
    return else_conv(cv, all_conv())

def comb_conv(cv):
    return combination_conv(cv, cv)

def arg_conv(cv):
    return combination_conv(all_conv(), cv)

def fun_conv(cv):
    return combination_conv(cv, all_conv())

def arg1_conv(cv):
    return fun_conv(arg_conv(cv))

def fun2_conv(cv):
    return fun_conv(fun_conv(cv))

def binop_conv(cv):
    return combination_conv(arg_conv(cv), cv)

def sub_conv(cv):
    return try_conv(comb_conv(cv))

class bottom_conv(Conv):
    """Applies cv repeatedly in the bottom-up manner."""
    def __init__(self, cv):
        assert isinstance(cv, Conv), "bottom_conv: argument"
        self.cv = cv

    def eval(self, t):
        return then_conv(sub_conv(self), try_conv(self.cv)).eval(t)

    def get_proof_term(self, t):
        return then_conv(sub_conv(self), try_conv(self.cv)).get_proof_term(t)

class top_conv(Conv):
    """Applies cv repeatedly in the top-down manner."""
    def __init__(self, cv):
        assert isinstance(cv, Conv), "top_conv: argument"
        self.cv = cv

    def eval(self, t):
        return then_conv(try_conv(self.cv), sub_conv(self)).eval(t)

    def get_proof_term(self, t):
        return then_conv(try_conv(self.cv), sub_conv(self)).get_proof_term(t)

class rewr_conv(Conv):
    """Rewrite using the given equality theorem. Currently perform
    no matching.

    """
    def __init__(self, th_name, th):
        assert isinstance(th, Thm), "rewr_conv: argument"
        self.th = th
        self.th_name = th_name

    def eval(self, t):
        if t == self.th.concl.dest_binop()[0]:
            return self.th
        else:
            raise ConvException()

    def get_proof_term(self, t):
        if t == self.th.concl.dest_binop()[0]:
            return ProofTerm.theorem(self.th_name, self.th)
        else:
            raise ConvException()

