"""Built in and user saved equalizer presets."""

import json

import addonHandler
from logHandler import log

from .engine import BANDS, conf

try:
	addonHandler.initTranslation()
except Exception:
	pass

# Every preset stores only what it changes; anything absent falls back to the band's design value.
BUILTIN_PRESETS = (
	(_("Flat"), {}),
	(_("Clarity"), {"lowGain": -2.0, "lowMidGain": -4.0, "midGain": 1.0, "presenceGain": 5.0, "highGain": 3.0}),
	(_("Warm"), {"lowGain": 5.0, "lowMidGain": 2.0, "presenceGain": -3.0, "highGain": -2.0}),
	(_("Bright"), {"lowGain": -2.0, "midGain": 1.0, "presenceGain": 4.0, "highGain": 6.0}),
	(_("Bass boost"), {"lowGain": 8.0, "lowMidGain": 1.0}),
	(_("Less sibilance"), {"presenceFreq": 6500.0, "presenceGain": -5.0, "presenceQ": 2.0, "highGain": -4.0}),
	(_("Small speakers"), {
		"rumbleFilter": True, "rumbleFreq": 180.0,
		"lowGain": -4.0, "midGain": 3.0, "presenceGain": 5.0, "highGain": 2.0,
	}),
	(_("Podcast voice"), {"lowGain": 4.0, "lowMidGain": -3.0, "presenceGain": 3.0, "highGain": 1.0}),
	(_("Telephone"), {
		"rumbleFilter": True, "rumbleFreq": 300.0,
		"hissFilter": True, "hissFreq": 3400.0,
		"midGain": 5.0,
	}),
	(_("Noisy room"), {"lowGain": -6.0, "lowMidGain": -3.0, "midGain": 2.0, "presenceGain": 6.0, "highGain": 2.0}),
)

# The keys a preset is allowed to carry, so a malformed saved preset cannot poke at unrelated settings.
PRESET_KEYS = {"preamp", "rumbleFilter", "rumbleFreq", "hissFilter", "hissFreq"}
for _band in BANDS:
	PRESET_KEYS.update((_band.gainKey, _band.freqKey, _band.qKey))


def loadUserPresets():
	raw = conf()["userPresets"]
	if not raw:
		return {}
	try:
		data = json.loads(raw)
	except ValueError:
		log.warning("Cedar: user presets could not be read, ignoring them")
		return {}
	if not isinstance(data, dict):
		return {}
	return {name: {k: v for k, v in values.items() if k in PRESET_KEYS} for name, values in data.items() if isinstance(values, dict)}


def saveUserPresets(presets):
	conf()["userPresets"] = json.dumps(presets) if presets else ""


def allPresetNames():
	builtin = [name for name, _values in BUILTIN_PRESETS]
	return builtin + sorted(loadUserPresets())


def getPreset(name):
	for presetName, values in BUILTIN_PRESETS:
		if presetName == name:
			return values
	return loadUserPresets().get(name)


def isBuiltin(name):
	return any(presetName == name for presetName, _values in BUILTIN_PRESETS)


def captureCurrent():
	"""Snapshot the settings a preset covers, so the user can save what they are hearing."""
	c = conf()
	return {key: c[key] for key in sorted(PRESET_KEYS)}


def applyPreset(name):
	"""Write a preset into the config, resetting anything the preset does not mention."""
	values = getPreset(name)
	if values is None:
		return False
	c = conf()
	c["preamp"] = 0.0
	c["rumbleFilter"] = False
	c["hissFilter"] = False
	for band in BANDS:
		c[band.gainKey] = 0.0
		c[band.freqKey] = band.defaultFreq
		c[band.qKey] = band.defaultQ
	for key, value in values.items():
		if key in PRESET_KEYS:
			c[key] = value
	c["currentPreset"] = name
	return True
