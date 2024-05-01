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
import logging
from typing import Set, Optional

from pycg import utils
from pycg.machinery.definitions import Definition, DefinitionManager
from pycg.machinery.modules import ModuleManager
from pycg.machinery.imports import ImportManager
from pycg.machinery.scopes import ScopeManager
from pycg.machinery.classes import ClassManager
from pycg.processing.base import ProcessingBase

logger = logging.getLogger(__name__)


class PreProcessor(ProcessingBase):
    def __init__(
        self,
        filename: str,
        modname: str,
        import_manager: ImportManager,
        scope_manager: ScopeManager,
        def_manager: DefinitionManager,
        class_manager: ClassManager,
        module_manager: ModuleManager,
        modules_analyzed: Set[str],
    ) -> None:
        logger.debug(
            "In PreProcessor.__init__: filename: %s; mod_name: %s; analyzed_modules: %s"
            %(filename, modname, str(modules_analyzed))
        )
        super().__init__(filename, modname, modules_analyzed)

        self.modname = modname
        self.mod_dir = "/".join(self.filename.split("/")[:-1])

        self.import_manager = import_manager
        self.scope_manager = scope_manager
        self.def_manager: DefinitionManager = def_manager
        self.class_manager = class_manager
        self.module_manager = module_manager
        logger.debug("Exit PreProcessor.__init__")

    def _get_fun_defaults(self, node):
        logger.debug("In PreProcessor._get_fun_defaults")
        defaults = {}
        start = len(node.args.args) - len(node.args.defaults)
        for cnt, d in enumerate(node.args.defaults, start=start):
            if not d:
                continue

            self.visit(d)
            try:
                defaults[node.args.args[cnt].arg] = self.decode_node(d)
            except IndexError:
                continue

        start = len(node.args.kwonlyargs) - len(node.args.kw_defaults)
        for cnt, d in enumerate(node.args.kw_defaults, start=start):
            if not d:
                continue
            self.visit(d)
            defaults[node.args.kwonlyargs[cnt].arg] = self.decode_node(d)

        logger.debug("Exit PreProcessor._get_fun_defaults")
        return defaults

    def analyze_submodule(self, modname: str) -> None:
        logger.debug("In PreProcessor.analyze_submodule %s" % (modname))
        super().analyze_submodule(PreProcessor, modname,
            self.import_manager, self.scope_manager, self.def_manager, self.class_manager,
            self.module_manager, modules_analyzed=self.get_modules_analyzed())
        logger.debug("En PreProcessor.analyze_submodule")

    def visit_Module(self, node):
        logger.debug("In PreProcessor.visit_Module")

        def iterate_mod_items(items, const):
            logger.debug("In PreProcessor.visit_Module.iterate_mod_items")
            for item in items:
                defi = self.def_manager.get(item)
                if not defi:
                    defi = self.def_manager.create(item, const)

                splitted = item.split(".")
                name = splitted[-1]
                parentns = ".".join(splitted[:-1])
                self.scope_manager.get_scope(parentns).add_def(name, defi)

            logger.debug("Exit PreProcessor.visit_Module.iterate_mod_items")

        self.import_manager.set_current_mod(self.modname, self.filename)

        mod = self.module_manager.create(self.modname, self.filename)

        first = 1
        last = len(self.contents.splitlines())
        if last == 0:
            first = 0
        mod.add_method(self.modname, first, last)

        root_sc = self.scope_manager.get_scope(self.modname)
        if not root_sc:
            # initialize module scopes
            items = self.scope_manager.handle_module(self.modname,
                self.filename, self.contents)

            root_sc = self.scope_manager.get_scope(self.modname)
            root_defi = self.def_manager.get(self.modname)
            if not root_defi:
                root_defi = self.def_manager.create(self.modname, utils.constants.MOD_DEF)
            root_sc.add_def(self.modname.split(".")[-1], root_defi)

            # create function and class defs and add them to their scope
            # we do this here, because scope_manager doesn't have an
            # interface with def_manager, and we want function definitions
            # to have the correct points_to set
            iterate_mod_items(items["functions"], utils.constants.FUN_DEF)
            iterate_mod_items(items["classes"], utils.constants.CLS_DEF)

        defi = self.def_manager.get(self.modname)
        if not defi:
            defi = self.def_manager.create(self.modname, utils.constants.MOD_DEF)

        super().visit_Module(node)
        logger.debug("Exit PreProcessor.visit_Module")

    def visit_Import(self, node: ast.Import, prefix="", level=0):
        """
        For imports of the form
            `from something import anything`
        prefix is set to "something".
        For imports of the form
            `from .relative import anything`
        level is set to a number indicating the number
        of parent directories (e.g. in this case level=1)
        """
        logger.debug("In PreProcessor.visit_Import")
        # logger.debug("%s"%(ast.dump(node, indent=4)))
        logger.debug("--------------------")

        def handle_src_name(name):
            logger.debug("In PreProcessor.visit_Import.handle_src_name")
            # Get the module name and prepend prefix if necessary
            src_name = name
            if prefix:
                src_name = prefix + "." + src_name
            logger.debug("Exit PreProcessor.visit_Import.handle_src_name")
            return src_name

        def handle_scopes(imp_name, tgt_name, modname):
            logger.debug("In PreProcessor.visit_Import.handle_scopes")

            def create_def(scope, name, imported_def):
                logger.debug("In PreProcessor.visit_Import.handle_scopes.create_def")
                if not name in scope.get_defs():
                    def_ns = utils.join_ns(scope.get_ns(), name)
                    defi = self.def_manager.get(def_ns)
                    if not defi:
                        defi = self.def_manager.assign(def_ns, imported_def)
                    defi.get_name_pointer().add(imported_def.get_ns())
                    current_scope.add_def(name, defi)
                logger.debug("Exit PreProcessor.visit_Import.handle_scopes.create_def")

            current_scope = self.scope_manager.get_scope(self.current_ns)
            imported_scope = self.scope_manager.get_scope(modname)
            if imported_scope is not None:
                if tgt_name == "*":
                    for name, defi in imported_scope.get_defs().items():
                        create_def(current_scope, name, defi)
                        current_scope.get_def(name).get_name_pointer().add(defi.get_ns())
                else:
                    # if it exists in the imported scope then copy it
                    defi = imported_scope.get_def(imp_name)
                    if not defi:
                        # maybe its a full namespace
                        defi = self.def_manager.get(imp_name)

                    if defi:
                        create_def(current_scope, tgt_name, defi)
                        current_scope.get_def(tgt_name).get_name_pointer().add(defi.get_ns())
            logger.debug("Exit PreProcessor.visit_Import.handle_scopes")

        def add_external_def(name, target):
            logger.debug("In PreProcessor.visit_Import.add_external_def")
            # add an external def for the name
            defi = self.def_manager.get(name)
            if not defi:
                defi = self.def_manager.create(name, utils.constants.EXT_DEF)
            scope = self.scope_manager.get_scope(self.current_ns)
            if target != "*":
                # add a def for the target that points to the name
                tgt_ns = utils.join_ns(scope.get_ns(), target)
                tgt_defi = self.def_manager.get(tgt_ns)
                if not tgt_defi:
                    tgt_defi = self.def_manager.create(tgt_ns, utils.constants.EXT_DEF)
                tgt_defi.get_name_pointer().add(defi.get_ns())
                scope.add_def(target, tgt_defi)
            logger.debug("Exit PreProcessor.visit_Import.add_external_def")

        for import_item in node.names:
            logger.debug("IMP-1 %s"%(import_item.name))
            src_name = handle_src_name(import_item.name)
            logger.debug("IMP-2 %s"%(src_name))
            tgt_name = import_item.asname if import_item.asname else import_item.name
            logger.debug("IMP-3 %s"%(tgt_name))
            imported_name = self.import_manager.handle_import(src_name, level)
            logger.debug("IMP-4 %s"%(imported_name))

            if not imported_name:
                add_external_def(src_name, tgt_name)
                continue

            fname = self.import_manager.get_filepath(imported_name)
            logger.debug("IMP-5 %s"%(fname))
            if not fname:
                add_external_def(src_name, tgt_name)
                continue

            logger.debug("IMP-6")
            # only analyze modules under the current directory
            if self.import_manager.get_mod_dir() in fname:
                logger.debug("IMP-7")
                if not imported_name in self.modules_analyzed:
                    logger.debug("IMP-8")
                    self.analyze_submodule(imported_name)
                handle_scopes(import_item.name, tgt_name, imported_name)
            else:
                logger.debug("IMP-9")
                add_external_def(src_name, tgt_name)
            logger.debug("IMP-10")

        # handle all modules that were not analyzed
        for modname in self.import_manager.get_imports(self.modname):
            fname = self.import_manager.get_filepath(modname)
            if not fname:
                continue
            # only analyze modules under the current directory
            if self.import_manager.get_mod_dir() in fname and \
                not modname in self.modules_analyzed:
                    self.analyze_submodule(modname)
        logger.debug("Exit PreProcessor.visit_Import")

    def visit_ImportFrom(self, node):
        logger.debug("In PreProcessor.visit_ImportFrom")
        self.visit_Import(node, prefix=node.module, level=node.level)
        logger.debug("Exit PreProcessor.visit_ImportFrom")

    def _get_last_line(self, node):
        logger.debug("In PreProcessor._get_last_line")
        lines = sorted(list(ast.walk(node)), key=lambda x: x.lineno if hasattr(x, "lineno") else 0, reverse=True)
        if not lines:
            logger.debug("Exit PreProcessor._get_last_line")
            return node.lineno

        last = getattr(lines[0], "lineno", node.lineno)
        if last < node.lineno:
            logger.debug("Exit PreProcessor._get_last_line")
            return node.lineno

        logger.debug("Exit PreProcessor._get_last_line")
        return last

    def _handle_function_def(self, node, fn_name: str):
        logger.debug("In PreProcessor._handle_function_def")
        current_def = self.def_manager.get(self.current_ns)

        defaults = self._get_fun_defaults(node)

        fn_def = self.def_manager.handle_function_def(self.current_ns, fn_name)

        mod = self.module_manager.get(self.modname)
        if not mod:
            mod = self.module_manager.create(self.modname, self.filename)
        mod.add_method(fn_def.get_ns(), node.lineno, self._get_last_line(node))

        defs_to_create = []
        name_pointer = fn_def.get_name_pointer()

        # TODO: static methods can be created using the staticmethod() function too
        is_static_method = False
        if hasattr(node, "decorator_list"):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == utils.constants.STATIC_METHOD:
                    is_static_method = True

        if current_def.is_class_def() and not is_static_method and node.args.args:
            arg_ns = utils.join_ns(fn_def.get_ns(), node.args.args[0].arg)
            arg_def = self.def_manager.get(arg_ns)
            if not arg_def:
                arg_def = self.def_manager.create(arg_ns, utils.constants.NAME_DEF)
            arg_def.get_name_pointer().add(current_def.get_ns())

            self.scope_manager.handle_assign(fn_def.get_ns(), arg_def.get_name(), arg_def)
            node.args.args = node.args.args[1:]

        for pos, arg in enumerate(node.args.args):
            arg_ns = utils.join_ns(fn_def.get_ns(), arg.arg)
            name_pointer.add_pos_arg(pos, arg.arg, arg_ns)
            defs_to_create.append(arg_ns)

        for arg in node.args.kwonlyargs:
            arg_ns = utils.join_ns(fn_def.get_ns(), arg.arg)
            # TODO: add_name_arg function
            name_pointer.add_name_arg(arg.arg, arg_ns)
            defs_to_create.append(arg_ns)

        # TODO: Add support for kwargs and varargs
        #if node.args.kwarg:
        #    pass
        #if node.args.vararg:
        #    pass

        for arg_ns in defs_to_create:
            arg_def = self.def_manager.get(arg_ns)
            if not arg_def:
                arg_def = self.def_manager.create(arg_ns, utils.constants.NAME_DEF)

            self.scope_manager.handle_assign(fn_def.get_ns(), arg_def.get_name(), arg_def)

            # has a default
            arg_name = arg_ns.split(".")[-1]
            if defaults.get(arg_name, None):
                for default in defaults[arg_name]:
                    if isinstance(default, Definition):
                        arg_def.get_name_pointer().add(default.get_ns())
                        if default.is_function_def():
                            arg_def.get_name_pointer().add(default.get_ns())
                        else:
                            arg_def.merge(default)
                    else:
                        arg_def.get_lit_pointer().add(default)
        logger.debug("Exit PreProcessor._handle_function_def")
        return fn_def

    def visit_AsyncFunctionDef(self, node):
        logger.debug("In PreProcessor.visit_AsyncFunctionDef")
        self.visit_FunctionDef(node)
        logger.debug("Exit PreProcessor.visit_AsyncFunctionDef")

    def visit_FunctionDef(self, node):
        logger.debug("In PreProcessor.visit_FunctionDef")
        fn_def = self._handle_function_def(node, node.name)

        super().visit_FunctionDef(node)
        logger.debug("Exit PreProcessor.visit_FunctionDef")

    def visit_For(self, node):
        logger.debug("In PreProcessor.visit_For")
        # just create the definition for target
        if isinstance(node.target, ast.Name):
            target_ns = utils.join_ns(self.current_ns, node.target.id)
            if not self.def_manager.get(target_ns):
                defi = self.def_manager.create(target_ns, utils.constants.NAME_DEF)
                self.scope_manager.get_scope(self.current_ns).add_def(node.target.id, defi)
        super().visit_For(node)
        logger.debug("Exit PreProcessor.visit_For")

    def visit_Assign(self, node):
        logger.debug("In PreProcessor.visit_Assign")
        self._visit_assign(node.value, node.targets)
        logger.debug("Exit PreProcessor.visit_Assign")

    def visit_Return(self, node):
        logger.debug("In PreProcessor.visit_Return")
        self._visit_return(node)
        logger.debug("Exit PreProcessor.visit_Return")

    def visit_Yield(self, node):
        logger.debug("In PreProcessor.visit_Yield")
        self._visit_return(node)
        logger.debug("Exit PreProcessor.visit_Yield")

    def visit_Call(self, node):
        logger.debug("In PreProcessor.visit_Call")
        self.visit(node.func)
        # if it is not a name there's nothing we can do here
        # ModuleVisitor will be able to resolve those calls
        # since it'll have the name tracking information
        if not isinstance(node.func, ast.Name):
            return

        fullns = utils.join_ns(self.current_ns, node.func.id)

        defi = self.scope_manager.get_def(self.current_ns, node.func.id)
        if not defi:
            return

        if defi.is_class_def():
            defi = self.def_manager.get(utils.join_ns(defi.get_ns(), utils.constants.CLS_INIT))
            if not defi:
                return

        self.iterate_call_args(defi, node)

        logger.debug("Exit PreProcessor.visit_Call")

    def visit_Lambda(self, node):
        logger.debug("In PreProcessor.visit_Lambda")
        # The name of a lambda is defined by the counter of the current scope
        current_scope = self.scope_manager.get_scope(self.current_ns)
        lambda_counter = current_scope.inc_lambda_counter()
        lambda_name = utils.get_lambda_name(lambda_counter)
        lambda_full_ns = utils.join_ns(self.current_ns, lambda_name)

        # create a scope for the lambda
        self.scope_manager.create_scope(lambda_full_ns, current_scope)
        lambda_def = self._handle_function_def(node, lambda_name)
        # add it to the current scope
        current_scope.add_def(lambda_name, lambda_def)

        super().visit_Lambda(node, lambda_name)

        logger.debug("Exit PreProcessor.visit_Lambda")

    def visit_ClassDef(self, node: ast.ClassDef):
        # create a definition for the class (node.name)
        logger.debug("In PreProcessor.visit_ClassDef")
        cls_def = self.def_manager.handle_class_def(self.current_ns, node.name)

        mod = self.module_manager.get(self.modname)
        if not mod:
            mod = self.module_manager.create(self.modname, self.filename)
        mod.add_method(cls_def.get_ns(), node.lineno, self._get_last_line(node))

        # iterate bases to compute MRO for the class
        cls = self.class_manager.get(cls_def.get_ns())
        if not cls:
            cls = self.class_manager.create(cls_def.get_ns(), self.modname)
            for nam in node.bases:
                if isinstance(nam, ast.Name):
                    self.class_manager.add_inheritance(cls_def.get_ns(), nam.id)

        super().visit_ClassDef(node)

        logger.debug("Exit PreProcessor.visit_Lambda")

    def analyze(self) -> None:
        logger.debug("In PreProcessor.analyze")
        if not self.import_manager.get_node(self.modname):
            self.import_manager.create_node(self.modname)
            self.import_manager.set_filepath(self.modname, self.filename)

        try:
            self.visit(ast.parse(self.contents, self.filename))
        except SyntaxError:
            # In the event for some reason there is a Syntax error we avoid
            # failing completely.
            logger.info("SyntaxError happened for %s" % (self.filename))
            pass

        logger.debug("Exit PreProcessor.analyze")
