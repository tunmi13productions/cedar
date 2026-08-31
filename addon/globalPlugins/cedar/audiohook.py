"""Patches nvwave.WavePlayer so speech audio passes through the equalizer on its way to the device."""

import ctypes
import sys

import nvwave
from logHandler import log

from . import dsp
from .engine import conf, equalizer

_originalFeed = None
_originalStop = None
_warnedFormats = set()

# Older builds route every stream through one player and cannot say what the audio is for.
_SPEECH_PURPOSE = getattr(getattr(nvwave, "AudioPurpose", None), "SPEECH", None)


def _synthDriverOnStack():
	"""True when a synth driver is somewhere in the call chain feeding this audio.

	NVDA loads every synth driver, add-on ones included, into the synthDrivers package, so the
	module name of a frame is a reliable marker of speech.
	"""
	frame = sys._getframe(1)
	depth = 0
	while frame is not None and depth < 25:
		name = frame.f_globals.get("__name__", "")
		if name == "synthDrivers" or name.startswith("synthDrivers."):
			return True
		frame = frame.f_back
		depth += 1
	return False


def _belongsToActiveSynth(player):
	"""A synth that feeds from somewhere unexpected can still be recognised by what it owns."""
	try:
		import synthDriverHandler

		synth = synthDriverHandler.getSynth()
	except Exception:
		return False
	if synth is None:
		return False
	try:
		return any(value is player for value in vars(synth).values())
	except TypeError:
		return False


def _isSpeech(player):
	"""Decide once per player whether its audio is speech, and remember the answer.

	WavePlayer's purpose argument defaults to SPEECH, and add-ons that produce sounds rarely pass
	it, so a stream calling itself speech proves nothing. Only audio that a synth driver is
	actually producing counts.
	"""
	decided = getattr(player, "_cedarIsSpeech", None)
	if decided is not None:
		return decided
	if _SPEECH_PURPOSE is not None and getattr(player, "_purpose", None) is not _SPEECH_PURPOSE:
		decided = False
	else:
		decided = _synthDriverOnStack() or _belongsToActiveSynth(player)
	player._cedarIsSpeech = decided
	log.debug("Cedar: %d Hz player treated as %s" % (player.samplesPerSec, "speech" if decided else "not speech"))
	return decided


def _cascadeFor(player):
	"""Pick the cascade for this player, or None when its audio should be left alone."""
	if player.bitsPerSample != 16:
		key = (player.bitsPerSample, player.samplesPerSec)
		if key not in _warnedFormats:
			_warnedFormats.add(key)
			log.debug("Cedar: passing through %d bit audio, only 16 bit is filtered" % player.bitsPerSample)
		return None
	if not conf()["processSounds"] and not _isSpeech(player):
		return None
	return equalizer.getCascade(player.samplesPerSec)


def _stateFor(player, cascade, channels):
	"""Per player delay lines, rebuilt whenever the cascade it was made for is replaced."""
	held = getattr(player, "_cedarState", None)
	if held is None or held[0] is not cascade:
		held = (cascade, cascade.newState(channels))
		player._cedarState = held
	return held[1]


def _feed(self, data, size=None, onDone=None):
	try:
		cascade = _cascadeFor(self)
		if cascade is not None:
			if size is not None:
				data = ctypes.string_at(data, size)
				size = None
			elif not isinstance(data, bytes):
				data = bytes(memoryview(data))
			channels = self.channels
			data = dsp.process(cascade, data, channels, _stateFor(self, cascade, channels))
	except Exception:
		log.error("Cedar: could not filter this chunk, playing it unprocessed", exc_info=True)
	return _originalFeed(self, data, size, onDone)


def _stop(self, *args, **kwargs):
	# Dropping the delay lines stops the tail of cancelled speech bleeding into the next utterance.
	try:
		self._cedarState = None
	except Exception:
		pass
	return _originalStop(self, *args, **kwargs)


def patch():
	global _originalFeed, _originalStop
	if _originalFeed is not None:
		return
	currentFeed = nvwave.WavePlayer.feed
	currentStop = nvwave.WavePlayer.stop
	# Reloading plugins can leave a hook from a previous load behind; take its place rather than stack on it.
	_originalFeed = getattr(currentFeed, "_cedarOriginal", currentFeed)
	_originalStop = getattr(currentStop, "_cedarOriginal", currentStop)
	_feed._cedarOriginal = _originalFeed
	_stop._cedarOriginal = _originalStop
	nvwave.WavePlayer.feed = _feed
	nvwave.WavePlayer.stop = _stop
	log.debug("Cedar: audio hook installed")


def unpatch():
	global _originalFeed, _originalStop
	if _originalFeed is None:
		return
	if nvwave.WavePlayer.feed is not _feed:
		# Another add-on wrapped us, so removing our hook would cut theirs out of the chain too.
		log.warning("Cedar: another add-on patched feed after us, leaving the hook in place")
		return
	nvwave.WavePlayer.feed = _originalFeed
	if nvwave.WavePlayer.stop is _stop:
		nvwave.WavePlayer.stop = _originalStop
	_originalFeed = None
	_originalStop = None
