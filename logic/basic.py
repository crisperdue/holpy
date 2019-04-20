# Author: Bohua Zhan

from copy import copy
import os
import inspect
import json

from kernel.theory import Theory
from logic.operator import OperatorTable
from logic import logic_macro  # Load all defined macros
from logic import expr
from logic import hoare
from syntax import parser


"""Global record of loaded theories."""
loaded_theories = dict()


def getInitTheory():
    """Returns a (fresh copy of) the initial theory. This is an
    extension of EmptyTheory, adding only the operator data field.

    """
    # The root theory
    thy = Theory.EmptyTheory()

    # Operators
    thy.add_data_type("operator", OperatorTable())

    return thy

def loadImportedTheory(imports, username):
    """Load imported theory according to the imports field in data."""
    if imports:
        # Has at least one import
        if len(imports) > 1:
            raise NotImplementedError

        return copy(loadTheory(imports[0], user = username))
    else:
        return getInitTheory()

def loadTheory(theory_name, *, limit=None, user=""):
    """Load the theory with the given theory name. Optional limit is
    a pair (ty, name) specifying the first item that should not
    be loaded.
    
    """
    # If the theory is already loaded, return the theory.
    if limit is None and theory_name in loaded_theories:
        return loaded_theories[theory_name]

    # Otherwise, open the corresponding file.
    if user == "":
        dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        with open(dir + '/../library/' + theory_name + '.json', encoding='utf-8') as a:
            data = json.load(a)
    else:
        with open('users/' + user + '/' + theory_name + '.json', encoding='utf-8') as a:
            data = json.load(a)

    content = data['content']
    limit_i = -1
    if limit:
        ty, name = limit
        for i, val in enumerate(content):
            if val['ty'] == ty and val['name'] == name:
                limit_i = i
                break
        assert limit_i != -1, "Limit not found"
        content = content[:limit_i]

    thy = loadImportedTheory(data['imports'], username = user)
    parser.parse_extensions(thy, content)

    if limit is None:
        loaded_theories[theory_name] = thy

    return thy
