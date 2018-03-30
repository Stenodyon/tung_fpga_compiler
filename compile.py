
import sys

try:
    from lark import Lark, Transformer
except ImportError:
    raise ImportError("This program requires the Lark library (pip install lark-parser)")

grammar = r'''start: module* (construction ("," construction)*)?

        module: "module" NAME "{" stmt* "}"

        ?stmt: passthrough | function | sync_function

        passthrough: lane "<->" lane ";"

        function: eq "->" lane ";"
        sync_function: eq "sync" "->" lane ";"

        eq: anding "~=" eq | anding
        anding: oring "&" anding | oring
        oring: atom "|" oring | atom
        noting: "~" eq
        ?atom: noting | lane | "(" eq ")"

        lane: LANE

        LANE: "w0" | "w1" | "e0" | "e1" | "n0" | "n1" | "s0" | "s1"

        NAME: ("_" | /\w/)+

        construction: NAME

        %import common.WORD
        %import common.WS
        %ignore WS
        '''

l = Lark(grammar, parser="earley")

opposites = {
        "e": "w",
        "w": "e",
        "n": "s",
        "s": "n"
        }

def get_other_lane(lane):
    return lane[0] + str(1 - int(lane[1]))

def get_opposite_lane(lane):
    return opposites[lane[0]] + lane[1]

def to_bin(bool):
    if bool:
        return "1"
    else:
        return "0"

class Expression():
    def __init__(self, lhs, rhs):
        self.lanes = []
        self.lhs = lhs
        self.rhs = rhs
        for i in lhs.lanes:
            self.add_input(i)
        for i in rhs.lanes:
            self.add_input(i)

    def add_input(self, input):
        if(input[0] == "s"):
            print("Error, no input on south side")
            sys.exit(-1)
        other_lane = get_other_lane(input)
        if other_lane in self.lanes:
            print("Error, cannot use %s when using %s" % (input, other_lane))
            sys.exit(-1)
        self.lanes.append(input)

class Or(Expression):
    def __init__(self, lhs, rhs):
        Expression.__init__(self, lhs, rhs)

    def eval(self, inputs):
        return self.lhs.eval(inputs) or self.rhs.eval(inputs)

    def __repr__(self):
        return "(" + self.lhs.__repr__() + " | " + self.rhs.__repr__() + ")"

class And(Expression):
    def __init__(self, lhs, rhs):
        Expression.__init__(self, lhs, rhs)

    def eval(self, inputs):
        return self.lhs.eval(inputs) and self.rhs.eval(inputs)

    def __repr__(self):
        return "(" + self.lhs.__repr__() + " & " + self.rhs.__repr__() + ")"

class Xor(Expression):
    def __init__(self, lhs, rhs):
        Expression.__init__(self, lhs, rhs)

    def eval(self, inputs):
        return self.lhs.eval(inputs) != self.rhs.eval(inputs)

    def __repr__(self):
        return "(" + self.lhs.__repr__() + " != " + self.rhs.__repr__() + ")"

lanes = { "w": 0, "n": 1, "e": 2 }

class Lane(Expression):
    def __init__(self, name):
        self.name = name
        self.lanes = [name]

    def eval(self, inputs):
        return inputs[lanes[self.name[0]]]

    def __repr__(self):
        return "lane %s" % self.name

class Not(Expression):
    def __init__(self, nested):
        self.nested = nested
        self.lanes = nested.lanes

    def eval(self, inputs):
        return not self.nested.eval(inputs)

    def __repr__(self):
        return "~" + self.nested.__repr__()

class Switch():
    def __init__(self, a, b):
        if get_opposite_lane(a.name) != b.name:
            print("Error, %s and %s are not connectible" % (a, b))
            sys.exit(-1)
        self.a = a
        self.b = b
        if a.name[0] == "e" or a.name[0] == "s":
            self.a, self.b = b, a

    def __repr__(self):
        return "%s <-> %s" % (self.a, self.b)

class NullFunc():
    def __init__(self):
        self.sync = False

    def get_truth_table(self):
        return "0" * 8

class Func():
    def __init__(self, expr, output, sync=False):
        if (output.name[0] != "s") and (output.name[0] != "e"):
            print("Error, cannot output on lane %s" % output.name)
            sys.exit(-1)
        self.expr = expr
        self.output = output
        self.sync = sync

    def get_truth_table(self):
        out = ""
        for A in [False, True]:
            for B in [False, True]:
                for C in [False, True]:
                    out += to_bin(self.expr.eval([C, B, A]))
        return out

    def __repr__(self):
        out = self.expr.__repr__() 
        if self.sync:
            out += " sync"
        out += " -> " + self.output.__repr__()
        return out

