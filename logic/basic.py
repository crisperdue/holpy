# Author: Bohua Zhan

from kernel.term import Var, Term
from kernel.thm import Thm
from kernel.proof import Proof
from kernel.theory import Theory
from kernel.macro import ProofMacro

class OperatorData():
    """Represents information for operators.
    
    For each operator, we record its corresponding function, priority,
    and left/right associativity.
    
    """
    LEFT_ASSOC, RIGHT_ASSOC = range(2)

    def __init__(self):
        data = [
            ("=", "equals", 50, OperatorData.LEFT_ASSOC),
            ("-->", "implies", 25, OperatorData.RIGHT_ASSOC),
        ]

        self.op_dict = dict()
        self.fun_dict = dict()

        for op_str, fun_name, priority, assoc in data:
            self.op_dict[op_str] = (fun_name, priority, assoc)
            self.fun_dict[fun_name] = (op_str, priority, assoc)

    def get_info_for_op(self, op_str):
        """Returns (priority, fun_name) associated to an operator. The
        result is None if the operator is not found.
        
        """
        if op_str in self.op_dict:
            return self.op_dict[op_str]
        else:
            return None

    def get_info_for_fun(self, t):
        """Returns (priority, op_str) associated to a function term. The
        result is None if the function is not found.

        """
        if t.ty == Term.CONST and t.name in self.fun_dict:
            return self.fun_dict[t.name]
        else:
            return None


def arg_combination_eval(th, f):
    assert th.concl.is_equals(), "arg_combination"
    return Thm.combination(Thm.reflexive(f), th)

def arg_combination_expand(depth, ids, th, f):
    assert th.concl.is_equals(), "arg_combination"

    th1 = Thm.reflexive(f)
    th2 = Thm.combination(th1, th)
    prf = Proof()
    prf.add_item((depth, "S1"), th1, "reflexive", args = f)
    prf.add_item("C", th2, "combination", prevs = [(depth, "S1"), ids[0]])
    return prf

arg_combination_macro = ProofMacro(
    "Given theorem x = y and term f, return f x = f y.",
    arg_combination_eval,
    arg_combination_expand,
    level = 1
)

def fun_combination_eval(th, f):
    assert th.concl.is_equals(), "fun_combination"
    return Thm.combination(th, Thm.reflexive(f))

def fun_combination_expand(depth, ids, th, f):
    assert th.concl.is_equals(), "fun_combination"

    th1 = Thm.reflexive(f)
    th2 = Thm.combination(th, th1)
    prf = Proof()
    prf.add_item((depth, "S1"), th1, "reflexive", args = f)
    prf.add_item("C", th2, "combination", prevs = [ids[0], (depth, "S1")])
    return prf

fun_combination_macro = ProofMacro(
    "Given theorem f = g and term x, return f x = g x.",
    fun_combination_eval,
    fun_combination_expand,
    level = 1
)

def BasicTheory():
    thy = Theory.EmptyTheory()

    # Operators
    thy.add_data_type("operator", OperatorData())

    # Basic macros
    thy.add_proof_macro("arg_combination", arg_combination_macro)
    thy.add_proof_macro("fun_combination", fun_combination_macro)
    return thy
