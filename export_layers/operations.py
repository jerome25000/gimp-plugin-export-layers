# -*- coding: utf-8 -*-
#
# This file is part of Export Layers.
#
# Copyright (C) 2013-2018 khalim19 <khalim19@gmail.com>
#
# Export Layers is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Export Layers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Export Layers.  If not, see <https://www.gnu.org/licenses/>.

"""
This module defines the means to create and manipulate plug-in operations and
constraints.

Most functions take a setting group containing operations/constraints as its
first argument.

Many functions define events invoked on the setting group containing
operations/constraints. These events include:

* `"before-add-operation"` - invoked when:
  * calling `add` before adding an operation,
  * calling `SettingGroup.load` or `SettingPersistor.load` before loading an
    operation (loading an operation counts as adding),
  * calling `clear` before resetting operations (due to initial operations being
    added back).
  
  Arguments: operation dictionary to be added

* `"after-add-operation"` - invoked when:
  * calling `add` after adding an operation,
  * calling `SettingGroup.load` or `SettingPersistor.load` after loading an
    operation (loading an operation counts as adding),
  * calling `clear` after resetting operations (due to initial operations being
    added back).
  
  Arguments: created operation, original operation dictionary (same as in
  `"before-add-operation"`)

* `"before-reorder-operation"` - invoked when calling `reorder` before
  reordering an operation.
  
  Arguments: operation, position before reordering

* `"after-reorder-operation"` - invoked when calling `reorder` after reordering
  an operation.
  
  Arguments: operation, position before reordering, new position

* `"before-remove-operation"` - invoked when calling `remove` before removing an
  operation.
  
  Arguments: operation to be removed

* `"after-remove-operation"` - invoked when calling `remove` after removing an
  operation.
  
  Arguments: name of the removed operation

* `"before-clear-operation"` - invoked when calling `clear` before clearing
  operations.

* `"after-clear-operation"` - invoked when calling `clear` after clearing
  operations.
"""

from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *

from export_layers import pygimplib
from export_layers.pygimplib import pgpath
from export_layers.pygimplib import pgpdb
from export_layers.pygimplib import pgsetting
from export_layers.pygimplib import pgsettinggroup


BUILTIN_TAGS = {
  "background": _("Background"),
  "foreground": _("Foreground")
}

DEFAULT_OPERATIONS_GROUP = "default_operations"
DEFAULT_CONSTRAINTS_GROUP = "default_constraints"


