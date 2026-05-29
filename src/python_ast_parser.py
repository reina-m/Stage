import ast


class Python_AST_Parser(ast.NodeVisitor):
    # inherits from ast.NodeVisitor (see documentation :)
    # class meant to be subclassed with the subclass adding visitor methods 
    """
    Minimal parser for one Python notebook code cell.

    """

    def __init__(self, code):
        self.code = code
        self.imports = []
        self.defines = []
        self.callable_defines = []
        self.uses = []
        self.calls = []
        
        # maps function names to list of external uses 
        self.function_uses = {}
        self.syntax_error = None

    def analyse(self):
        try:
            # ast.parse could return SyntaxError
            tree = ast.parse(self.code)
        except SyntaxError as error:
            self.syntax_error = error
            return
        # calls the method called self.visit_classname 
        # where classname is the name of the node class
        self.visit(tree)

    # GETTERS
    def get_imports(self):
        return self.imports

    def get_defines(self):
        return self.defines

    def get_callable_defines(self):
        return self.callable_defines

    def get_uses(self):
        return self.uses

    def get_calls(self):
        return self.calls

    def get_function_uses(self):
        return self.function_uses

    def get_syntax_error(self):
        return self.syntax_error

    # VISITOR METHODS

    # stmt

    def visit_Import(self, node):
        # Import(alias* names)
        for alias in node.names:
            # e.g. import pandas adds pandas to imports
            self.add_import(alias.name)

    def visit_ImportFrom(self, node):
        # ImportFrom(identifier? module, alias* names, int? level)
        module = node.module or ""
        for alias in node.names:
            # e. g.: from Bio import SeqIO adds Bio.SeqIO to imports
            if module != "":
                self.add_import(f"{module}.{alias.name}")
            else:
                self.add_import(alias.name)

    def visit_Assign(self, node):
        # Assign(expr* targets, expr value, string? type_comment)
        for tgt in node.targets:
            # e.g. b = a + 1 adds b to defines
            self.add_target_defines(tgt)
        # then visits a + 1
        self.visit(node.value)
    
    def visit_AugAssign(self, node):
        # AugAssign(expr target, operator op, expr value)
        # e.g. x += y adds x to uses + defines, y to uses
        self.add_target_uses(node.target)
        self.add_target_defines(node.target)
        self.visit(node.value)

    def visit_AnnAssign(self, node):
        # AnnAssign(expr target, expr annotation, expr? value, int simple)
        # e.g.  x: int = y adds x to defines, then visits y
        self.add_target_defines(node.target)
        if node.value != None:
            self.visit(node.value)

    def visit_For(self, node):
        self.add_target_defines(node.target)
        self.visit(node.iter)
        self.visit_body_with_bound_targets([node.target], node.body + node.orelse)

    def visit_AsyncFor(self, node):
        self.visit_For(node)

    def visit_With(self, node):
        bound_targets = []
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.add_target_defines(item.optional_vars)
                bound_targets.append(item.optional_vars)
        self.visit_body_with_bound_targets(bound_targets, node.body)

    def visit_AsyncWith(self, node):
        self.visit_With(node)

    def visit_body_with_bound_targets(self, targets, body):
        bound_names = set()
        for target in targets:
            self.collect_target_names(target, bound_names)

        prior_uses = set(self.uses)
        for statement in body:
            self.visit(statement)

        for name in bound_names:
            if name not in prior_uses and name in self.uses:
                self.uses.remove(name)

    def visit_FunctionDef(self, node):
        # FunctionDef(identifier name, arguments args,
                       # stmt* body, expr* decorator_list, expr? returns,
                       # string? type_comment, type_param* type_params)
        
        # e.g. def f(x): return x + a -> defines callable f
        self.add_define(node.name)
        self.add_callable_define(node.name)
        self.add_function_uses(node.name, self.get_function_external_uses(node))

    def visit_AsyncFunctionDef(self, node):
        # logic: same as FunctionDef but for async functions
        self.add_define(node.name)
        self.add_callable_define(node.name)
        self.add_function_uses(node.name, self.get_function_external_uses(node))

    def visit_ClassDef(self, node):
        # ClassDef(identifier name,
             # expr* bases,
             # keyword* keywords,
             # stmt* body,
             # expr* decorator_list,
             # type_param* type_params)

        # e.g. class Model defines callable Model
        self.add_define(node.name)
        self.add_callable_define(node.name)

    # expr
    def visit_Name(self, node):
        # Name(identifier id, expr_context ctx)
    
        # e.g. print(a) adds a to uses
        if isinstance(node.ctx, ast.Load):
            self.add_use(node.id)

    def visit_Call(self, node):
        # Call(expr func, expr* args, keyword* keywords)

        # e.g. pd.read_csv(path) adds pd.read_csv to calls, then visits path
        call = self.get_call_name(node.func)
        if call != None:
            self.add_call(call)
        self.generic_visit(node)

    # ADDERS
    def add_import(self, value):
        self.add_if_not_in(value, self.imports)

    def add_define(self, value):
        self.add_if_not_in(value, self.defines)

    def add_callable_define(self, value):
        self.add_if_not_in(value, self.callable_defines)

    def add_use(self, value):
        self.add_if_not_in(value, self.uses)

    def add_call(self, value):
        self.add_if_not_in(value, self.calls)

    def add_function_uses(self, name, uses):
        self.function_uses[name] = uses

    # generic adder function
    def add_if_not_in(self, value, tab):
        if value not in tab:
            tab.append(value)
    
    # target adders (defines, uses)
    def add_target_defines(self, target):
        if isinstance(target, ast.Name):
            self.add_define(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.add_target_defines(element)

    def add_target_uses(self, target):
        # used for AugAssign: x += y both uses and defines x
        if isinstance(target, ast.Name):
            self.add_use(target.id)

        elif isinstance(target, ast.Attribute):
            # obj.attr uses obj
            self.visit(target.value)

        elif isinstance(target, ast.Subscript):
            # tab[i] uses tab and i
            self.visit(target.value)
            self.visit(target.slice)

        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self.add_target_uses(elt)
    
    def collect_target_names(self, target, names):
        # same target logic as add_target_defines, but stores in a set
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.collect_target_names(element, names)

    # FUNCTION BODY USES
    def get_function_external_uses(self, n):
        # goal: find variables used inside a function, but defined outside
        locs = self.get_function_argument_names(n)
        defs = set()
        globs = set()

        # first pass: find names that are local to the function
        for child in n.body:
            self.collect_function_local_names(child, defs, globs)

        locs.update(defs)
        # global x means x is not local, so it can be a dependency
        locs.difference_update(globs)

        # second pass: collect uses that are not local
        uses = []
        for child in n.body:
            self.collect_external_uses(child, locs, uses)
        return uses

    def collect_function_local_names(self, n, defs, globs):
        # e.g. (local names :)
        # def f(x): y = x + 1 , x and y are local
        # def f(): import pandas as pd , pd is local
        # def f(): for row in data: , row is local, data is not

        # Global(identifier* names)
        if isinstance(n, ast.Global):
            for name in n.names:
                globs.add(name)
            return

        # import inside a function creates a local name
        if isinstance(n, ast.Import):
            for alias in n.names:
                defs.add(alias.asname or alias.name.split(".")[0])
            return

        # from module import name creates a local name
        if isinstance(n, ast.ImportFrom):
            for alias in n.names:
                defs.add(alias.asname or alias.name)
            return

        # functions/classes are local definitions
        # e.g. def f(): def helper(): ..., helper is local
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.add(n.name)
            return

        # collect assignment targets that define local names
        # e.g. total = value -> total is local, value might be external

        if isinstance(n, ast.Assign):
            for tgt in n.targets:
                self.collect_target_names(tgt, defs)

        elif isinstance(n, ast.AnnAssign):
            self.collect_target_names(n.target, defs)
            
        elif isinstance(n, ast.AugAssign):
            self.collect_target_names(n.target, defs)

        elif isinstance(n, (ast.For, ast.AsyncFor)):
            self.collect_target_names(n.target, defs)

        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if item.optional_vars != None:
                    self.collect_target_names(item.optional_vars, defs)
        
        elif isinstance(n, ast.ExceptHandler):
            if n.name != None:
                defs.add(n.name)

        # continue recursively in children of this node
        for child in ast.iter_child_nodes(n):
            self.collect_function_local_names(child, defs, globs)

    def collect_external_uses(self, n, locs, uses):
        # e.g. def f(x): return x + a
        # x is ignored because it is local and a is added to uses
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return

        # Name(identifier id, expr_context ctx)
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load) and n.id not in locs:
                self.add_if_not_in(n.id, uses)

        # continue recursively in children of this node
        for child in ast.iter_child_nodes(n):
            self.collect_external_uses(child, locs, uses)

    def get_function_argument_names(self, n):
        # arguments object: positional args, *args, keyword args, **kwargs
        
        # e.g. def f(a, b=1, *args, c=2, **kwargs)
        # all of these names are local to f
        names = set()
        args = n.args
        for arg in args.posonlyargs:
            names.add(arg.arg)
        for arg in args.args:
            names.add(arg.arg)
        if args.vararg != None:
            names.add(args.vararg.arg)
        for arg in args.kwonlyargs:
            names.add(arg.arg)
        if args.kwarg != None:
            names.add(args.kwarg.arg)
        return names

    def get_call_name(self, n):
        # transforms a Call func node into a readable name
        # f() -> f, module.f() -> module.f
        if isinstance(n, ast.Name):
            return n.id
        if isinstance(n, ast.Attribute):
            parent = self.get_call_name(n.value)
            if parent == None:
                return n.attr
            return f"{parent}.{n.attr}"
        if isinstance(n, ast.Subscript):
            # f()[i]() keeps the callable part when possible
            return self.get_call_name(n.value)
        return None
