"""Cedar, a speech equalizer for NVDA."""

import addonHandler
import config
import globalPluginHandler
import gui
import ui
import wx
from logHandler import log
from scriptHandler import script

from . import audiohook, presets
from .engine import BAND_BY_ID, GAIN_LIMIT, conf, equalizer
from .settingsgui import CedarSettingsPanel

try:
	addonHandler.initTranslation()
except Exception:
	pass

GAIN_STEP = 1.0


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: the category Cedar's commands appear under in NVDA's Input Gestures dialog.
	scriptCategory = _("Cedar equalizer")

	def __init__(self):
		super().__init__()
		audiohook.patch()
		gui.NVDASettingsDialog.categoryClasses.append(CedarSettingsPanel)
		config.post_configProfileSwitch.register(self._onConfigChanged)
		config.post_configReset.register(self._onConfigChanged)

	def terminate(self):
		try:
			config.post_configProfileSwitch.unregister(self._onConfigChanged)
			config.post_configReset.unregister(self._onConfigChanged)
		except Exception:
			log.debugWarning("Cedar: could not unregister config handlers", exc_info=True)
		try:
			gui.NVDASettingsDialog.categoryClasses.remove(CedarSettingsPanel)
		except ValueError:
			pass
		audiohook.unpatch()
		super().terminate()

	def _onConfigChanged(self, *args, **kwargs):
		equalizer.invalidate()

	def _adjustBand(self, bandId, delta):
		band = BAND_BY_ID[bandId]
		c = conf()
		value = max(-GAIN_LIMIT, min(GAIN_LIMIT, float(c[band.gainKey]) + delta))
		c[band.gainKey] = value
		c["currentPreset"] = ""
		equalizer.invalidate()
		if value == 0.0:
			# Translators: reported when a band is returned to no boost and no cut. {band} is the band name.
			ui.message(_("{band} flat").format(band=band.label))
		else:
			# Translators: reports a band's new level. {band} is the band name, {gain} the level in decibels.
			ui.message(_("{band} {gain:+.0f} decibels").format(band=band.label, gain=value))

	def _cyclePreset(self, step):
		names = presets.allPresetNames()
		if not names:
			return
		current = conf()["currentPreset"]
		index = names.index(current) + step if current in names else 0
		name = names[index % len(names)]
		presets.applyPreset(name)
		equalizer.invalidate()
		ui.message(name)

	@script(
		# Translators: message presented in input help mode.
		description=_("Toggles the Cedar equalizer on and off"),
		gesture=None,
	)
	def script_toggleCedar(self, gesture):
		c = conf()
		c["enabled"] = not c["enabled"]
		equalizer.invalidate()
		# Translators: reported when the equalizer is switched on or off.
		ui.message(_("Cedar on") if c["enabled"] else _("Cedar off"))

	@script(
		# Translators: message presented in input help mode.
		description=_("Selects the next Cedar preset"),
		gesture=None,
	)
	def script_nextPreset(self, gesture):
		self._cyclePreset(1)

	@script(
		# Translators: message presented in input help mode.
		description=_("Selects the previous Cedar preset"),
		gesture=None,
	)
	def script_previousPreset(self, gesture):
		self._cyclePreset(-1)

	@script(
		# Translators: message presented in input help mode.
		description=_("Increases the bass"),
		gesture=None,
	)
	def script_bassUp(self, gesture):
		self._adjustBand("low", GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Decreases the bass"),
		gesture=None,
	)
	def script_bassDown(self, gesture):
		self._adjustBand("low", -GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Increases the mids"),
		gesture=None,
	)
	def script_midsUp(self, gesture):
		self._adjustBand("mid", GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Decreases the mids"),
		gesture=None,
	)
	def script_midsDown(self, gesture):
		self._adjustBand("mid", -GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Increases the treble"),
		gesture=None,
	)
	def script_trebleUp(self, gesture):
		self._adjustBand("high", GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Decreases the treble"),
		gesture=None,
	)
	def script_trebleDown(self, gesture):
		self._adjustBand("high", -GAIN_STEP)

	@script(
		# Translators: message presented in input help mode.
		description=_("Opens the Cedar equalizer settings"),
		gesture=None,
	)
	def script_openSettings(self, gesture):
		wx.CallAfter(gui.mainFrame.popupSettingsDialog, gui.NVDASettingsDialog, CedarSettingsPanel)