def create(name, initial_operations=None):
  """
  Create a `SettingGroup` instance containing operations.
  
  Parameters:
  * `name` - name of the `SettingGroup` instance.
  * `type` - `"operation"` or `"constraint"`, see below for details.
  * `initial_operations` - list of dictionaries describing operations to be
    added by default. Calling `clear` will reset the operations returned by this
    function to the initial operations. By default, no initial operations are
    added.
  
  The resulting `SettingGroup` instance contains the following subgroups:
  * `"added"` - contains operations added via `add`.
  * `"added_data"` - operations stored as dictionaries, used when loading or
    saving operations persistently. `"added_data"` should only be used and
    modified internally.
  
  Each dictionary in `initial_operations` can contain the following fields:
  * `"name"` - name of the operation.
  * `"type"` - see below for details.
  * `"function"` - the function to execute.
  * `"arguments"` - arguments to `"function"` as a list of dictionaries defining
    settings. Each dictionary must contain mandatory attributes and can contain
    optional attributes as stated in `SettingGroup.add`.
  * `"enabled"` - whether the operation should be executed or not.
  * `"display_name"` - the display name (human-readable name) of the operation
  * `"operation_group"` - list of groups the operation belongs to; used in
    `pgoperations.OperationExecutor` and `exportlayers.LayerExporter`
  
  Each created operation in the returned group is a nested `SettingGroup`.
  An additional group is `"arguments"` that contains arguments to the function;
  each argument is a separate setting (`Setting` instance).
  
  Possible values for `"type"`:
  * `"operation"` (default) - represents a regular operation.
    `"operation_group"` defaults to `DEFAULT_OPERATIONS_GROUP` if not defined.
  * `"constraint"` - represents a constraint.
    `"operation_group"` defaults to `DEFAULT_CONSTRAINTS_GROUP` if not defined.
    Additional allowed fields for `"constraint"` include:
      * `subfilter` - the name of a subfilter for an `ObjectFilter` instance
        where constraints should be added. By default, `subfilter` is `None` (no
        subfilter is assumed).
  
  Other values for `"type"` raise `ValueError`.
  """
  operations = pgsettinggroup.SettingGroup(
    name=name,
    setting_attributes={
      "pdb_type": None,
      "setting_sources": None,
    })
  
  added_operations = pgsettinggroup.SettingGroup(
    name="added",
    setting_attributes={
      "pdb_type": None,
      "setting_sources": None,
    })
  
  operations.add([
    added_operations,
    {
      "type": pgsetting.SettingTypes.generic,
      "name": "added_data",
      "default_value": _get_initial_added_data(initial_operations),
      "setting_sources": [
        pygimplib.config.SOURCE_SESSION, pygimplib.config.SOURCE_PERSISTENT]
    },
    {
      "type": pgsetting.SettingTypes.generic,
      "name": "added_data_values",
      "default_value": {},
      "setting_sources": [
        pygimplib.config.SOURCE_SESSION, pygimplib.config.SOURCE_PERSISTENT]
    },
  ])
  
  _create_operations_from_added_data(operations)
  
  operations.connect_event(
    "after-clear-operations",
    _create_operations_from_added_data)
  
  operations["added_data"].connect_event(
    "before-load",
    _clear_operations_before_load_without_adding_initial_operations,
    operations)
  
  operations["added_data"].connect_event(
    "after-load",
    lambda added_data_setting: (
      _create_operations_from_added_data(added_data_setting.parent)))
  
  operations["added_data_values"].connect_event(
    "before-save",
    _get_values_from_operations,
    operations["added"])
  
  operations["added_data_values"].connect_event(
    "after-load",
    _set_values_for_operations,
    operations["added"])
  
  return operations


def _get_initial_added_data(initial_operations):
  if not initial_operations:
    return []
  else:
    return [dict(operation_dict) for operation_dict in initial_operations]


def _clear_operations_before_load_without_adding_initial_operations(
      added_data_setting, operations_group):
  _clear(operations_group)


def _create_operations_from_added_data(operations):
  for operation_dict in operations["added_data"].value:
    operations.invoke_event("before-add-operation", operation_dict)
    
    operation = _create_operation_by_type(**dict(operation_dict))
    operations["added"].add([operation])
    
    operations.invoke_event("after-add-operation", operation, operation_dict)


def _create_operation_by_type(**kwargs):
  type_ = kwargs.pop("type", "operation")
  
  if type_ not in _OPERATION_TYPES_AND_FUNCTIONS:
    raise ValueError(
      "invalid type '{}'; valid values: {}".format(
        type_, list(_OPERATION_TYPES_AND_FUNCTIONS)))
  
  return _OPERATION_TYPES_AND_FUNCTIONS[type_](**kwargs)


def _get_values_from_operations(added_data_values_setting, added_operations_group):
  added_data_values_setting.reset()
  
  for setting in added_operations_group.walk():
    added_data_values_setting.value[
      setting.get_path(added_operations_group)] = setting.value


def _set_values_for_operations(added_data_values_setting, added_operations_group):
  for setting in added_operations_group.walk():
    if setting.get_path(added_operations_group) in added_data_values_setting.value:
      setting.set_value(
        added_data_values_setting.value[setting.get_path(added_operations_group)])


