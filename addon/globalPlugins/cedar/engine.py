"""Configuration schema and compilation of settings into a runnable filter cascade."""

import json
import threading

import addonHandler
import config
from logHandler import log

from . import dsp

try:
	addonHandler.initTranslation()
except Exception:
	pass

CONFIG_SECTION = "cedar"


class BandDef:
	"""One fixed slot in the equalizer, described once and reused by the config and the GUI."""

	__slots__ = ("id", "filterType", "label", "defaultFreq", "defaultQ", "minFreq", "maxFreq", "basic")

	def __init__(self, id, filterType, label, defaultFreq, defaultQ, minFreq, maxFreq, basic):
		self.id = id
		self.filterType = filterType
		self.label = label
		self.defaultFreq = defaultFreq
		self.defaultQ = defaultQ
		self.minFreq = minFreq
		self.maxFreq = maxFreq
		self.basic = basic

	@property
	def isShelf(self):
		return self.filterType in (dsp.LOW_SHELF, dsp.HIGH_SHELF)

	@property
	def gainKey(self):
		return "%sGain" % self.id

	@property
	def freqKey(self):
		return "%sFreq" % self.id

	@property
	def qKey(self):
		return "%sQ" % self.id


# The two shelves read their width control as a slope; the three peaking bands read it as a Q.
BANDS = (
	BandDef("low", dsp.LOW_SHELF, _("Bass"), 150.0, 0.7, 40.0, 600.0, True),
	BandDef("lowMid", dsp.PEAKING, _("Low mid"), 400.0, 1.0, 100.0, 1200.0, False),
	BandDef("mid", dsp.PEAKING, _("Mids"), 1200.0, 0.8, 300.0, 4000.0, True),
	BandDef("presence", dsp.PEAKING, _("Presence"), 3200.0, 1.2, 1500.0, 9000.0, False),
	BandDef("high", dsp.HIGH_SHELF, _("Treble"), 5000.0, 0.7, 2000.0, 14000.0, True),
)

BAND_BY_ID = {b.id: b for b in BANDS}

GAIN_LIMIT = 18.0
PREAMP_LIMIT = 12.0


def usesPercentScale():
	return conf()["percentScale"]


def displayRange(limit):
	"""The range a level control should offer for a gain of plus or minus limit decibels."""
	if usesPercentScale():
		return 0, 100
	return -int(limit), int(limit)


def displayFromDb(db, limit):
	"""Show a gain on the scale the user reads, where the middle of the range is flat."""
	if not usesPercentScale():
		return int(round(db))
	return int(round((db + limit) / (2.0 * limit) * 100.0))


def dbFromDisplay(value, limit):
	if not usesPercentScale():
		return float(value)
	return value / 100.0 * (2.0 * limit) - limit

confspec = {
	"enabled": "boolean(default=True)",
	"processSounds": "boolean(default=False)",
	"advancedMode": "boolean(default=False)",
	"percentScale": "boolean(default=True)",
	"preamp": "float(default=0.0, min=-%s, max=%s)" % (PREAMP_LIMIT, PREAMP_LIMIT),
	"autoGain": "boolean(default=True)",
	"softClip": "boolean(default=True)",
	"rumbleFilter": "boolean(default=False)",
	"rumbleFreq": "float(default=80.0, min=20.0, max=400.0)",
	"hissFilter": "boolean(default=False)",
	"hissFreq": "float(default=9000.0, min=2000.0, max=16000.0)",
	"currentPreset": 'string(default="")',
	"userPresets": 'string(default="")',
	"synthSettings": 'string(default="")',
}
for _band in BANDS:
	confspec[_band.gainKey] = "float(default=0.0, min=-%s, max=%s)" % (GAIN_LIMIT, GAIN_LIMIT)
	confspec[_band.freqKey] = "float(default=%s, min=%s, max=%s)" % (_band.defaultFreq, _band.minFreq, _band.maxFreq)
	confspec[_band.qKey] = "float(default=%s, min=0.1, max=%s)" % (
		_band.defaultQ, 1.0 if _band.isShelf else 10.0
	)


# The settings that shape the sound, which a synthesizer can keep its own copy of. Everything else,
# such as whether Cedar is on or how levels read, is shared by every synthesizer.
SYNTH_KEYS = {"preamp", "autoGain", "softClip", "rumbleFilter", "rumbleFreq", "hissFilter", "hissFreq", "currentPreset"}
for _band in BANDS:
	SYNTH_KEYS.update((_band.gainKey, _band.freqKey, _band.qKey))


def registerConfig():
	config.conf.spec[CONFIG_SECTION] = confspec


def rawConf():
	"""The config section itself, ignoring any synthesizer's own settings."""
	return config.conf[CONFIG_SECTION]


# Stands for whichever synthesizer is running, where None means the shared settings.
ACTIVE = object()

# NVDA's No speech driver makes no audio, so it is never offered settings of its own.
SILENCE_SYNTH = "silence"


def activeSynth():
	try:
		import synthDriverHandler

		return synthDriverHandler.getSynth()
	except Exception:
		return None


def activeSynthName():
	name = getattr(activeSynth(), "name", None)
	return None if name == SILENCE_SYNTH else name


def activeSynthDescription():
	synth = activeSynth()
	return getattr(synth, "description", None) or getattr(synth, "name", None)


def installedSynths():
	"""(name, description) for every synthesizer NVDA can load, as its own synthesizer dialog lists them."""
	try:
		import synthDriverHandler

		return [(name, description) for name, description in synthDriverHandler.getSynthList() if name != SILENCE_SYNTH]
	except Exception:
		name = activeSynthName()
		return [(name, activeSynthDescription())] if name else []


