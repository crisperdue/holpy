# Author: Bohua Zhan

from typing import Tuple, List
import copy
from lark import Lark, Transformer, v_args, exceptions

from kernel.type import HOLType, TVar, Type, TFun, boolT
from kernel.term import Var, Const, Comb, Abs, Bound, Term
from kernel import macro
from kernel import term
from kernel.thm import Thm
from kernel.proof import ProofItem, id_force_tuple
from kernel import extension
from logic import induct
from syntax import infertype


class ParserException(Exception):
    """Exceptions during parsing."""
    def __init__(self, str):
        self.str = str


grammar = r"""
    ?type: "'" CNAME  -> tvar              // Type variable
        | type ("=>"|"⇒") type -> funtype       // Function types
        | CNAME -> type                   // Type constants
        | type CNAME                      // Type constructor with one argument
        | "(" type ("," type)* ")" CNAME  // Type constructor with multiple arguments
        | "(" type ")"                    // Parenthesis

    ?atom: CNAME -> vname                 // Constant, variable, or bound variable
        | INT -> number                   // Numbers
        | ("%"|"λ") CNAME "::" type ". " term -> abs     // Abstraction
        | ("%"|"λ") CNAME ". " term           -> abs_notype
        | ("!"|"∀") CNAME "::" type ". " term -> all     // Forall quantification
        | ("!"|"∀") CNAME ". " term           -> all_notype
        | ("?"|"∃") CNAME "::" type ". " term -> exists  // Exists quantification
        | ("?"|"∃") CNAME ". " term           -> exists_notype
        | ("?!"|"∃!") CNAME "::" type ". " term -> exists1   // Exists unique
        | ("?!"|"∃!") CNAME ". " term         -> exists1_notype
        | "THE" CNAME "::" type ". " term -> the         // THE operator
        | "THE" CNAME ". " term -> the_notype
        | "[]"                     -> literal_list  // Empty list
        | "[" term ("," term)* "]" -> literal_list  // List
        | ("{}"|"∅")               -> literal_set   // Empty set
        | "{" term ("," term)* "}" -> literal_set   // Set
        | "{" CNAME "::" type "." term "}" -> collect_set
        | "{" CNAME ". " term "}"          -> collect_set_notype
        | "if" term "then" term "else" term  -> if_expr // if expression
        | "(" term ")(" term ":=" term ("," term ":=" term)* ")"   -> fun_upd // function update
        | "{" term ".." term "}"   -> nat_interval
        | "(" term ")"                    // Parenthesis
        | "(" term "::" type ")"   -> typed_term    // Term with specified type

    ?comb: comb atom | atom

    ?big_inter: ("INT"|"⋂") big_inter -> big_inter | comb         // Intersection: priority 90

    ?big_union: ("UN"|"⋃") big_union -> big_union | big_inter     // Union: priority 90

    ?power: power "^" big_union | big_union   // Power: priority 81

    ?uminus: "-" uminus -> uminus | power   // Unary minus: priority 80

    ?times: times "*" uminus | uminus        // Multiplication: priority 70

    ?real_divide: real_divide "/" times | times        // Division: priority 70

    ?nat_divide: nat_divide "DIV" real_divide | real_divide        // Division: priority 70

    ?nat_modulus: nat_modulus "MOD" nat_divide | nat_divide        // Modulus: priority 70

    ?inter: inter ("Int"|"∩") nat_modulus | nat_modulus     // Intersection: priority 70

    ?plus: plus "+" inter | inter       // Addition: priority 65

    ?minus: minus "-" plus | plus       // Subtraction: priority 65

    ?append: minus "@" append | minus     // Append: priority 65

    ?cons: append "#" cons | append     // Cons: priority 65

    ?union: union ("Un"|"∪") cons | cons        // Union: priority 65

    ?comp_fun: union ("O"|"∘") comp_fun | union // Function composition: priority 60

    ?eq: eq "=" comp_fun | comp_fun             // Equality: priority 50

    ?mem: mem ("Mem"|"∈") mem | eq              // Membership: priority 50

    ?subset: subset ("Sub"|"⊆") subset | mem    // Subset: priority 50

    ?less_eq: less_eq ("<="|"≤") less_eq | subset  // Less-equal: priority 50

    ?less: less "<" less | less_eq      // Less: priority 50

    ?greater_eq: greater_eq (">="|"≥") greater_eq | less   // greater-equal: priority 50

    ?greater: greater ">" greater | greater_eq     // greater: priority 50

    ?neg: ("~"|"¬") neg -> neg | greater   // Negation: priority 40

    ?conj: neg ("&"|"∧") conj | neg     // Conjunction: priority 35

    ?disj: conj ("|"|"∨") disj | conj   // Disjunction: priority 30

    ?imp: disj ("-->"|"⟶") imp | disj  // Implies: priority 25

    ?iff: imp ("<-->"|"⟷") iff | imp   // Iff: priority 25

    ?term: iff

    thm: ("|-"|"⊢") term
        | term ("," term)* ("|-"|"⊢") term

    term_pair: CNAME ":" term

    inst: "{}"
        | "{" term_pair ("," term_pair)* "}"

    type_pair: CNAME ":" type

    tyinst: "{}"
        | "{" type_pair ("," type_pair)* "}"

    instsp: tyinst "," inst
    
    var_decl: CNAME "::" type  // variable declaration

    ind_constr: CNAME ("(" CNAME "::" type ")")*  // constructor for inductive types

    named_thm: CNAME ":" term | term  // named theorem

    term_list: term ("," term)*   // list of terms

    %import common.CNAME
    %import common.WS
    %import common.INT

    %ignore WS
"""