def _create_operation(
      name,
      function,
      arguments=None,
      enabled=True,
      display_name=None,
      operation_groups=None,
      **custom_fields):
  
  def _set_display_name_for_enabled_gui(setting_enabled, setting_display_name):
    setting_display_name.set_gui(
      gui_type=pgsetting.SettingGuiTypes.check_button_label,
      gui_element=setting_enabled.gui.element)
  
  operation = pgsettinggroup.SettingGroup(
    name,
    tags=["operation"],
    setting_attributes={
      "pdb_type": None,
      "setting_sources": None,
    })
  
  arguments_group = pgsettinggroup.SettingGroup(
    "arguments",
    setting_attributes={
      "pdb_type": None,
      "setting_sources": None,
    })
  
  if arguments:
    arguments_group.add(arguments)
  
  if operation_groups is None:
    operation_groups = [DEFAULT_OPERATIONS_GROUP]
  
  operation.add([
    {
      "type": pgsetting.SettingTypes.generic,
      "name": "function",
      "default_value": function,
      "setting_sources": None,
    },
    arguments_group,
    {
      "type": pgsetting.SettingTypes.boolean,
      "name": "enabled",
      "default_value": enabled,
    },
    {
      "type": pgsetting.SettingTypes.string,
      "name": "display_name",
      "default_value": display_name,
      "gui_type": None,
      "tags": ["ignore_initialize_gui"],
    },
    {
      "type": pgsetting.SettingTypes.generic,
      "name": "operation_groups",
      "default_value": operation_groups,
      "gui_type": None,
    },
  ])
  
  for field_name, field_value in custom_fields.items():
    operation.add([
      {
        "type": pgsetting.SettingTypes.generic,
        "name": field_name,
        "default_value": field_value,
        "gui_type": None,
      },
    ])
  
  operation["enabled"].connect_event(
    "after-set-gui",
    _set_display_name_for_enabled_gui,
    operation["display_name"])
  
  return operation


def _create_constraint(name, function, subfilter=None, **create_operation_kwargs):
  if create_operation_kwargs.get("operation_groups", None) is None:
    create_operation_kwargs["operation_groups"] = [DEFAULT_CONSTRAINTS_GROUP]
  
  constraint = _create_operation(name, function, **create_operation_kwargs)
  
  constraint.tags.add("constraint")
  
  constraint.add([
    {
      "type": pgsetting.SettingTypes.string,
      "name": "subfilter",
      "default_value": subfilter,
      "gui_type": None,
    },
  ])
  
  return constraint


_OPERATION_TYPES_AND_FUNCTIONS = {
  "operation": _create_operation,
  "constraint": _create_constraint
}


def add(operations, operation_dict_or_function):
  """
  Add an operation to the `operations` setting group.
  
  `operation_dict_or_function` can be one of the following:
  * a dictionary - see `create` for more information.
  * a PDB procedure.
  
  Objects of other types passed to `operation_dict_or_function` raise
  `TypeError`.
  
  The same operation can be added multiple times. Each operation will be
  assigned a unique name and display name (e.g. `"autocrop"` and `"Autocrop"`
  for the first operation, `"autocrop_2"` and `"Autocrop (2)"` for the second
  operation, and so on).
  """
  if isinstance(operation_dict_or_function, dict):
    operation_dict = operation_dict_or_function
  else:
    if pgpdb.is_pdb_procedure(operation_dict_or_function):
      operation_dict = _get_operation_dict_for_pdb_procedure(
        operations, operation_dict_or_function)
    else:
      raise TypeError(
        "'{}' is not a valid object - pass a dict or a PDB procedure".format(
          operation_dict_or_function))
  
  operations.invoke_event("before-add-operation", dict(operation_dict))
  
  _uniquify_name_and_display_name(operations, operation_dict)
  
  operation = _create_operation_by_type(**operation_dict)
  
  operations["added"].add([operation])
  operations["added_data"].value.append(dict(operation_dict))
  
  operations.invoke_event("after-add-operation", operation, dict(operation_dict))
  
  return operation


def _get_operation_dict_for_pdb_procedure(operations, pdb_procedure):
  operation_dict = {
    "name": pdb_procedure.proc_name,
    "function": pdb_procedure.proc_name,
    "arguments": [],
    "display_name": pdb_procedure.proc_name,
    "is_pdb_procedure": True,
  }
  
  for pdb_param_type, pdb_param_name, unused_ in pdb_procedure.params:
    setting_type = pgsetting.PDB_TYPES_TO_SETTING_TYPES_MAP[pdb_param_type]
    if isinstance(setting_type, dict):
      arguments_dict = dict(setting_type)
      arguments_dict["name"] = pdb_param_name
      operation_dict["arguments"].append(arguments_dict)
    else:
      operation_dict["arguments"].append({
        "type": setting_type,
        "name": pdb_param_name,
      })
  
  return operation_dict


