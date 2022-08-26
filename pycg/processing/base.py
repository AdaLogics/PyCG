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
import ast
import os
import sys
import logging
import traceback

from pycg import utils
from pycg.machinery.definitions import Definition

logging.basicConfig(
    format='%(levelname)-8s %(asctime)s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)


class ProcessingBase(ast.NodeVisitor):
    def __init__(self, filename, modname, modules_analyzed):
        logger.debug(
            "In ProcessingBase.__init__: filename: %s; mod_name: %s; "
            " analyzed modules: %s"
            %(filename, modname, str(modules_analyzed))
        )

        self.modname = modname

        self.modules_analyzed = modules_analyzed
        self.modules_analyzed.add(self.modname)

        self.filename = os.path.abspath(filename)

        print("Opening: %s"%(filename))
        ff = open(filename, "rt")
        self.contents = ff.read()

        self.name_stack = []
        self.method_stack = []
        self.last_called_names = None
        logger.debug("Exit ProcessingBase.__init__")

    def get_modules_analyzed(self):
        logger.debug("Called ProcessingBase.get_modules_analyzed")
        return self.modules_analyzed

    def merge_modules_analyzed(self, analyzed):
        logger.debug("In ProcessingBase.merge_modules_analyzed")
        self.modules_analyzed = self.modules_analyzed.union(analyzed)
        logger.debug("Exit ProcessingBase.merge_modules_analyzed")

    @property
    def current_ns(self):
        logger.debug("Called ProcessingBase.current_ns")
        return ".".join(self.name_stack)

    @property
    def current_method(self):
        logger.debug("Called ProcessingBase.current_method")
        return ".".join(self.method_stack)

    def visit_Module(self, node):
        logger.debug("In ProcessingBase.visit_Module")
        self.name_stack.append(self.modname)
        self.method_stack.append(self.modname)
        self.scope_manager.get_scope(self.modname).reset_counters()
        self.generic_visit(node)
        self.method_stack.pop()
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_Module")

    def visit_FunctionDef(self, node):
        logger.debug("In ProcessingBase.visit_FunctionDef")
        self.name_stack.append(node.name)
        self.method_stack.append(node.name)
        if self.scope_manager.get_scope(self.current_ns):
            self.scope_manager.get_scope(self.current_ns).reset_counters()
            for stmt in node.body:
                self.visit(stmt)
        self.method_stack.pop()
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_FunctionDef")

    def visit_Lambda(self, node, lambda_name=None):
        logger.debug("In ProcessingBase.visit_Lambda")
        lambda_ns = utils.join_ns(self.current_ns, lambda_name)
        if not self.scope_manager.get_scope(lambda_ns):
            self.scope_manager.create_scope(lambda_ns,
                    self.scope_manager.get_scope(self.current_ns))
        self.name_stack.append(lambda_name)
        self.method_stack.append(lambda_name)
        self.visit(node.body)
        self.method_stack.pop()
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_Lambda")

    def visit_For(self, node):
        logger.debug("In ProcessingBase.visit_For")
        for item in node.body:
            self.visit(item)
        logger.debug("Exit ProcessingBase.visit_For")

    def visit_Dict(self, node):
        logger.debug("In ProcessingBase.visit_Dict")
        counter = self.scope_manager.get_scope(self.current_ns).inc_dict_counter()
        dict_name = utils.get_dict_name(counter)

        sc = self.scope_manager.get_scope(utils.join_ns(self.current_ns, dict_name))
        if not sc:
            logger.debug("Exit ProcessingBase.visit_Dict: No scope definition")
            return
        self.name_stack.append(dict_name)
        sc.reset_counters()
        for key, val in zip(node.keys, node.values):
            if key:
                self.visit(key)
            if val:
                self.visit(val)
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_Dict")

    def visit_List(self, node):
        logger.debug("In ProcessingBase.visit_List")
        counter = self.scope_manager.get_scope(self.current_ns).inc_list_counter()
        list_name = utils.get_list_name(counter)

        sc = self.scope_manager.get_scope(utils.join_ns(self.current_ns, list_name))
        if not sc:
            logger.debug("Exit ProcessingBase.visit_List: No scope definition")
            return
        self.name_stack.append(list_name)
        sc.reset_counters()
        for elt in node.elts:
            self.visit(elt)
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_List")

    def visit_BinOp(self, node):
        logger.debug("In ProcessingBase.visit_BinOp")
        self.visit(node.left)
        self.visit(node.right)
        logger.debug("Exit ProcessingBase.visit_BinOp")

    def visit_ClassDef(self, node):
        logger.debug("In ProcessingBase.visit_ClassDef")
        self.name_stack.append(node.name)
        self.method_stack.append(node.name)
        self.scope_manager.get_scope(self.current_ns).reset_counters()
        for stmt in node.body:
            self.visit(stmt)
        self.method_stack.pop()
        self.name_stack.pop()
        logger.debug("Exit ProcessingBase.visit_ClassDef")

    def visit_Tuple(self, node):
        logger.debug("In ProcessingBase.visit_Tuple")
        for elt in node.elts:
            self.visit(elt)
        logger.debug("Exit ProcessingBase.visit_Tuple")

    def _handle_assign(self, targetns, decoded):
        logger.debug("In ProcessingBase._handle_assign")
        defi = self.def_manager.get(targetns)
        if not defi:
            defi = self.def_manager.create(targetns, utils.constants.NAME_DEF)

        # check if decoded is iterable
        try:
            iter(decoded)
        except TypeError:
            logger.debug("Exit ProcessingBase._handle_assign: No definition found")
            return defi

        for d in decoded:
            if isinstance(d, Definition):
                defi.get_name_pointer().add(d.get_ns())
            else:
                defi.get_lit_pointer().add(d)
        logger.debug("Exit ProcessingBase._handle_assign")
        return defi

    def _visit_return(self, node):
        logger.debug("In ProcessingBase._visit_return")
        if not node or not node.value:
            return

        self.visit(node.value)

        return_ns = utils.join_ns(self.current_ns, utils.constants.RETURN_NAME)
        self._handle_assign(return_ns, self.decode_node(node.value))
        logger.debug("Exit ProcessingBase._visit_return")

    def _get_target_ns(self, target):
        logger.debug("In ProcessingBase._get_target_ns")
        if isinstance(target, ast.Name):
            logger.debug("Exit ProcessingBase._get_target_ns: Node type: Name")
            return [utils.join_ns(self.current_ns, target.id)]
        if isinstance(target, ast.Attribute):
            bases = self._retrieve_base_names(target)
            res = []
            for base in bases:
                res.append(utils.join_ns(base, target.attr))
            logger.debug("Exit ProcessingBase._get_target_ns: Node type: Attribute")
            return res
        if isinstance(target, ast.Subscript):
            logger.debug("Exit ProcessingBase._get_target_ns: Node type: Subscript")
            return self.retrieve_subscript_names(target)
        logger.debug("Exit ProcessingBase._get_target_ns: Invalid node type")
        return []

    def _visit_assign(self, value, targets):
        logger.debug("In ProcessingBase._visit_assign")
        self.visit(value)

        decoded = self.decode_node(value)

        def do_assign(decoded, target):
            logger.debug("In ProcessingBase._visit_assign.do_assign: Target: %s" % target)
            self.visit(target)
            if isinstance(target, ast.Tuple):
                for pos, elt in enumerate(target.elts):
                    if not isinstance(decoded, Definition) and pos < len(decoded):
                        do_assign(decoded[pos], elt)
            else:
                targetns = self._get_target_ns(target)
                for tns in targetns:
                    if not tns:
                        continue
                    defi = self._handle_assign(tns, decoded)
                    splitted = tns.split(".")
                    self.scope_manager.handle_assign(".".join(splitted[:-1]), splitted[-1], defi)
            logger.debug("Exit ProcessingBase._visit_assign.do_assign")

        for target in targets:
            do_assign(decoded, target)
        logger.debug("Exit ProcessingBase._visit_assign")

    def decode_node(self, node):
        logger.debug("In ProcessingBase.decode_node")
        if isinstance(node, ast.Name):
            logger.debug("Exit ProcessingBase.decode_node: Node type: Name")
            return [self.scope_manager.get_def(self.current_ns, node.id)]
        elif isinstance(node, ast.Call):
            decoded = self.decode_node(node.func)
            return_defs = []
            for called_def in decoded:
                if not isinstance(called_def, Definition):
                    continue

                return_ns = utils.constants.INVALID_NAME
                if called_def.is_function_def():
                    return_ns = utils.join_ns(called_def.get_ns(), utils.constants.RETURN_NAME)
                elif called_def.is_class_def():
                    return_ns = called_def.get_ns()
                elif called_def.is_ext_def():
                    return_ns_set = called_def.get_name_pointer().get()
                    if return_ns_set:
                        return_ns = next(iter(return_ns_set))
                defi = self.def_manager.get(return_ns)
                if defi:
                    return_defs.append(defi)

            logger.debug("Exit ProcessingBase.decode_node: Node type: Call")
            return return_defs
        elif isinstance(node, ast.Lambda):
            lambda_counter = self.scope_manager.get_scope(self.current_ns).get_lambda_counter()
            lambda_name = utils.get_lambda_name(lambda_counter)
            logger.debug("Exit ProcessingBase.decode_node: Node type: Lambda")
            return [self.scope_manager.get_def(self.current_ns, lambda_name)]
        elif isinstance(node, ast.Tuple):
            decoded = []
            for elt in node.elts:
                decoded.append(self.decode_node(elt))
            logger.debug("Exit ProcessingBase.decode_node: Node type: Tuple")
            return decoded
        elif isinstance(node, ast.BinOp):
            decoded_left = self.decode_node(node.left)
            decoded_right = self.decode_node(node.right)
            # return the non definition types if we're talking about a binop
            # since we only care about the type of the return (num, str, etc)
            if not isinstance(decoded_left, Definition):
                logger.debug("Exit ProcessingBase.decode_node: Node type: BinOp->Left")
                return decoded_left
            if not isinstance(decoded_right, Definition):
                logger.debug("Exit ProcessingBase.decode_node: Node type: BinOp->Right")
                return decoded_right
        elif isinstance(node, ast.Attribute):
            names = self._retrieve_attribute_names(node)
            defis = []
            for name in names:
                defi = self.def_manager.get(name)
                if defi:
                    defis.append(defi)
            logger.debug("Exit ProcessingBase.decode_node: Node type: Attribute")
            return defis
        elif isinstance(node, ast.Num):
            logger.debug("Exit ProcessingBase.decode_node: Node type: Num")
            return [node.n]
        elif isinstance(node, ast.Str):
            logger.debug("Exit ProcessingBase.decode_node: Node type: Str")
            return [node.s]
        elif self._is_literal(node):
            logger.debug("Exit ProcessingBase.decode_node: Node type: Literal Node")
            return [node]
        elif isinstance(node, ast.Dict):
            dict_counter = self.scope_manager.get_scope(self.current_ns).get_dict_counter()
            dict_name = utils.get_dict_name(dict_counter)
            scope_def = self.scope_manager.get_def(self.current_ns, dict_name)
            logger.debug("Exit ProcessingBase.decode_node: Node type: Dict")
            return [self.scope_manager.get_def(self.current_ns, dict_name)]
        elif isinstance(node, ast.List):
            list_counter = self.scope_manager.get_scope(self.current_ns).get_list_counter()
            list_name = utils.get_list_name(list_counter)
            scope_def = self.scope_manager.get_def(self.current_ns, list_name)
            logger.debug("Exit ProcessingBase.decode_node: Node type: List")
            return [self.scope_manager.get_def(self.current_ns, list_name)]
        elif isinstance(node, ast.Subscript):
            names = self.retrieve_subscript_names(node)
            defis = []
            for name in names:
                defi = self.def_manager.get(name)
                if defi:
                    defis.append(defi)
            logger.debug("Exit ProcessingBase.decode_node: Node type: Subscript")
            return defis

        logger.debug("Exit ProcessingBase.decode_node: Invalid node type")
        return []

    def _is_literal(self, item):
        logger.debug("Called ProcessingBase._is_literal")
        return isinstance(item, int) or isinstance(item, str) or isinstance(item, float)

    def _retrieve_base_names(self, node):
        logger.debug("In ProcessingBase._retrieve_base_names")
        if not isinstance(node, ast.Attribute):
            raise Exception("The node is not an attribute")

        if not getattr(self, "closured", None):
            logger.debug("Exit ProcessingBase._retrieve_base_names: Not closure")
            return set()

        decoded = self.decode_node(node.value)
        if not decoded:
            logger.debug("Exit ProcessingBase._retrieve_base_names: Fail to decode node value")
            return set()

        names = set()
        for name in decoded:
            if not name or not isinstance(name, Definition):
                continue

            for base in self.closured.get(name.get_ns(), []):
                cls = self.class_manager.get(base)
                if not cls:
                    continue

                for item in cls.get_mro():
                    names.add(item)
        logger.debug("Exit ProcessingBase._retrieve_base_names")
        return names


    def _retrieve_parent_names(self, node):
        logger.debug("In ProcessingBase._retrieve_parent_names")
        if not isinstance(node, ast.Attribute):
            raise Exception("The node is not an attribute")

        decoded = self.decode_node(node.value)
        if not decoded:
            logger.debug("Exit ProcessingBase._retrieve_parent_names: Fail to decode node value")
            return set()

        names = set()
        for parent in decoded:
            if not parent or not isinstance(parent, Definition):
                continue
            if getattr(self, "closured", None) and self.closured.get(parent.get_ns(), None):
                names = names.union(self.closured.get(parent.get_ns()))
            else:
                names.add(parent.get_ns())
        logger.debug("Exit ProcessingBase._retrieve_parent_names")
        return names

    def _retrieve_attribute_names(self, node):
        logger.debug("In ProcessingBase._retrieve_attribute_names")
        if not getattr(self, "closured", None):
            logger.debug("Exit ProcessingBase._retrieve_attribute_names: Not closure")
            return set()

        parent_names = self._retrieve_parent_names(node)
        names = set()
        for parent_name in parent_names:
            for name in self.closured.get(parent_name, []):
                defi = self.def_manager.get(name)
                if not defi:
                    continue
                if defi.is_class_def():
                    cls_names = self.find_cls_fun_ns(defi.get_ns(), node.attr)
                    if cls_names:
                        names = names.union(cls_names)
                if defi.is_function_def() or defi.is_module_def():
                    names.add(utils.join_ns(name, node.attr))
                if defi.is_ext_def():
                    # HACK: extenral attributes can lead to infinite loops
                    # Identify them here
                    if node.attr in name:
                        continue
                    ext_name = utils.join_ns(name, node.attr)
                    if not self.def_manager.get(ext_name):
                        self.def_manager.create(ext_name, utils.constants.EXT_DEF)
                    names.add(ext_name)

        logger.debug("Exit ProcessingBase._retrieve_attribute_names")
        return names

    def iterate_call_args(self, defi, node):
        logger.debug("In ProcessingBase.iterate_call_args")
        for pos, arg in enumerate(node.args):
            self.visit(arg)
            decoded = self.decode_node(arg)
            if defi.is_function_def():
                pos_arg_names = defi.get_name_pointer().get_pos_arg(pos)
                # if arguments for this position exist update their namespace
                if not pos_arg_names:
                    continue
                for name in pos_arg_names:
                    arg_def = self.def_manager.get(name)
                    if not arg_def:
                        continue
                    for d in decoded:
                        if isinstance(d, Definition):
                            arg_def.get_name_pointer().add(d.get_ns())
                        else:
                            arg_def.get_lit_pointer().add(d)
            else:
                for d in decoded:
                    if isinstance(d, Definition):
                        defi.get_name_pointer().add_pos_arg(pos, None, d.get_ns())
                    else:
                        defi.get_name_pointer().add_pos_lit_arg(pos, None, d)

        for keyword in node.keywords:
            self.visit(keyword.value)
            decoded = self.decode_node(keyword.value)
            if defi.is_function_def():
                arg_names = defi.get_name_pointer().get_arg(keyword.arg)
                if not arg_names:
                    continue
                for name in arg_names:
                    arg_def = self.def_manager.get(name)
                    if not arg_def:
                        continue
                    for d in decoded:
                        if isinstance(d, Definition):
                            arg_def.get_name_pointer().add(d.get_ns())
                        else:
                            arg_def.get_lit_pointer().add(d)
            else:
                for d in decoded:
                    if isinstance(d, Definition):
                        defi.get_name_pointer().add_arg(keyword.arg, d.get_ns())
                    else:
                        defi.get_name_pointer().add_lit_arg(keyword.arg, d)
        logger.debug("Exit ProcessingBase.loiterate_call_args")

    def retrieve_subscript_names(self, node):
        logger.debug("In ProcessingBase.retrieve_subscript_names")
        if not isinstance(node, ast.Subscript):
            raise Exception("The node is not an subcript")

        if not getattr(self, "closured", None):
            logger.debug("Exit ProcessingBase.retrieve_subscript_names: Not Closure")
            return set()

        if getattr(node.slice, "value", None) and self._is_literal(node.slice.value):
            sl_names = [node.slice.value]
        else:
            sl_names = self.decode_node(node.slice)

        val_names = self.decode_node(node.value)

        decoded_vals = set()
        keys = set()
        full_names = set()
        # get all names associated with this variable name
        for n in val_names:
            if n and isinstance(n, Definition) and self.closured.get(n.get_ns(), None):
                decoded_vals |= self.closured.get(n.get_ns())
        for s in sl_names:
            if isinstance(s, Definition) and self.closured.get(s.get_ns(), None):
                # we care about the literals pointed by the name
                # not the namespaces, so retrieve the literals pointed
                for name in self.closured.get(s.get_ns()):
                    defi = self.def_manager.get(name)
                    if not defi:
                        continue
                    keys |= defi.get_lit_pointer().get()
            elif isinstance(s, str):
                keys.add(s)
            elif isinstance(s, int):
                keys.add(utils.get_int_name(s))

        for d in decoded_vals:
            for key in keys:
                # check for existence of var name and key combination
                str_key = str(key)
                if isinstance(key, int):
                    str_key = utils.get_int_name(key)
                full_ns = utils.join_ns(d, str_key)
                full_names.add(full_ns)

        logger.debug("Exit ProcessingBase.retrieve_subscript_names")
        return full_names

    def retrieve_call_names(self, node):
        logger.debug("In ProcessingBase.retrieve_call_names")
        names = set()
        if isinstance(node.func, ast.Name):
            defi = self.scope_manager.get_def(self.current_ns, node.func.id)
            if defi:
                names = self.closured.get(defi.get_ns(), None)
        elif isinstance(node.func, ast.Call) and self.last_called_names:
            for name in self.last_called_names:
                return_ns = utils.join_ns(name, utils.constants.RETURN_NAME)
                returns = self.closured.get(return_ns)
                if not returns:
                    continue
                for ret in returns:
                    defi = self.def_manager.get(ret)
                    names.add(defi.get_ns())
        elif isinstance(node.func, ast.Attribute):
            names = self._retrieve_attribute_names(node.func)
        elif isinstance(node.func, ast.Subscript):
            # Calls can be performed only on single indices, not ranges
            full_names = self.retrieve_subscript_names(node.func)
            for n in full_names:
                if self.closured.get(n, None):
                    names |= self.closured.get(n)

        logger.debug("Exit ProcessingBase.retrieve_call_names")
        return names

    def analyze_submodules(self, cls, *args, **kwargs):
        logger.debug("In ProcessingBase.analyze_submodules")
        imports = self.import_manager.get_imports(self.modname)

        for imp in imports:
            self.analyze_submodule(cls, imp, *args, **kwargs)
        logger.debug("Exit ProcessingBase.analyze_submodules")

    def analyze_submodule(self, cls, imp, *args, **kwargs):
        logger.debug("In ProcessingBase.analyze_submodule")
        if imp in self.get_modules_analyzed():
            logger.debug("Exit ProcessingBase.analyze_submodule: Skip analyzed module: %s" % imp)
            return

        fname = self.import_manager.get_filepath(imp)

        if not fname or not self.import_manager.get_mod_dir() in fname:
            logger.debug("Exit ProcessingBase.analyze_submodule: Fail to locate module source:  %s" % imp)
            return

        self.import_manager.set_current_mod(imp, fname)

        visitor = cls(fname, imp, *args, **kwargs)
        visitor.analyze()
        self.merge_modules_analyzed(visitor.get_modules_analyzed())

        self.import_manager.set_current_mod(self.modname, self.filename)
        logger.debug("Exit ProcessingBase.analyze_submodule")

    def find_cls_fun_ns(self, cls_name, fn):
        logger.debug("In ProcessingBase.find_cls_fun_ns")
        cls = self.class_manager.get(cls_name)
        if not cls:
            logger.debug("Exit ProcessingBase.find_cls_fun_ns: No class manager found")
            return set()

        ext_names = set()
        for item in cls.get_mro():
            ns = utils.join_ns(item, fn)
            names = set()
            if getattr(self, "closured", None) and self.closured.get(ns, None):
                names = self.closured[ns]
            else:
                names.add(ns)

            if self.def_manager.get(ns):
                logger.debug("Exit ProcessingBase.find_cls_fun_ns: Found from definition manager")
                return names

            parent = self.def_manager.get(item)
            if parent and parent.is_ext_def():
                ext_names.add(ns)

        for name in ext_names:
            self.def_manager.create(name, utils.constants.EXT_DEF)
            self.add_ext_mod_node(name)

        logger.debug("Exit ProcessingBase.find_cls_fun_ns: Found from external source")
        return ext_names

    def add_ext_mod_node(self, name):
        logger.debug("In ProcessingBase.add_ext_mod_node")
        ext_modname = name.split(".")[0]
        ext_mod = self.module_manager.get(ext_modname)
        if not ext_mod:
            ext_mod = self.module_manager.create(ext_modname, None, external=True)
            ext_mod.add_method(ext_modname)

        ext_mod.add_method(name)
        logger.debug("Exit ProcessingBase.add_ext_mod_node")
