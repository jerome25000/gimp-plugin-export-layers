#! /usr/bin/env python
#
# Export Layers - GIMP plug-in that exports layers as separate images
#
# Copyright (C) 2013-2015 khalim19 <khalim19@gmail.com>
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
# along with Export Layers.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

str = unicode

from export_layers import constants

import gettext
gettext.install(constants.DOMAIN_NAME, constants.LOCALE_PATH, unicode=True)

from export_layers import log_output
log_output.log_output(constants.DEBUG)

import os

try:
  # Disable overlay scrolling (notably used in Ubuntu) to be consistent with the
  # Export menu.
  os.environ['LIBOVERLAY_SCROLLBAR'] = "0"
except Exception:
  pass

import gimp
import gimpenums

import export_layers.pygimplib as pygimplib

from export_layers.pygimplib import pgsettinggroup
from export_layers.pygimplib import pgsettingpersistor

from export_layers import exportlayers
from export_layers import gui_plugin
from export_layers import settings_plugin

#===============================================================================


pygimplib.config.PLUGIN_NAME = "export_layers"
 
pygimplib.config.LOCALE_PATH = os.path.join(
  pygimplib.config.PLUGINS_DIRECTORY, pygimplib.config.PLUGIN_NAME, "locale")
pygimplib.config.DOMAIN_NAME = "gimp-" + pygimplib.config.PLUGIN_NAME.replace("_", "-")
 
pygimplib.config.PLUGIN_VERSION = "2.5"
pygimplib.config.BUG_REPORT_URI_LIST = [
  # ("GIMP Plugin Registry", "http://registry.gimp.org/node/28268"),
  ("GitHub", "https://github.com/khalim19/gimp-plugin-export-layers/issues")
]
pygimplib.config.DEBUG = pygimplib.DEBUG_NONE

# If True, display each step of image/layer editing in GIMP.
pygimplib.config.DEBUG_IMAGE_PROCESSING = False


class ExportLayersPlugin(pygimplib.GimpPlugin):
  
  def __init__(self):
    self.session_source = pgsettingpersistor.SessionPersistentSettingSource(constants.SESSION_SOURCE_NAME)
    self.persistent_source = pgsettingpersistor.PersistentSettingSource(constants.PERSISTENT_SOURCE_NAME)
    pygimplib.GimpPlugin.__init__(self)
    
    self.settings = settings_plugin.create_settings()
  
  def init_additional_config(self):
    pygimplib.config.PLUGIN_TITLE = _("Export Layers")
  
  def query(self):
    gimp.domain_register(constants.DOMAIN_NAME, constants.LOCALE_PATH)
    
    gimp.install_procedure(
      "plug_in_export_layers",
      _("Export layers as separate images"),
      "",
      "khalim19 <khalim19@gmail.com>",
      "khalim19",
      "2013",
      _("E_xport Layers..."),
      "*",
      gimpenums.PLUGIN,
      pgsettinggroup.PdbParamCreator.create_params(self.settings['special'], self.settings['main']),
      []
    )
    gimp.menu_register("plug_in_export_layers", "<Image>/File/Export")
    
    gimp.install_procedure(
      "plug_in_export_layers_repeat",
      _("Run \"{0}\" with the last values specified").format(constants.PLUGIN_TITLE),
      _("If the plug-in is run for the first time (i.e. no last values exist), "
        "default values will be used."),
      "khalim19 <khalim19@gmail.com>",
      "khalim19",
      "2013",
      _("E_xport Layers (repeat)"),
      "*",
      gimpenums.PLUGIN,
      pgsettinggroup.PdbParamCreator.create_params(self.settings['special'], self.settings['main']),
      []
    )
    gimp.menu_register("plug_in_export_layers_repeat", "<Image>/File/Export")
  
  def plug_in_export_layers(self, run_mode, image, *args):
    self.settings['special']['run_mode'].set_value(run_mode)
    self.settings['special']['image'].set_value(image)
    
    if run_mode == gimpenums.RUN_INTERACTIVE:
      self._run_export_layers_interactive(image)
    elif run_mode == gimpenums.RUN_WITH_LAST_VALS:
      self._run_with_last_vals(image)
    else:
      self._run_noninteractive(image, args)
  
  def plug_in_export_layers_repeat(self, run_mode, image):
    if run_mode == gimpenums.RUN_INTERACTIVE:
      pgsettingpersistor.SettingPersistor.load(
        [self.settings['special']['first_plugin_run']], [self.session_source])
      if self.settings['special']['first_plugin_run'].value:
        self._run_export_layers_interactive(image)
      else:
        self._run_export_layers_repeat_interactive(image)
    else:
      self._run_with_last_vals(image)
  
  def _run_noninteractive(self, image, args):
    for setting, arg in zip(self.settings['main'], args):
      if isinstance(arg, bytes):
        arg = arg.decode()
      setting.set_value(arg)
    
    self._run_plugin_noninteractive(gimpenums.RUN_NONINTERACTIVE, image)
  
  def _run_with_last_vals(self, image):
    status, status_message = pgsettingpersistor.SettingPersistor.load(
      [self.settings['main']], [self.session_source, self.persistent_source])
    if status == pgsettingpersistor.SettingPersistor.READ_FAIL:
      print(status_message)
    
    self._run_plugin_noninteractive(gimpenums.RUN_WITH_LAST_VALS, image)
  
  def _run_export_layers_interactive(self, image):
    gui_plugin.export_layers_gui(image, self.settings, self.session_source, self.persistent_source)
  
  def _run_export_layers_repeat_interactive(self, image):
    gui_plugin.export_layers_repeat_gui(image, self.settings, self.session_source, self.persistent_source)
  
  def _run_plugin_noninteractive(self, run_mode, image):
    layer_exporter = exportlayers.LayerExporter(run_mode, image, self.settings['main'])
    
    try:
      layer_exporter.export_layers()
    except exportlayers.ExportLayersCancelError as e:
      print(str(e))
    except exportlayers.ExportLayersError as e:
      print(str(e))
      raise


#===============================================================================

if __name__ == "__main__":
  ExportLayersPlugin().start()
