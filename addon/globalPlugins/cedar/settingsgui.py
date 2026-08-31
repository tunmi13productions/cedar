"""Settings panel and advanced dialog for Cedar."""

import addonHandler
import ui
import wx
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel

try:
	from gui.message import messageBox
except ImportError:
	from gui import messageBox

from . import presets
from .engine import BANDS, GAIN_LIMIT, PREAMP_LIMIT, conf, equalizer, resetToFlat

try:
	addonHandler.initTranslation()
except Exception:
	pass

# Translators: shown in the preset list when the settings do not match any saved preset.
CUSTOM_LABEL = _("(Custom)")

# Translators: the sentence spoken by the Test voice button so settings can be judged by ear.
SAMPLE_TEXT = _("The quick brown fox jumps over the lazy dog. Cedar is shaping this voice right now.")


def _snapshotConfig():
	c = conf()
	return {key: c[key] for key in c}


def _restoreConfig(snapshot):
	c = conf()
	for key, value in snapshot.items():
		c[key] = value
	equalizer.invalidate()


# Width steps offered per band type, as (value, name) pairs. Shelves read the value as a slope.
SHELF_WIDTHS = (
	(0.3, _("Gentle")),
	(0.5, _("Moderate")),
	(0.7, _("Standard")),
	(1.0, _("Steep")),
)
PEAK_WIDTHS = (
	(0.4, _("Very wide")),
	(0.7, _("Wide")),
	(1.0, _("Medium")),
	(1.4, _("Narrow")),
	(2.0, _("Very narrow")),
	(3.0, _("Extremely narrow")),
)


def _setSpinStep(ctrl, step):
	"""A settable spin increment only exists in newer wxWidgets, so treat it as a bonus."""
	try:
		ctrl.SetIncrement(step)
	except Exception:
		pass