def _uniquify_name_and_display_name(operations, operation_dict):
  
  def _generate_unique_operation_name():
    i = 2
    while True:
      yield "_{}".format(i)
      i += 1
  
  def _generate_unique_display_name():
    i = 2
    while True:
      yield " ({})".format(i)
      i += 1
  
  operation_dict["name"] = (
    pgpath.uniquify_string(
      operation_dict["name"],
      [operation.name for operation in walk(operations)],
      uniquifier_generator=_generate_unique_operation_name()))
  
  operation_dict["display_name"] = (
    pgpath.uniquify_string(
      operation_dict["display_name"],
      [operation["display_name"].value for operation in walk(operations)],
      uniquifier_generator=_generate_unique_display_name()))


def reorder(operations, operation_name, new_position):
  """
  Modify the position of the added operation given by its name to the new
  position specified as an integer.
  
  A negative position functions as an n-th to last position (-1 for last, -2
  for second to last, etc.).
  
  Raises:
  * `ValueError` - `operation_name` not found in `operations`.
  """
  current_position = _find_index_in_added_data(operations, operation_name)
  
  if current_position is None:
    raise ValueError("operation '{}' not found in operations named '{}'".format(
      operation_name, operations.name))
  
  operation = operations["added"][operation_name]
  
  operations.invoke_event("before-reorder-operation", operation, current_position)
  
  operation_dict = operations["added_data"].value.pop(current_position)
  
  if new_position < 0:
    new_position = max(len(operations["added_data"].value) + new_position + 1, 0)
  
  operations["added_data"].value.insert(new_position, operation_dict)
  
  operations.invoke_event(
    "after-reorder-operation", operation, current_position, new_position)


def remove(operations, operation_name):
  """
  Remove the operation specified by its name from `operations`.
  
  Raises:
  * `ValueError` - `operation_name` not found in `operations`.
  """
  operation_index = _find_index_in_added_data(operations, operation_name)
  
  if operation_index is None:
    raise ValueError("operation '{}' not found in operations named '{}'".format(
      operation_name, operations.name))
  
  operation = operations["added"][operation_name]
  
  operations.invoke_event("before-remove-operation", operation)
  
  operations["added"].remove([operation_name])
  del operations["added_data"].value[operation_index]
  
  operations.invoke_event("after-remove-operation", operation_name)


def _find_index_in_added_data(operations, operation_name):
  return next(
    (index for index, dict_ in enumerate(operations["added_data"].value)
     if dict_["name"] == operation_name),
    None)


def clear(operations):
  """
  Remove all added operations.
  """
  operations.invoke_event("before-clear-operations")
  
  _clear(operations)
  
  operations.invoke_event("after-clear-operations")


def _clear(operations):
  operations["added"].remove([operation.name for operation in walk(operations)])
  operations["added_data"].reset()
  operations["added_data_values"].reset()


def walk(operations, setting_name="operation"):
  """
  Walk (iterate over) a setting group containing operations.
  
  `setting_name` specifies which underlying setting or subgroup of each
  operation is returned. By default, the setting group representing the entire
  operation is returned. For possible values, see `create`. Additional values
  include:
  * `"operation"` - the setting group if the group is an operation or constraint
  * `"constraint"` - the setting group if the group is a constraint
  """
  if setting_name in _OPERATION_TYPES_AND_FUNCTIONS:
    def has_tag(setting):
      return setting_name in setting.tags
    
    include_setting_func = has_tag
  else:
    def matches_setting_name(setting):
      return setting_name == setting.name
    
    include_setting_func = matches_setting_name
  
  def _walk_added_operations():
    listed_operations = {
      (setting.name if setting_name in _OPERATION_TYPES_AND_FUNCTIONS
       else setting.parent.name): setting
      for setting in operations["added"].walk(
        include_setting_func=include_setting_func,
        include_groups=True,
        include_if_parent_skipped=True)}
    
    for operation_dict in operations["added_data"].value:
      operation_name = operation_dict["name"]
      if operation_name in listed_operations:
        yield listed_operations[operation_name]
  
  return _walk_added_operations()
