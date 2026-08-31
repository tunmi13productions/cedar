"""Configuration schema and compilation of settings into a runnable filter cascade."""

import threading

import addonHandler
import config

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

confspec = {
	"enabled": "boolean(default=True)",
	"processSounds": "boolean(default=False)",
	"advancedMode": "boolean(default=False)",
	"preamp": "float(default=0.0, min=-%s, max=%s)" % (PREAMP_LIMIT, PREAMP_LIMIT),
	"autoGain": "boolean(default=True)",
	"softClip": "boolean(default=True)",
	"rumbleFilter": "boolean(default=False)",
	"rumbleFreq": "float(default=80.0, min=20.0, max=400.0)",
	"hissFilter": "boolean(default=False)",
	"hissFreq": "float(default=9000.0, min=2000.0, max=16000.0)",
	"currentPreset": 'string(default="")',
	"userPresets": 'string(default="")',
}
for _band in BANDS:
	confspec[_band.gainKey] = "float(default=0.0, min=-%s, max=%s)" % (GAIN_LIMIT, GAIN_LIMIT)
	confspec[_band.freqKey] = "float(default=%s, min=%s, max=%s)" % (_band.defaultFreq, _band.minFreq, _band.maxFreq)
	confspec[_band.qKey] = "float(default=%s, min=0.1, max=%s)" % (
		_band.defaultQ, 1.0 if _band.isShelf else 10.0
	)


def registerConfig():
	config.conf.spec[CONFIG_SECTION] = confspec


def conf():
	return config.conf[CONFIG_SECTION]


def resetToFlat():
	"""Zero every gain and return every band to its designed frequency and width."""
	c = conf()
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