_parsedSynthSettings = (None, {})


def _sameKind(value, default):
	if isinstance(default, bool):
		return isinstance(value, bool)
	if isinstance(default, float):
		return isinstance(value, (int, float)) and not isinstance(value, bool)
	return isinstance(value, str)


def loadSynthSettings():
	"""Every synthesizer's own settings, keyed by driver name, with anything malformed dropped."""
	global _parsedSynthSettings
	raw = rawConf()["synthSettings"]
	if raw == _parsedSynthSettings[0]:
		return _parsedSynthSettings[1]
	result = {}
	if raw:
		try:
			data = json.loads(raw)
		except ValueError:
			log.warning("Cedar: per synthesizer settings could not be read, ignoring them")
			data = {}
		section = rawConf()
		if isinstance(data, dict):
			for name, values in data.items():
				if isinstance(values, dict) and name != SILENCE_SYNTH:
					result[name] = {
						k: v for k, v in values.items() if k in SYNTH_KEYS and _sameKind(v, section[k])
					}
	_parsedSynthSettings = (raw, result)
	return result


def saveSynthSettings(settings):
	rawConf()["synthSettings"] = json.dumps(settings, sort_keys=True) if settings else ""


def _resolve(name):
	return activeSynthName() if name is ACTIVE else name


def synthHasOwnSettings(name=ACTIVE):
	name = _resolve(name)
	return name is not None and name in loadSynthSettings()


def setSynthHasOwnSettings(own, name=ACTIVE):
	"""Give a synthesizer its own copy of the current settings, or drop it back onto the shared ones."""
	name = _resolve(name)
	if name is None:
		return
	settings = dict(loadSynthSettings())
	if own:
		if name not in settings:
			# Starts from what that synthesizer plays now, so ticking the box changes nothing you can hear.
			current = conf(name)
			settings[name] = {key: current[key] for key in sorted(SYNTH_KEYS)}
	else:
		settings.pop(name, None)
	saveSynthSettings(settings)


class Settings:
	"""Cedar's settings as one synthesizer sees them, the active one unless told otherwise.

	Sound shaping keys read and write that synthesizer's own copy when it has one, and the shared
	config otherwise. Every other key always goes straight to the config.
	"""

	def __init__(self, section, synthName=ACTIVE):
		self._section = section
		self._synthName = synthName

	def _own(self):
		name = _resolve(self._synthName)
		if name is None:
			return None
		return loadSynthSettings().get(name)

	def __getitem__(self, key):
		if key in SYNTH_KEYS:
			own = self._own()
			if own is not None and key in own:
				return own[key]
		return self._section[key]

	def __setitem__(self, key, value):
		if key in SYNTH_KEYS:
			name = _resolve(self._synthName)
			settings = loadSynthSettings()
			if name in settings:
				settings = dict(settings)
				settings[name] = dict(settings[name], **{key: value})
				saveSynthSettings(settings)
				return
		self._section[key] = value

	def __iter__(self):
		return iter(self._section)

	def __contains__(self, key):
		return key in self._section


def conf(synthName=ACTIVE):
	return Settings(rawConf(), synthName)


def resetToFlat(c=None):
	"""Zero every gain and return every band to its designed frequency and width."""
	c = conf() if c is None else c
	c["preamp"] = 0.0
	c["rumbleFilter"] = False
	c["hissFilter"] = False
	for band in BANDS:
		c[band.gainKey] = 0.0
		c[band.freqKey] = band.defaultFreq
		c[band.qKey] = band.defaultQ
	c["currentPreset"] = ""


_MISSING = object()


class Engine:
	"""Turns the current settings into per sample rate cascades, rebuilding only when they change."""

	def __init__(self):
		self._lock = threading.Lock()
		self._cache = {}
		self._generation = 0

	def invalidate(self):
		with self._lock:
			self._generation += 1
			self._cache.clear()

	def getCascade(self, sampleRate):
		"""Return the Cascade for this sample rate, or None when Cedar should not touch the audio."""
		with self._lock:
			generation = self._generation
			cascade = self._cache.get(sampleRate, _MISSING)
		if cascade is _MISSING:
			cascade = self._build(sampleRate)
			with self._lock:
				# A settings change while this was building wins, so a stale cascade is not cached.
				if generation == self._generation:
					self._cache[sampleRate] = cascade
		return None if cascade is None or cascade.isBypass else cascade

	def _build(self, sampleRate):
		c = conf()
		if not c["enabled"]:
			return None
		sections = []
		if c["rumbleFilter"]:
			sections.append(dsp.makeSection(dsp.HIGH_PASS, sampleRate, c["rumbleFreq"], 0.0, 0.707))
		for band in BANDS:
			sections.append(dsp.makeSection(
				band.filterType, sampleRate, c[band.freqKey], c[band.gainKey], c[band.qKey]
			))
		if c["hissFilter"]:
			sections.append(dsp.makeSection(dsp.LOW_PASS, sampleRate, c["hissFreq"], 0.0, 0.707))
		# Bands sitting at zero gain compile to nothing, so a mostly flat setting stays cheap.
		sections = [s for s in sections if s is not None]

		inputGain = 10.0 ** (c["preamp"] / 20.0)
		outputGain = 1.0
		if c["autoGain"] and sections:
			# Compensates only the filters' own boost; the preamp stays a deliberate level control.
			peak = dsp.peakResponseDb(sections, sampleRate)
			if peak > 0.0:
				outputGain = 10.0 ** (-peak / 20.0)
		return dsp.Cascade(sections, inputGain, outputGain, c["softClip"])


equalizer = Engine()

registerConfig()
