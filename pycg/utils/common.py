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
from typing import Optional


def get_lambda_name(counter) -> str:
    return "<lambda{}>".format(counter)


def get_dict_name(counter) -> str:
    return "<dict{}>".format(counter)


def get_list_name(counter) -> str:
    return "<list{}>".format(counter)


def get_int_name(counter) -> str:
    return "<int{}>".format(counter)


def join_ns(*args: str) -> str:
    return ".".join(args)


def to_mod_name(name, package=None) -> str:
    return os.path.splitext(name)[0].replace("/", ".")