# Modifiable settings in the transformation part of the parser.
# This includes thy and ctxt.
parser_setting = dict()

@v_args(inline=True)
class HOLTransformer(Transformer):
    def __init__(self):
        pass

    def tvar(self, s):
        return TVar(s)

    def type(self, *args):
        return Type(str(args[-1]), *args[:-1])

    def funtype(self, t1, t2):
        return TFun(t1, t2)

    def vname(self, s):
        thy = parser_setting['thy']
        ctxt = parser_setting['ctxt']
        s = str(s)
        if thy.has_term_sig(s) or ('consts' in ctxt and s in ctxt['consts']):
            # s is the name of a constant in the theory
            return Const(s, None)
        else:
            # s not found, either bound or free variable
            return Var(s, None)

    def typed_term(self, t, T):
        from data import nat
        if t.is_comb() and t.fun.is_const_name("of_nat") and \
           nat.is_binary(t.arg) and nat.from_binary(t.arg) >= 2:
            t.fun.T = TFun(nat.natT, T)
        else:
            t.T = T
        return t

    def number(self, n):
        from data import nat
        if int(n) == 0:
            return Const("zero", None)
        elif int(n) == 1:
            return Const("one", None)
        else:
            return Const("of_nat", None)(nat.to_binary(int(n)))

    def literal_list(self, *args):
        from data import list
        return list.mk_literal_list(args, None)

    def if_expr(self, P, x, y):
        return Const("IF", None)(P, x, y)

    def fun_upd(self, *args):
        def helper(*args):
            if len(args) == 3:
                f, a, b = args
                return Const("fun_upd", None)(f, a, b)
            elif len(args) > 3:
                return helper(helper(*args[:3]), *args[3:])
            else:
                raise TypeError
        return helper(*args)

    def comb(self, fun, arg):
        return Comb(fun, arg)

    def abs(self, var_name, T, body):
        return Abs(str(var_name), T, body.abstract_over(Var(var_name, None)))

    def abs_notype(self, var_name, body):
        return Abs(str(var_name), None, body.abstract_over(Var(var_name, None)))

    def all(self, var_name, T, body):
        all_t = Const("all", None)
        return all_t(Abs(str(var_name), T, body.abstract_over(Var(var_name, None))))

    def all_notype(self, var_name, body):
        all_t = Const("all", None)
        return all_t(Abs(str(var_name), None, body.abstract_over(Var(var_name, None))))

    def exists(self, var_name, T, body):
        exists_t = Const("exists", None)
        return exists_t(Abs(str(var_name), T, body.abstract_over(Var(var_name, None))))

    def exists_notype(self, var_name, body):
        exists_t = Const("exists", None)
        return exists_t(Abs(str(var_name), None, body.abstract_over(Var(var_name, None))))

    def exists1(self, var_name, T, body):
        exists1_t = Const("exists1", None)
        return exists1_t(Abs(str(var_name), T, body.abstract_over(Var(var_name, None))))

    def exists1_notype(self, var_name, body):
        exists1_t = Const("exists1", None)
        return exists1_t(Abs(str(var_name), None, body.abstract_over(Var(var_name, None))))

    def the(self, var_name, T, body):
        the_t = Const("The", None)
        return the_t(Abs(str(var_name), T, body.abstract_over(Var(var_name, None))))

    def the_notype(self, var_name, body):
        the_t = Const("The", None)
        return the_t(Abs(str(var_name), None, body.abstract_over(Var(var_name, None))))

    def collect_set(self, var_name, T, body):
        from data import set
        return set.collect(T)(Abs(str(var_name), T, body.abstract_over(Var(var_name, None))))

    def collect_set_notype(self, var_name, body):
        from data import set
        return set.collect(None)(Abs(str(var_name), None, body.abstract_over(Var(var_name, None))))

    def power(self, lhs, rhs):
        return Const("power", None)(lhs, rhs)

    def times(self, lhs, rhs):
        return Const("times", None)(lhs, rhs)

    def real_divide(self, lhs, rhs):
        return Const("real_divide", None)(lhs, rhs)

    def nat_divide(self, lhs, rhs):
        return Const("nat_divide", None)(lhs, rhs)

    def nat_modulus(self, lhs, rhs):
        return Const("nat_modulus", None)(lhs, rhs)

    def plus(self, lhs, rhs):
        return Const("plus", None)(lhs, rhs)

    def minus(self, lhs, rhs):
        return Const("minus", None)(lhs, rhs)

    def uminus(self, x):
        return Const("uminus", None)(x)

    def less_eq(self, lhs, rhs):
        return Const("less_eq", None)(lhs, rhs)

    def less(self, lhs, rhs):
        return Const("less", None)(lhs, rhs)

    def greater_eq(self, lhs, rhs):
        return Const("greater_eq", None)(lhs, rhs)

    def greater(self, lhs, rhs):
        return Const("greater", None)(lhs, rhs)

    def append(self, lhs, rhs):
        return Const("append", None)(lhs, rhs)

    def cons(self, lhs, rhs):
        return Const("cons", None)(lhs, rhs)

    def eq(self, lhs, rhs):
        return Const("equals", None)(lhs, rhs)

    def neg(self, t):
        from logic import logic
        return logic.neg(t)

    def conj(self, s, t):
        from logic import logic
        return logic.mk_conj(s, t)

    def disj(self, s, t):
        from logic import logic
        return logic.mk_disj(s, t)

    def imp(self, s, t):
        return Term.mk_implies(s, t)

    def iff(self, s, t):
        return Const("equals", None)(s, t)

    def literal_set(self, *args):
        from data import set
        return set.mk_literal_set(args, None)

    def mem(self, x, A):
        return Const("member", None)(x, A)

    def subset(self, A, B):
        return Const("subset", None)(A, B)

    def inter(self, A, B):
        return Const("inter", None)(A, B)

    def union(self, A, B):
        return Const("union", None)(A, B)

    def big_inter(self, t):
        return Const("Inter", None)(t)

    def big_union(self, t):
        return Const("Union", None)(t)

    def comp_fun(self, f, g):
        return Const("comp_fun", None)(f, g)

    def nat_interval(self, m, n):
        from data import interval
        return interval.mk_interval(m, n)

    def thm(self, *args):
        return Thm(args[:-1], args[-1])

    def term_pair(self, name, T):
        return (str(name), T)

    def type_pair(self, name, T):
        return (str(name), T)

    def inst(self, *args):
        return dict(args)

    def tyinst(self, *args):
        return dict(args)

    def instsp(self, *args):
        return tuple(args)

    def ind_constr(self, *args):
        constrs = {}
        constrs['name'] = str(args[0])
        constrs['args'] = []
        constrs['type'] = []
        for id in range(1, len(args), 2):
            constrs['args'].append(str(args[id]))
            constrs['type'].append(args[id+1])
        return constrs

    def var_decl(self, name, T):
        return (str(name), T)

    def named_thm(self, *args):
        return tuple(args)

    def term_list(self, *args):
        return list(args)