class AdvancedDialog(wx.Dialog):
	"""Per band frequency and width controls, plus the filters most users never need."""

	def __init__(self, parent):
		# Translators: title of the Cedar advanced settings dialog.
		super().__init__(parent, title=_("Cedar advanced settings"))
		self._snapshot = _snapshotConfig()
		self._loading = False
		c = conf()

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		sHelper = guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)

		# Translators: chooses which band the frequency and width controls below apply to.
		self.bandChoice = sHelper.addLabeledControl(_("&Band:"), wx.Choice, choices=[b.label for b in BANDS])
		self.bandChoice.SetSelection(0)
		self.bandChoice.Bind(wx.EVT_CHOICE, self.onBandChanged)

		# Translators: how much the selected band boosts or cuts, in decibels.
		self.gainSlider = sHelper.addLabeledControl(
			_("&Gain (dB):"), wx.Slider,
			value=0, minValue=-int(GAIN_LIMIT), maxValue=int(GAIN_LIMIT),
		)
		self.gainSlider.SetLineSize(1)
		self.gainSlider.SetPageSize(3)
		self.gainSlider.Bind(wx.EVT_SLIDER, self.onBandValueChanged)

		# Translators: the centre frequency of a peaking band, or the corner frequency of a shelf.
		self.freqCtrl = sHelper.addLabeledControl(
			_("&Frequency (Hz):"), wx.SpinCtrl, min=20, max=16000, initial=1000,
		)
		self.freqCtrl.Bind(wx.EVT_SPINCTRL, self.onBandValueChanged)

		# Translators: how wide a peaking band is, or how steep a shelf is.
		self.widthChoice = sHelper.addLabeledControl(_("&Width or slope:"), wx.Choice, choices=[])
		self.widthChoice.Bind(wx.EVT_CHOICE, self.onBandValueChanged)

		# Translators: removes very low frequency rumble from speech.
		self.rumbleCheckBox = sHelper.addItem(wx.CheckBox(self, label=_("Remove low frequency &rumble")))
		self.rumbleCheckBox.SetValue(c["rumbleFilter"])
		self.rumbleCheckBox.Bind(wx.EVT_CHECKBOX, self.onGlobalChanged)
		# Translators: the cutoff frequency of the rumble filter.
		self.rumbleFreqCtrl = sHelper.addLabeledControl(
			_("R&umble filter cutoff (Hz):"), wx.SpinCtrl,
			min=20, max=400, initial=int(round(c["rumbleFreq"])),
		)
		_setSpinStep(self.rumbleFreqCtrl, 5)
		self.rumbleFreqCtrl.Bind(wx.EVT_SPINCTRL, self.onGlobalChanged)

		# Translators: removes high frequency hiss from speech.
		self.hissCheckBox = sHelper.addItem(wx.CheckBox(self, label=_("Remove high frequency &hiss")))
		self.hissCheckBox.SetValue(c["hissFilter"])
		self.hissCheckBox.Bind(wx.EVT_CHECKBOX, self.onGlobalChanged)
		# Translators: the cutoff frequency of the hiss filter.
		self.hissFreqCtrl = sHelper.addLabeledControl(
			_("&Hiss filter cutoff (Hz):"), wx.SpinCtrl,
			min=2000, max=16000, initial=int(round(c["hissFreq"])),
		)
		_setSpinStep(self.hissFreqCtrl, 100)
		self.hissFreqCtrl.Bind(wx.EVT_SPINCTRL, self.onGlobalChanged)

		# Translators: rounds off loud peaks instead of letting them distort.
		self.softClipCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("&Soften loud peaks instead of clipping them"))
		)
		self.softClipCheckBox.SetValue(c["softClip"])
		self.softClipCheckBox.Bind(wx.EVT_CHECKBOX, self.onGlobalChanged)

		# Translators: applies the equalizer to NVDA's beeps and sounds as well as to speech.
		self.soundsCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("Also equalize NVDA s&ounds and beeps"))
		)
		self.soundsCheckBox.SetValue(c["processSounds"])
		self.soundsCheckBox.Bind(wx.EVT_CHECKBOX, self.onGlobalChanged)

		mainSizer.Add(sHelper.sizer, border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL)
		mainSizer.Add(
			self.CreateButtonSizer(wx.OK | wx.CANCEL),
			border=guiHelper.BORDER_FOR_DIALOGS, flag=wx.ALL | wx.ALIGN_RIGHT,
		)
		mainSizer.Fit(self)
		self.SetSizer(mainSizer)
		self.Bind(wx.EVT_BUTTON, self.onCancel, id=wx.ID_CANCEL)
		self._loadBand()
		self.bandChoice.SetFocus()

	def _currentBand(self):
		return BANDS[max(0, self.bandChoice.GetSelection())]

	def _loadBand(self):
		band = self._currentBand()
		c = conf()
		self._loading = True
		try:
			self.gainSlider.SetValue(int(round(c[band.gainKey])))
			self.freqCtrl.SetRange(int(band.minFreq), int(band.maxFreq))
			_setSpinStep(self.freqCtrl, 5 if band.maxFreq <= 1500 else 25)
			self.freqCtrl.SetValue(int(round(c[band.freqKey])))
			self._loadWidths(band, float(c[band.qKey]))
		finally:
			self._loading = False

	def _loadWidths(self, band, current):
		options = list(SHELF_WIDTHS if band.isShelf else PEAK_WIDTHS)
		if not any(abs(value - current) < 0.005 for value, _name in options):
			# Keeps a value set outside this dialog from being replaced by the nearest offered step.
			# Translators: the width list entry for a value that is not one of the offered steps.
			options.append((current, _("Custom")))
			options.sort()
		self._widthValues = [value for value, _name in options]
		self.widthChoice.Set(["%s (%.2f)" % (name, value) for value, name in options])
		closest = min(range(len(self._widthValues)), key=lambda i: abs(self._widthValues[i] - current))
		self.widthChoice.SetSelection(closest)

	def onBandChanged(self, evt):
		evt.Skip()
		self._loadBand()

	def onBandValueChanged(self, evt):
		evt.Skip()
		if self._loading:
			return
		band = self._currentBand()
		c = conf()
		c[band.gainKey] = float(self.gainSlider.GetValue())
		c[band.freqKey] = float(self.freqCtrl.GetValue())
		selection = self.widthChoice.GetSelection()
		if selection != wx.NOT_FOUND:
			c[band.qKey] = self._widthValues[selection]
		c["currentPreset"] = ""
		equalizer.invalidate()

	def onGlobalChanged(self, evt):
		evt.Skip()
		c = conf()
		c["rumbleFilter"] = self.rumbleCheckBox.GetValue()
		c["rumbleFreq"] = float(self.rumbleFreqCtrl.GetValue())
		c["hissFilter"] = self.hissCheckBox.GetValue()
		c["hissFreq"] = float(self.hissFreqCtrl.GetValue())
		c["softClip"] = self.softClipCheckBox.GetValue()
		c["processSounds"] = self.soundsCheckBox.GetValue()
		c["currentPreset"] = ""
		equalizer.invalidate()

	def onCancel(self, evt):
		_restoreConfig(self._snapshot)
		evt.Skip()


