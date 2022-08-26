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
import logging

logging.basicConfig(
    format='%(levelname)-8s %(asctime)s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)


class ModuleManager:
    def __init__(self):
        self.internal = {}
        self.external = {}

    def create(self, name, fname, external=False):
        logger.debug("In ModuleManager.create")
        mod = Module(name, fname)
        if external:
            self.external[name] = mod
        else:
            self.internal[name] = mod
        return mod

    def get(self, name):
        logger.debug("In ModuleManager.get")
        if name in self.internal:
            return self.internal[name]
        if name in self.external:
            return self.external[name]

    def get_internal_modules(self):
        logger.debug("In ModuleManager.get_internal_modules")
        return self.internal

    def get_external_modules(self):
        logger.debug("In ModuleManager.get_external_modules")
        return self.external

class Module:
    def __init__(self, name, filename):
        logger.debug("In Module.__init__")
        self.name = name
        self.filename = filename
        self.methods = dict()

    def get_name(self):
        logger.debug("In Module.get_name")
        return self.name

    def get_filename(self):
        logger.debug("In Module.get_filename")
        return self.filename

    def get_methods(self):
        logger.debug("In Module.get_methods")
        return self.methods

    def add_method(self, method, first=None, last=None):
        logger.debug("In Module.add_method")
        if not self.methods.get(method, None):
            self.methods[method] = dict(
                    name=method,
                    first=first,
                    last=last)