def get_parser_for(start):
    return Lark(grammar, start=start, parser="lalr", transformer=HOLTransformer())

type_parser = get_parser_for("type")
term_parser = get_parser_for("term")
thm_parser = get_parser_for("thm")
inst_parser = get_parser_for("inst")
tyinst_parser = get_parser_for("tyinst")
named_thm_parser = get_parser_for("named_thm")
instsp_parser = get_parser_for("instsp")
var_decl_parser = get_parser_for("var_decl")
ind_constr_parser = get_parser_for("ind_constr")
term_list_parser = get_parser_for("term_list")

def parse_type(thy, s):
    """Parse a type."""
    parser_setting['thy'] = thy
    return type_parser.parse(s)

def parse_term(thy, ctxt, s):
    """Parse a term."""
    parser_setting['thy'] = thy
    parser_setting['ctxt'] = ctxt
    # Permit parsing a list of strings by concatenating them.
    if isinstance(s, list):
        s = " ".join(s)
    try:
        t = term_parser.parse(s)
        return infertype.type_infer(thy, ctxt, t)
    except (term.OpenTermException, exceptions.UnexpectedToken, exceptions.UnexpectedCharacters, infertype.TypeInferenceException) as e:
        print("When parsing:", s)
        raise e

def parse_thm(thy, ctxt, s):
    """Parse a theorem (sequent)."""
    parser_setting['thy'] = thy
    parser_setting['ctxt'] = ctxt
    th = thm_parser.parse(s)
    th.hyps = tuple(infertype.type_infer(thy, ctxt, hyp) for hyp in th.hyps)
    th.prop = infertype.type_infer(thy, ctxt, th.prop)
    return th

