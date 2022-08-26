#
# Copyright (c) 2020 Vitalis Salis.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import os
import ast

from pycg import utils
from pycg.processing.base import ProcessingBase
from pycg.machinery.callgraph import CallGraph
from pycg.machinery.definitions import Definition

class CallGraphProcessor(ProcessingBase):
    def __init__(self, filename, modname, import_manager,
            scope_manager, def_manager, class_manager,
            module_manager, call_graph=None, modules_analyzed=None):
        print("C1")
        super().__init__(filename, modname, modules_analyzed)
        # parent directory of file
        self.parent_dir = os.path.dirname(filename)
        self.current_node_name = None
        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager = def_manager
        self.class_manager = class_manager
        self.module_manager = module_manager

        self.call_graph = call_graph

        self.closured = self.def_manager.transitive_closure()

    def visit_Module(self, node):
        print("C1")
        print("Visiting module %s"%(self.modname))
        self.call_graph.add_node(self.modname, self.modname)
        super().visit_Module(node)

    def visit_For(self, node):
        print("C1")
        self.visit(node.iter)
        self.visit(node.target)
        # assign target.id to the return value of __next__ of node.iter.it
        # we need to have a visit for on the postprocessor also
        iter_decoded = self.decode_node(node.iter)
        for item in iter_decoded:
            if not isinstance(item, Definition):
                continue
            names = self.closured.get(item.get_ns(), [])
            for name in names:
                iter_ns = utils.join_ns(name, utils.constants.ITER_METHOD)
                next_ns = utils.join_ns(name, utils.constants.NEXT_METHOD)
                if self.def_manager.get(iter_ns):
                    self.call_graph.add_edge(self.current_method, iter_ns, mod=self.modname)
                if self.def_manager.get(next_ns):
                    self.call_graph.add_edge(self.current_method, next_ns, mod=self.modname)

        super().visit_For(node)

    def visit_Lambda(self, node):
        print("C1")
        counter = self.scope_manager.get_scope(self.current_ns).inc_lambda_counter()
        lambda_name = utils.get_lambda_name(counter)
        lambda_fullns = utils.join_ns(self.current_ns, lambda_name)

        self.call_graph.add_node(lambda_fullns, self.modname)

        super().visit_Lambda(node, lambda_name)

    def visit_Raise(self, node):
        print("C1")
        if not node.exc:
            return
        self.visit(node.exc)
        decoded = self.decode_node(node.exc)
        for d in decoded:
            if not isinstance(d, Definition):
                continue
            names = self.closured.get(d.get_ns(), [])
            for name in names:
                pointer_def = self.def_manager.get(name)
                if pointer_def.is_class_def():
                    init_ns = self.find_cls_fun_ns(name, utils.constants.CLS_INIT)
                    for ns in init_ns:
                        self.call_graph.add_edge(self.current_method, ns, mod=self.modname)
                if pointer_def.is_ext_def():
                    self.call_graph.add_edge(self.current_method, name, mod=self.modname)

    def visit_AsyncFunctionDef(self, node):
        print("C1")
        self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node):
        print("C1")
        for decorator in node.decorator_list:
            self.visit(decorator)
            decoded = self.decode_node(decorator)
            for d in decoded:
                if not isinstance(d, Definition):
                    continue
                names = self.closured.get(d.get_ns(), [])
                for name in names:
                    self.call_graph.add_edge(self.current_method, name, mod=self.modname)

        self.call_graph.add_node(utils.join_ns(self.current_ns, node.name), self.modname)
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['lineno'] = node.lineno
        arg_names = []
        arg_count = 0
        if node.args.args != None:
            for arg in node.args.args:
                arg_names.append(arg.arg)
        if node.args.vararg != None:
            arg_names.append(node.args.vararg.arg)
        if node.args.kwonlyargs != None:
            for arg in node.args.kwonlyargs:
                arg_names.append(arg.arg)
        if node.args.kwarg != None:
            arg_names.append(node.args.kwarg.arg)

        arg_types = []
        for arg_name in arg_names:
            arg_types.append("N/A")
        print("Setting callgraph to: %d"%(arg_count))
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['argCount'] = len(arg_names)
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['argNames'] = arg_names
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['argTypes'] = arg_types
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['ifCount'] = 0
        self.call_graph.cg_extended[utils.join_ns(self.current_ns, node.name)]['meta']['exprCount'] = 0
        self.current_node_name = node.name


        super().visit_FunctionDef(node)

    def visit_If(self, node):
        print("C1")
        #print("TTT: %s%s"%(str(self.current_ns), str(self.current_node_name)))
        #FTS="%s%s"%(str(self.current_ns), str(self.current_node_name))
        FTS="%s"%(str(self.current_ns))
        print("Checking: %s"%(FTS))
        print("Checking2: %s"%(utils.join_ns(self.current_ns, self.current_node_name)))

        if (
            self.current_node_name != None and
            FTS in self.call_graph.cg_extended
        ):
            try:
                self.call_graph.cg_extended[FTS]['meta']['ifCount'] += 1
            except:
                self.call_graph.cg_extended[FTS]['meta']['ifCount'] = 1

        self.generic_visit(node)

    def visit_Expr(self, node):
        print("C1")
        #print("Visiting expr")
        FTS="%s"%(str(self.current_ns))
        if FTS in self.call_graph.cg_extended:
            try:
                self.call_graph.cg_extended[FTS]['meta']['exprCount'] += 1
            except:
                self.call_graph.cg_extended[FTS]['meta']['exprCount'] = 1
        self.generic_visit(node)
    #    #super().visit_Expr(node)

    def visit_Call(self, node):
        print("C1")
        def create_ext_edge(name, ext_modname, e_lineno=-1, mod=""):
            self.add_ext_mod_node(name)
            self.call_graph.add_node(name, ext_modname)
            self.call_graph.add_edge(self.current_method, name, lineno=e_lineno, mod=mod, ext_mod=ext_modname)

        # First visit the child function so that on the case of
        #       func()()()
        # we first visit the call to func and then the other calls
        for arg in node.args:
            self.visit(arg)

        for keyword in node.keywords:
            self.visit(keyword.value)

        self.visit(node.func)

        names = self.retrieve_call_names(node)
        print("Iterating node with line number2: %d"%(node.lineno))
        try:
            print("- %s"%(node.func.id))
            print("- Arguments: %s"%(str(node.args)))
        except:
            try:
                print("- %s.%s"%(node.func.value.id, node.func.attr))
                print("%s"%(str(node.args)))
            except:
                None
            for elem in node.args:
                #print("%s"%(str(elem)))
                try:
                    print("%s"%(str(elem.id)))
                except:
                    None
            None
        print("D1")
        # Go through the arguments
        try:
            if ( isinstance(node.func, ast.Attribute) and
                 node.func.value.id == "atheris" and 
                 node.func.attr == "Setup"
            ):
                # Get the target function
                target_func = node.args[1].id
                self.call_graph.add_entrypoint(target_func, self.modname)
                print("We have the set up function here")
                print("Target func: %s"%(target_func))
        except:
            None
        if not names:
            print("D2")
            print(str(node))
            if isinstance(node.func, ast.Attribute) and self.has_ext_parent(node.func):
                print("D3")
                # TODO: This doesn't work for cases where there is an assignment of an attribute
                # i.e. import os; lala = os.path; lala.dirname()
                for name in self.get_full_attr_names(node.func):
                    ext_modname = name.split(".")[0]
                    create_ext_edge(name, ext_modname, node.lineno, self.modname)
            elif getattr(node.func, "id", None) and self.is_builtin(node.func.id):
                print("D4")
                name = utils.join_ns(utils.constants.BUILTIN_NAME, node.func.id)
                create_ext_edge(name, utils.constants.BUILTIN_NAME, node.lineno, self.modname)
            elif isinstance(node.func, ast.Attribute):
                print("It is actually an attribute")
                print(str(node.func.value))
                print(ast.dump(node))
                print("-----------------")
                print(ast.dump(node.func.value))
                print("-----------------")
                try:
                    a1 = node.func.value.id
                    # a2 = node.func.value.attr # Not sure the usage for a2, so comment it out temporary to avoid bug
                    a3 = node.func.attr
                    # print("Got it: %s -- %s -- %s"%(a1, a2, a3)) 
                    print("Got it: %s -- %s"%(a1, a3)) 
                    # Skip selfs for now. Down the line we probably want to fix this as well, but
                    # will wait with doing this. Most likely a larger rewrite is needed once
                    # I fully grasp what we need.
                    if a1 != "self":
                        # name = "%s.%s.%s"%(a1,a2,a3)
                        name = "%s.%s"%(a1,a3)
                        create_ext_edge(name, utils.constants.BUILTIN_NAME, node.lineno, self.modname)
                except:
                    print("Did not get it")
            print("D2.1")
            return
        print("D6")

        self.last_called_names = names
        for pointer in names:
            pointer_init = "%s.__init__" % pointer
            if pointer_init in self.scope_manager.get_scopes().keys():
                pointer = pointer_init
            pointer_def = self.def_manager.get(pointer)
            if not pointer_def or not isinstance(pointer_def, Definition):
                continue
            if pointer_def.is_callable():
                if pointer_def.is_ext_def():
                    ext_modname = pointer.split(".")[0]
                    create_ext_edge(pointer, ext_modname, node.lineno, self.modname)
                    continue
                self.call_graph.add_edge(self.current_method, pointer, lineno=node.lineno, mod=self.modname)

                # TODO: This doesn't work and leads to calls from the decorators
                #    themselves to the function, creating edges to the first decorator
                #for decorator in pointer_def.decorator_names:
                #    dec_names = self.closured.get(decorator, [])
                #    for dec_name in dec_names:
                #        if self.def_manager.get(dec_name).get_type() == utils.constants.FUN_DEF:
                #            self.call_graph.add_edge(self.current_ns, dec_name)

            if pointer_def.is_class_def():
                init_ns = self.find_cls_fun_ns(pointer, utils.constants.CLS_INIT)

                for ns in init_ns:
                    print("D7")
                    self.call_graph.add_edge(self.current_method, ns, lineno=node.lineno, mod=self.modname)

    def analyze_submodules(self):
        print("C1")
        super().analyze_submodules(CallGraphProcessor, self.import_manager,
                self.scope_manager, self.def_manager, self.class_manager, self.module_manager,
                call_graph=self.call_graph, modules_analyzed=self.get_modules_analyzed())

    def analyze(self):
        print("C1")
        self.visit(ast.parse(self.contents, self.filename))
        self.analyze_submodules()

    def get_all_reachable_functions(self):
        print("C1")
        reachable = set()
        names = set()
        current_scope = self.scope_manager.get_scope(self.current_ns)
        while current_scope:
            for name, defi in current_scope.get_defs().items():
                if defi.is_function_def() and not name in names:
                    closured = self.closured.get(defi.get_ns())
                    for item in closured:
                        reachable.add(item)
                    names.add(name)
            current_scope = current_scope.parent

        return reachable

    def has_ext_parent(self, node):
        print("C1")
        if not isinstance(node, ast.Attribute):
            return False

        while isinstance(node, ast.Attribute):
            parents = self._retrieve_parent_names(node)
            for parent in parents:
                for name in self.closured.get(parent, []):
                    defi = self.def_manager.get(name)
                    if defi and defi.is_ext_def():
                        return True
            node = node.value
        return False

    def get_full_attr_names(self, node):
        print("C1")
        name = ""
        while isinstance(node, ast.Attribute):
            if not name:
                name = node.attr
            else:
                name = node.attr + "." + name
            node = node.value

        names = []
        if getattr(node, "id", None) == None:
            return names

        defi = self.scope_manager.get_def(self.current_ns, node.id)
        if defi and self.closured.get(defi.get_ns()):
            for id in self.closured.get(defi.get_ns()):
                names.append(id + "." + name)

        return names

    def is_builtin(self, name):
        print("C1")
        return name in __builtins__