class Module():
    def __init__(self, name, funcs, switches):
        if len(funcs) > 2:
            print("Error, cannot perform more than 2 functions")
            sys.exit(-1)
        if len(funcs) == 2 and funcs[0].output.name[0] == funcs[1].output.name[0]:
            print("Error, cannot output both function on the same side")
            sys.exit(-1)
        prev_len = len(funcs)
        for i in range(len(funcs), 2):
            funcs.append(NullFunc())
        if prev_len > 0 and funcs[0].output.name[0] == "e":
            funcs[0], funcs[1] = funcs[1], funcs[0]
        all_lanes = []
        for func in funcs:
            for lane in func.expr.lanes:
                if get_opposite_lane(lane) in all_lanes:
                    print("Error, module %s has conflicting inputs")
                    sys.exit(-1)
                all_lanes.append(lane)
        self.name = name
        self.funcs = funcs
        self.switches = switches

    def async_flags(self):
        return to_bin(not self.funcs[1].sync) + to_bin(not self.funcs[1].sync)

    def has_switch(self, side):
        for switch in self.switches:
            if switch.a.name == side:
                return True
        return False

    def input_flags(self):
        out = ["0", "0", "0"]
        for func in self.funcs:
            for lane in func.expr.lanes:
                out[2 - lanes[lane[0]]] = lane[1]
        return "".join(out)

    def switch_flags(self):
        return "".join([to_bin(self.has_switch(flag)) for flag in ["w1", "w0", "n1", "n0"]])
    
    def output_flags(self):
        return "".join([
            to_bin(self.funcs[1].output.name == "e1"),
            to_bin(self.funcs[1].output.name == "e0"),
            to_bin(self.funcs[0].output.name == "s1"),
            to_bin(self.funcs[0].output.name == "s0"),
            ])

    def compile(self):
        input_flags = self.input_flags()
        return "\n".join([
            self.funcs[0].get_truth_table()[::-1],
            self.funcs[1].get_truth_table()[::-1],
            "%s%s%s" % (input_flags[1:],
                self.switch_flags(),
                self.async_flags()),
            "000%s%s" % (self.output_flags(), input_flags[0])])

    def __repr__(self):
        return "module %s {\n %s\n%s\n }" % (self.name,
                "\t\n".join(map(repr, self.funcs)),
                "\t\n".join(map(repr, self.switches)))

modules = {}

class Parser(Transformer):
    def lane(self, items):
        return Lane(items[0])

    def noting(self, items):
        return Not(items[0])

    def oring(self, items):
        if(len(items) == 2):
            return Or(items[0], items[1])
        else:
            return items[0]

    def anding(self, items):
        if(len(items) == 2):
            return And(items[0], items[1])
        else:
            return items[0]

    def eq(self, items):
        if(len(items) == 2):
            return Xor(items[0], items[1])
        else:
            return items[0]

    def passthrough(self, items):
        return Switch(items[0], items[1])

    def function(self, items):
        func = Func(items[0], items[1], False)
        return func

    def sync_function(self, items):
        func = Func(items[0], items[1], False)
        return func

    def construction(self, items):
        return "".join(items)

    def module(self, items):
        name = items[0]
        funcs = []
        switches = []
        for i in range(1, len(items)):
            item = items[i]
            if isinstance(item, Switch):
                switches.append(item)
            else:
                funcs.append(item)
        return Module(name, funcs, switches)

    def start(self, items):
        modules = []
        order = []
        for item in items:
            if isinstance(item, Module):
                modules.append(item)
            else:
                order.append(item)
        return (modules, order)

if __name__ == "__main__":
    if not len(sys.argv) == 2:
        print("Usage: python compile.py filename")
        exit(-1)
    filename = sys.argv[1]
    with open(filename, "r") as in_file:
        contents = in_file.read()

    tree = l.parse(contents)

#   tree = l.parse('''
#   module adder {
#       (w0 == n0) == e1 -> e0;
#       (w0 & n0) | (e1 & (n0 == w0)) -> s0;
#       w1 <-> e1;
#   }

#   adder
#   ''')
    modules, order = Parser().transform(tree)
    for module in modules:
        #print(module)
        print("Module %s:" % module.name)
        print(module.compile())