def parse_inst(thy, ctxt, s):
    """Parse a term instantiation."""
    parser_setting['thy'] = thy
    parser_setting['ctxt'] = ctxt
    inst = inst_parser.parse(s)
    for k in inst:
        inst[k] = infertype.type_infer(thy, ctxt, inst[k])
    return inst

def parse_tyinst(thy, s):
    """Parse a type instantiation."""
    parser_setting['thy'] = thy
    return tyinst_parser.parse(s)

def parse_named_thm(thy, ctxt, s):
    """Parse a named theorem."""
    res = named_thm_parser.parse(s)
    if len(res) == 1:
        return (None, infertype.type_infer(thy, ctxt, res[0]))
    else:
        return (str(res[0]), infertype.type_infer(thy, ctxt, res[1]))

def parse_instsp(thy, ctxt, s):
    """Parse type and term instantiations."""
    parser_setting['thy'] = thy
    parser_setting['ctxt'] = ctxt
    tyinst, inst = instsp_parser.parse(s)
    for k in inst:
        inst[k] = infertype.type_infer(thy, ctxt, inst[k])
    return tyinst, inst

def parse_ind_constr(thy, s):
    """Parse a constructor for an inductive type definition."""
    parser_setting['thy'] = thy
    return ind_constr_parser.parse(s)

def parse_var_decl(thy, s):
    """Parse a variable declaration."""
    parser_setting['thy'] = thy
    return var_decl_parser.parse(s)

def parse_term_list(thy, ctxt, s):
    """Parse a list of terms."""
    if s == "":
        return []
    parser_setting['thy'] = thy
    parser_setting['ctxt'] = ctxt
    ts = term_list_parser.parse(s)
    for i in range(len(ts)):
        ts[i] = infertype.type_infer(thy, ctxt, ts[i])
    return ts

def parse_args(thy, ctxt, sig, args):
    """Parse the argument according to the signature."""
    try:
        if sig == None:
            assert args == "", "rule expects no argument."
            return None
        elif sig == str:
            return args
        elif sig == Term:
            return parse_term(thy, ctxt, args)
        elif sig == macro.Inst:
            return parse_inst(thy, ctxt, args)
        elif sig == macro.TyInst:
            return parse_tyinst(thy, args)
        elif sig == Tuple[str, HOLType]:
            s1, s2 = args.split(",", 1)
            return s1, parse_type(thy, s2)
        elif sig == Tuple[str, Term]:
            s1, s2 = args.split(",", 1)
            return s1, parse_term(thy, ctxt, s2)
        elif sig == Tuple[str, macro.TyInst, macro.Inst]:
            s1, s2 = args.split(",", 1)
            tyinst, inst = parse_instsp(thy, ctxt, s2)
            return s1, tyinst, inst
        elif sig == List[Term]:
            return parse_term_list(thy, ctxt, args)
        else:
            raise TypeError
    except exceptions.UnexpectedToken as e:
        raise ParserException("When parsing %s, unexpected token %r at column %s.\n"
                              % (args, e.token, e.column))

def parse_proof_rule(thy, ctxt, data):
    """Parse a proof rule.

    data is a dictionary containing id, rule, args, prevs, and th.
    The result is a ProofItem object.

    This need to be written by hand because different proof rules
    require different parsing of the arguments.

    """
    id, rule = data['id'], data['rule']

    if rule == "":
        return ProofItem(id, "")

    if data['th'] == "":
        th = None
    else:
        th = parse_thm(thy, ctxt, data['th'])

    sig = thy.get_proof_rule_sig(rule)
    args = parse_args(thy, ctxt, sig, data['args'])
    return ProofItem(id, rule, args=args, prevs=data['prevs'], th=th)