class CedarSettingsPanel(SettingsPanel):
	# Translators: the name of the Cedar category in NVDA's settings dialog.
	title = _("Cedar equalizer")

	def makeSettings(self, settingsSizer):
		self._snapshot = _snapshotConfig()
		c = conf()
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: turns the whole equalizer on or off.
		self.enabledCheckBox = sHelper.addItem(wx.CheckBox(self, label=_("&Enable the Cedar equalizer")))
		self.enabledCheckBox.SetValue(c["enabled"])
		self.enabledCheckBox.Bind(wx.EVT_CHECKBOX, self.onEnabledChanged)

		# Translators: chooses a saved set of equalizer settings.
		self.presetChoice = sHelper.addLabeledControl(_("&Preset:"), wx.Choice, choices=self._presetChoices())
		self.presetChoice.Bind(wx.EVT_CHOICE, self.onPresetChosen)

		self.gainSliders = {}
		for band in BANDS:
			if not band.basic:
				continue
			# Translators: a boost or cut slider for one equalizer band, in decibels.
			slider = sHelper.addLabeledControl(
				_("%s (dB):") % band.label, wx.Slider,
				value=int(round(c[band.gainKey])),
				minValue=-int(GAIN_LIMIT), maxValue=int(GAIN_LIMIT),
			)
			slider.SetLineSize(1)
			slider.SetPageSize(3)
			slider.Bind(wx.EVT_SLIDER, self.onSliderChanged)
			self.gainSliders[band.id] = slider

		# Translators: overall level applied before the equalizer.
		self.preampSlider = sHelper.addLabeledControl(
			_("Overall &volume trim (dB):"), wx.Slider,
			value=int(round(c["preamp"])),
			minValue=-int(PREAMP_LIMIT), maxValue=int(PREAMP_LIMIT),
		)
		self.preampSlider.SetLineSize(1)
		self.preampSlider.SetPageSize(3)
		self.preampSlider.Bind(wx.EVT_SLIDER, self.onSliderChanged)

		# Translators: automatically lowers the level so boosted bands do not distort.
		self.autoGainCheckBox = sHelper.addItem(
			wx.CheckBox(self, label=_("&Prevent distortion from boosted bands"))
		)
		self.autoGainCheckBox.SetValue(c["autoGain"])
		self.autoGainCheckBox.Bind(wx.EVT_CHECKBOX, self.onSliderChanged)

		buttonHelper = guiHelper.ButtonHelper(wx.HORIZONTAL)
		# Translators: speaks a sample sentence so the current settings can be judged by ear.
		testButton = buttonHelper.addButton(self, label=_("&Test voice"))
		testButton.Bind(wx.EVT_BUTTON, self.onTest)
		# Translators: stores the current settings under a name of the user's choosing.
		saveButton = buttonHelper.addButton(self, label=_("&Save as preset..."))
		saveButton.Bind(wx.EVT_BUTTON, self.onSavePreset)
		# Translators: removes a preset the user previously saved.
		self.deleteButton = buttonHelper.addButton(self, label=_("&Delete preset"))
		self.deleteButton.Bind(wx.EVT_BUTTON, self.onDeletePreset)
		# Translators: returns every band to no boost and no cut.
		resetButton = buttonHelper.addButton(self, label=_("&Reset to flat"))
		resetButton.Bind(wx.EVT_BUTTON, self.onReset)
		sHelper.addItem(buttonHelper.sizer)

		# Translators: unlocks the per band frequency and width controls.
		self.advancedCheckBox = sHelper.addItem(wx.CheckBox(self, label=_("Enable &advanced settings")))
		self.advancedCheckBox.SetValue(c["advancedMode"])
		self.advancedCheckBox.Bind(wx.EVT_CHECKBOX, self.onAdvancedToggled)
		# Translators: opens the advanced settings dialog.
		self.advancedButton = sHelper.addItem(wx.Button(self, label=_("Advanced se&ttings...")))
		self.advancedButton.Bind(wx.EVT_BUTTON, self.onAdvanced)

		self._selectPresetInList()

	def _presetChoices(self):
		return [CUSTOM_LABEL] + presets.allPresetNames()

	def _selectPresetInList(self):
		name = conf()["currentPreset"]
		index = self.presetChoice.FindString(name) if name else wx.NOT_FOUND
		self.presetChoice.SetSelection(0 if index == wx.NOT_FOUND else index)
		self._refreshEnabledStates()

	def _refreshEnabledStates(self):
		enabled = self.enabledCheckBox.GetValue()
		for slider in self.gainSliders.values():
			slider.Enable(enabled)
		self.preampSlider.Enable(enabled)
		self.autoGainCheckBox.Enable(enabled)
		self.advancedButton.Enable(enabled and self.advancedCheckBox.GetValue())
		selection = self.presetChoice.GetStringSelection()
		self.deleteButton.Enable(
			bool(selection) and selection != CUSTOM_LABEL and not presets.isBuiltin(selection)
		)

	def _writeSliders(self):
		c = conf()
		for bandId, slider in self.gainSliders.items():
			c["%sGain" % bandId] = float(slider.GetValue())
		c["preamp"] = float(self.preampSlider.GetValue())
		c["autoGain"] = self.autoGainCheckBox.GetValue()
		equalizer.invalidate()

	def _readSlidersFromConfig(self):
		c = conf()
		for bandId, slider in self.gainSliders.items():
			slider.SetValue(int(round(c["%sGain" % bandId])))
		self.preampSlider.SetValue(int(round(c["preamp"])))
		self.autoGainCheckBox.SetValue(c["autoGain"])

	def onEnabledChanged(self, evt):
		evt.Skip()
		conf()["enabled"] = self.enabledCheckBox.GetValue()
		equalizer.invalidate()
		self._refreshEnabledStates()

	def onSliderChanged(self, evt):
		evt.Skip()
		self._writeSliders()
		conf()["currentPreset"] = ""
		self.presetChoice.SetSelection(0)
		self._refreshEnabledStates()

	def onPresetChosen(self, evt):
		evt.Skip()
		name = self.presetChoice.GetStringSelection()
		if name == CUSTOM_LABEL:
			return
		presets.applyPreset(name)
		equalizer.invalidate()
		self._readSlidersFromConfig()
		self._refreshEnabledStates()

	def onReset(self, evt):
		resetToFlat()
		equalizer.invalidate()
		self._readSlidersFromConfig()
		self._selectPresetInList()

	def onTest(self, evt):
		ui.message(SAMPLE_TEXT)

	def onSavePreset(self, evt):
		# Translators: prompt for the name to store the current equalizer settings under.
		with wx.TextEntryDialog(self, _("Preset name:"), _("Save Cedar preset")) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			name = dialog.GetValue().strip()
		if not name or name == CUSTOM_LABEL:
			return
		if presets.isBuiltin(name):
			messageBox(
				# Translators: reported when the user tries to overwrite a preset that ships with Cedar.
				_("%s is a built in preset. Please choose a different name.") % name,
				_("Cedar"), wx.OK | wx.ICON_ERROR, self,
			)
			return
		userPresets = presets.loadUserPresets()
		if name in userPresets and messageBox(
			# Translators: asks whether to replace a preset that already exists.
			_("A preset called %s already exists. Replace it?") % name,
			_("Cedar"), wx.YES_NO | wx.ICON_QUESTION, self,
		) != wx.YES:
			return
		userPresets[name] = presets.captureCurrent()
		presets.saveUserPresets(userPresets)
		conf()["currentPreset"] = name
		self.presetChoice.Set(self._presetChoices())
		self._selectPresetInList()

	def onDeletePreset(self, evt):
		name = self.presetChoice.GetStringSelection()
		userPresets = presets.loadUserPresets()
		if name not in userPresets:
			return
		if messageBox(
			# Translators: asks the user to confirm deleting one of their saved presets.
			_("Delete the preset %s?") % name,
			_("Cedar"), wx.YES_NO | wx.ICON_QUESTION, self,
		) != wx.YES:
			return
		del userPresets[name]
		presets.saveUserPresets(userPresets)
		conf()["currentPreset"] = ""
		self.presetChoice.Set(self._presetChoices())
		self._selectPresetInList()

	def onAdvancedToggled(self, evt):
		evt.Skip()
		conf()["advancedMode"] = self.advancedCheckBox.GetValue()
		self._refreshEnabledStates()

	def onAdvanced(self, evt):
		with AdvancedDialog(self) as dialog:
			dialog.ShowModal()
		self._readSlidersFromConfig()
		self._selectPresetInList()

	def onSave(self):
		self._writeSliders()
		c = conf()
		c["enabled"] = self.enabledCheckBox.GetValue()
		c["advancedMode"] = self.advancedCheckBox.GetValue()
		equalizer.invalidate()

	def onDiscard(self):
		_restoreConfig(self._snapshot)