def parse_vars(thy, vars_data):
    ctxt = {'vars': {}}
    for k, v in vars_data.items():
        ctxt['vars'][k] = parse_type(thy, v)
    return ctxt

def parse_item(thy, data):
    """Parse the string elements in the item, replacing it by
    objects of the appropriate type (HOLType, Term, etc).
    
    """
    data = copy.deepcopy(data)  # Avoid modifying input

    if data['ty'] == 'def.ax':
        data['type'] = parse_type(thy, data['type'])

    elif data['ty'] == 'def':
        data['type'] = parse_type(thy, data['type'])
        ctxt = {'vars': {}, 'consts': {data['name']: data['type']}}
        data['prop'] = parse_term(thy, ctxt, data['prop'])

    elif data['ty'] in ('thm', 'thm.ax'):
        ctxt = parse_vars(thy, data['vars'])
        for nm in data['vars']:
            data['vars'][nm] = parse_type(thy, data['vars'][nm])
        data['prop'] = parse_term(thy, ctxt, data['prop'])
        prop_vars = set(v.name for v in term.get_vars(data['prop']))
        assert prop_vars.issubset(set(data['vars'].keys())), \
            "parse_item on %s: extra variables in prop: %s" % (
                data['name'], ", ".join(v for v in prop_vars - set(data['vars'].keys())))

    elif data['ty'] == 'type.ind':
        for constr in data['constrs']:
            constr['type'] = parse_type(thy, constr['type'])

    elif data['ty'] in ('def.ind', 'def.pred'):
        data['type'] = parse_type(thy, data['type'])
        for rule in data['rules']:
            ctxt = {'vars': {}, 'consts': {data['name']: data['type']}}
            rule['prop'] = parse_term(thy, ctxt, rule['prop'])

    else:
        pass

    return data

def get_extension(thy, data):
    """Given a parsed item, return the resulting extension."""

    ext = extension.TheoryExtension()

    if data['ty'] == 'type.ax':
        ext.add_extension(extension.AxType(data['name'], len(data['args'])))

    elif data['ty'] == 'def.ax':
        ext.add_extension(extension.AxConstant(data['name'], data['type']))
        if 'overloaded' in data:
            ext.add_extension(extension.Overload(data['name']))

    elif data['ty'] == 'def':
        ext.add_extension(extension.AxConstant(data['name'], data['type']))

        cname = thy.get_overload_const_name(data['name'], data['type'])
        ext.add_extension(extension.Theorem(cname + "_def", Thm([], data['prop'])))
        if 'attributes' in data:
            for attr in data['attributes']:
                ext.add_extension(extension.Attribute(cname + "_def", attr))

    elif data['ty'] == 'thm' or data['ty'] == 'thm.ax':
        ext.add_extension(extension.Theorem(data['name'], Thm([], data['prop'])))
        if 'attributes' in data:
            for attr in data['attributes']:
                ext.add_extension(extension.Attribute(data['name'], attr))

    elif data['ty'] == 'type.ind':
        constrs = []
        for constr in data['constrs']:
            constrs.append((constr['name'], constr['type'], constr['args']))
        ext = induct.add_induct_type(data['name'], data['args'], constrs)

    elif data['ty'] == 'def.ind':
        rules = []
        for rule in data['rules']:
            rules.append(rule['prop'])
        ext = induct.add_induct_def(thy, data['name'], data['type'], rules)

    elif data['ty'] == 'def.pred':
        rules = []
        for rule in data['rules']:
            rules.append((rule['name'], rule['prop']))
        ext = induct.add_induct_predicate(thy, data['name'], data['type'], rules)

    elif data['ty'] == 'macro':
        ext = extension.TheoryExtension()
        ext.add_extension(extension.Macro(data['name']))

    elif data['ty'] == 'method':
        ext = extension.TheoryExtension()
        ext.add_extension(extension.Method(data['name']))

    return ext

def parse_extensions(thy, data):
    """Parse a list of extensions to thy in sequence."""
    for item in data:
        try:
            item = parse_item(thy, item)
            ext = get_extension(thy, item)
            thy.unchecked_extend(ext)
        except Exception:
            pass
