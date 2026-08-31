"""Exercises Cedar's engine, presets and audio hook against stubbed NVDA modules."""

import ctypes
import io
import math
import os
import sys
import unittest
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nvda_stubs

nvwave, configMod = nvda_stubs.install()

from cedar import audiohook, dsp, engine, presets
from cedar.engine import BANDS, conf, resetToFlat

FS = 22050


def sine(freq, n, amp=6000.0, fs=FS, channels=1):
	buf = array("h")
	for i in range(n):
		value = int(amp * math.sin(2 * math.pi * freq * i / fs))
		buf.extend([value] * channels)
	return buf.tobytes()


_CALL_SOURCE = """
def call(player, args):
	player.feed(*args)
"""


def feedFrom(moduleName, player, *args):
	"""Feed from a frame belonging to moduleName, which is how the hook tells speech apart."""
	namespace = {"__name__": moduleName}
	exec(_CALL_SOURCE, namespace)
	namespace["call"](player, args)


def speak(player, *args):
	"""Feed the way a synth driver does."""
	feedFrom("synthDrivers.fake", player, *args)


def peak(data):
	buf = array("h")
	buf.frombytes(data)
	return max(abs(v) for v in buf)


class CedarTestCase(unittest.TestCase):
	def setUp(self):
		engine.registerConfig()
		resetToFlat()
		c = conf()
		c["enabled"] = True
		c["processSounds"] = False
		c["autoGain"] = True
		c["softClip"] = True
		c["userPresets"] = ""
		engine.equalizer.invalidate()


class TestEngine(CedarTestCase):
	def test_defaults_come_from_the_spec(self):
		c = conf()
		self.assertTrue(c["enabled"])
		self.assertEqual(c["preamp"], 0.0)
		for band in BANDS:
			self.assertEqual(c[band.gainKey], 0.0)
			self.assertEqual(c[band.freqKey], band.defaultFreq)

	def test_flat_settings_bypass_entirely(self):
		self.assertIsNone(engine.equalizer.getCascade(FS))

	def test_disabled_bypasses_even_with_gain(self):
		conf()["lowGain"] = 9.0
		conf()["enabled"] = False
		engine.equalizer.invalidate()
		self.assertIsNone(engine.equalizer.getCascade(FS))

	def test_gain_produces_a_cascade(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		cascade = engine.equalizer.getCascade(FS)
		self.assertIsNotNone(cascade)
		self.assertEqual(len(cascade.sections), 1)

	def test_cascades_are_cached_per_sample_rate(self):
		conf()["highGain"] = 6.0
		engine.equalizer.invalidate()
		first = engine.equalizer.getCascade(FS)
		self.assertIs(first, engine.equalizer.getCascade(FS))
		self.assertIsNot(first, engine.equalizer.getCascade(48000))

	def test_invalidate_rebuilds(self):
		conf()["highGain"] = 6.0
		engine.equalizer.invalidate()
		first = engine.equalizer.getCascade(FS)
		conf()["highGain"] = 3.0
		engine.equalizer.invalidate()
		self.assertIsNot(first, engine.equalizer.getCascade(FS))

	def test_auto_gain_removes_the_boost_headroom(self):
		conf()["lowGain"] = 12.0
		conf()["highGain"] = 12.0
		engine.equalizer.invalidate()
		cascade = engine.equalizer.getCascade(FS)
		totalPeakDb = dsp.peakResponseDb(cascade.sections, FS) + 20 * math.log10(cascade.outputGain)
		self.assertLess(abs(totalPeakDb), 0.2)

	def test_preamp_survives_auto_gain(self):
		conf()["preamp"] = 6.0
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		cascade = engine.equalizer.getCascade(FS)
		self.assertAlmostEqual(cascade.inputGain, 10 ** (6.0 / 20.0), places=6)

	def test_rumble_filter_adds_a_section_without_any_band_gain(self):
		conf()["rumbleFilter"] = True
		engine.equalizer.invalidate()
		cascade = engine.equalizer.getCascade(FS)
		self.assertIsNotNone(cascade)
		self.assertEqual(len(cascade.sections), 1)


class TestPresets(CedarTestCase):
	def test_builtin_preset_applies_its_values(self):
		self.assertTrue(presets.applyPreset("Warm"))
		self.assertEqual(conf()["lowGain"], 5.0)
		self.assertEqual(conf()["highGain"], -2.0)
		self.assertEqual(conf()["currentPreset"], "Warm")

	def test_switching_preset_clears_what_the_new_one_omits(self):
		presets.applyPreset("Bass boost")
		self.assertEqual(conf()["lowGain"], 8.0)
		presets.applyPreset("Bright")
		self.assertEqual(conf()["lowGain"], -2.0)
		self.assertEqual(conf()["lowMidGain"], 0.0)

	def test_preset_restores_frequencies_it_does_not_set(self):
		presets.applyPreset("Less sibilance")
		self.assertEqual(conf()["presenceFreq"], 6500.0)
		presets.applyPreset("Warm")
		self.assertEqual(conf()["presenceFreq"], engine.BAND_BY_ID["presence"].defaultFreq)

	def test_user_preset_round_trip(self):
		conf()["midGain"] = 7.0
		conf()["presenceFreq"] = 2800.0
		presets.saveUserPresets({"Mine": presets.captureCurrent()})
		resetToFlat()
		self.assertEqual(conf()["midGain"], 0.0)
		self.assertTrue(presets.applyPreset("Mine"))
		self.assertEqual(conf()["midGain"], 7.0)
		self.assertEqual(conf()["presenceFreq"], 2800.0)

	def test_unknown_preset_is_reported(self):
		self.assertFalse(presets.applyPreset("nope"))

	def test_corrupt_user_presets_are_ignored(self):
		conf()["userPresets"] = "{not json"
		self.assertEqual(presets.loadUserPresets(), {})

	def test_user_presets_cannot_smuggle_unrelated_keys(self):
		conf()["userPresets"] = '{"Evil": {"enabled": false, "midGain": 3.0}}'
		self.assertEqual(presets.loadUserPresets()["Evil"], {"midGain": 3.0})
		presets.applyPreset("Evil")
		self.assertTrue(conf()["enabled"])

	def test_builtin_names_are_listed_first(self):
		presets.saveUserPresets({"Aaa": {}})
		names = presets.allPresetNames()
		self.assertEqual(names[0], "Flat")
		self.assertEqual(names[-1], "Aaa")
		self.assertTrue(presets.isBuiltin("Flat"))
		self.assertFalse(presets.isBuiltin("Aaa"))


class TestAudioHook(CedarTestCase):
	def setUp(self):
		super().setUp()
		audiohook.patch()
		self.addCleanup(audiohook.unpatch)

	def _player(self, **kwargs):
		return nvwave.WavePlayer(**kwargs)

	def test_flat_audio_is_untouched(self):
		player = self._player()
		data = sine(400, 2000)
		speak(player, data)
		self.assertEqual(player.fed[0], data)

	def test_speech_is_filtered_and_matches_a_direct_run(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player()
		data = sine(80, 4000)
		speak(player, data)
		cascade = engine.equalizer.getCascade(FS)
		expected = dsp.process(cascade, data, 1, cascade.newState(1))
		self.assertEqual(player.fed[0], expected)
		self.assertNotEqual(player.fed[0], data)

	def test_sounds_are_left_alone_by_default(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player(purpose=nvwave.AudioPurpose.SOUNDS)
		data = sine(80, 2000)
		speak(player, data)
		self.assertEqual(player.fed[0], data)

	def test_sounds_are_filtered_when_the_user_asks(self):
		conf()["lowGain"] = 9.0
		conf()["processSounds"] = True
		engine.equalizer.invalidate()
		player = self._player(purpose=nvwave.AudioPurpose.SOUNDS)
		data = sine(80, 2000)
		speak(player, data)
		self.assertNotEqual(player.fed[0], data)

	def test_non_16_bit_audio_passes_through(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player(bitsPerSample=32)
		data = sine(80, 2000)
		speak(player, data)
		self.assertEqual(player.fed[0], data)

	def test_ctypes_pointer_input_is_handled(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		data = sine(80, 2000)
		buf = ctypes.create_string_buffer(data, len(data))
		byPointer = self._player()
		speak(byPointer, ctypes.cast(buf, ctypes.c_void_p), len(data))
		byBytes = self._player()
		speak(byBytes, data)
		self.assertEqual(byPointer.fed[0], byBytes.fed[0])

	def test_filtering_is_continuous_across_chunks(self):
		conf()["midGain"] = 8.0
		engine.equalizer.invalidate()
		data = sine(300, 4000)
		whole = self._player()
		speak(whole, data)
		chunked = self._player()
		for start in range(0, 4000, 512):
			speak(chunked, data[start * 2:(start + 512) * 2])
		self.assertEqual(b"".join(chunked.fed), whole.fed[0])

	def test_stop_clears_the_filter_tail(self):
		conf()["midGain"] = 8.0
		engine.equalizer.invalidate()
		data = sine(300, 1024)
		first = self._player()
		speak(first, data)
		first.stop()
		speak(first, data)
		fresh = self._player()
		speak(fresh, data)
		self.assertEqual(first.fed[1], fresh.fed[0])

	def test_stereo_is_filtered_per_channel(self):
		conf()["highGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player(channels=2, samplesPerSec=48000)
		data = sine(6000, 2000, fs=48000, channels=2)
		speak(player, data)
		out = array("h")
		out.frombytes(player.fed[0])
		self.assertEqual(list(out[0::2]), list(out[1::2]))

	def test_output_never_exceeds_full_scale(self):
		conf()["lowGain"] = 18.0
		conf()["midGain"] = 18.0
		conf()["preamp"] = 12.0
		conf()["autoGain"] = False
		engine.equalizer.invalidate()
		player = self._player()
		speak(player, sine(200, 4000, amp=30000.0))
		self.assertLessEqual(peak(player.fed[0]), 32767)

	def test_a_failing_cascade_still_plays_audio(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		original = dsp.process
		dsp.process = lambda *args, **kwargs: 1 / 0
		try:
			player = self._player()
			data = sine(400, 1000)
			speak(player, data)
		finally:
			dsp.process = original
		self.assertEqual(player.fed[0], data)

	def test_a_hook_left_by_a_previous_load_is_replaced(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		data = sine(80, 2000)
		reference = self._player()
		speak(reference, data)
		# NVDA reloading plugins re-imports the module while its hook is still installed.
		audiohook._originalFeed = None
		audiohook._originalStop = None
		audiohook.patch()
		player = self._player()
		speak(player, data)
		self.assertEqual(player.fed[0], reference.fed[0])

	def test_unpatch_leaves_another_addons_wrapper_alone(self):
		ourFeed = nvwave.WavePlayer.feed

		def theirFeed(player, data, size=None, onDone=None):
			return ourFeed(player, data, size, onDone)

		nvwave.WavePlayer.feed = theirFeed
		try:
			audiohook.unpatch()
			self.assertIs(nvwave.WavePlayer.feed, theirFeed)
			audiohook.patch()
			self.assertIs(nvwave.WavePlayer.feed, theirFeed)
		finally:
			nvwave.WavePlayer.feed = ourFeed

	def test_a_sound_add_on_calling_itself_speech_is_left_alone(self):
		"""WavePlayer defaults purpose to SPEECH, and add-ons that make sounds rarely override it."""
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player()
		data = sine(80, 2000)
		feedFrom("globalPlugins.enhancedTones._tones", player, data)
		self.assertEqual(player.fed[0], data)

	def test_a_sound_add_on_is_filtered_once_sounds_are_enabled(self):
		conf()["lowGain"] = 9.0
		conf()["processSounds"] = True
		engine.equalizer.invalidate()
		player = self._player()
		data = sine(80, 2000)
		feedFrom("globalPlugins.enhancedTones._tones", player, data)
		self.assertNotEqual(player.fed[0], data)

	def test_an_add_on_synthesizer_counts_as_speech(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player()
		data = sine(80, 2000)
		feedFrom("synthDrivers.leopardspeech", player, data)
		self.assertNotEqual(player.fed[0], data)

	def test_a_player_owned_by_the_active_synth_counts_as_speech(self):
		"""Covers a synth that feeds from somewhere with no synthDrivers frame on the stack."""
		import synthDriverHandler

		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player()

		class FakeSynth:
			pass

		synth = FakeSynth()
		synth._player = player
		synthDriverHandler.synth = synth
		self.addCleanup(setattr, synthDriverHandler, "synth", None)
		data = sine(80, 2000)
		feedFrom("queueHandler", player, data)
		self.assertNotEqual(player.fed[0], data)

	def test_the_speech_decision_is_made_once_per_player(self):
		conf()["lowGain"] = 9.0
		engine.equalizer.invalidate()
		player = self._player()
		data = sine(80, 2000)
		speak(player, data)
		# The synth owns this player, so a later feed from elsewhere is still its speech.
		feedFrom("queueHandler", player, data)
		self.assertNotEqual(player.fed[1], data)

	def test_patch_is_idempotent_and_reversible(self):
		before = nvwave.WavePlayer.feed
		audiohook.patch()
		self.assertIs(nvwave.WavePlayer.feed, before)
		audiohook.unpatch()
		self.assertIs(nvwave.WavePlayer.feed, nvda_stubs.FakeWavePlayer.__dict__["feed"])
		audiohook.patch()


class TestGlobalPlugin(CedarTestCase):
	"""Builds the plugin the way NVDA does, which is the only place the module wiring is exercised."""

	def setUp(self):
		super().setUp()
		import gui as nvdaGui

		from cedar import GlobalPlugin
		from cedar.settingsgui import CedarSettingsPanel

		self.nvdaGui = nvdaGui
		self.panelClass = CedarSettingsPanel
		self.plugin = GlobalPlugin()
		self.addCleanup(self.plugin.terminate)

	def test_settings_category_is_registered(self):
		self.assertIn(self.panelClass, self.nvdaGui.NVDASettingsDialog.categoryClasses)

	def test_terminate_removes_the_category_and_the_hook(self):
		self.plugin.terminate()
		self.assertNotIn(self.panelClass, self.nvdaGui.NVDASettingsDialog.categoryClasses)
		self.assertIs(nvwave.WavePlayer.feed, nvda_stubs.FakeWavePlayer.__dict__["feed"])

	def test_toggle_script_flips_enabled(self):
		self.assertTrue(conf()["enabled"])
		self.plugin.script_toggleCedar(None)
		self.assertFalse(conf()["enabled"])
		self.plugin.script_toggleCedar(None)
		self.assertTrue(conf()["enabled"])

	def test_band_scripts_adjust_and_clamp(self):
		self.plugin.script_bassUp(None)
		self.assertEqual(conf()["lowGain"], 1.0)
		self.plugin.script_bassDown(None)
		self.assertEqual(conf()["lowGain"], 0.0)
		for _ in range(int(engine.GAIN_LIMIT) + 5):
			self.plugin.script_trebleUp(None)
		self.assertEqual(conf()["highGain"], engine.GAIN_LIMIT)

	def test_preset_cycling_walks_the_list(self):
		names = presets.allPresetNames()
		self.plugin.script_nextPreset(None)
		self.assertEqual(conf()["currentPreset"], names[0])
		self.plugin.script_nextPreset(None)
		self.assertEqual(conf()["currentPreset"], names[1])
		self.plugin.script_previousPreset(None)
		self.assertEqual(conf()["currentPreset"], names[0])


class TestFilterSafety(unittest.TestCase):
	def test_steep_shelves_at_high_gain_do_not_blow_up(self):
		"""The shelf alpha term goes negative above slope 1, which used to raise a math domain error."""
		for filterType in (dsp.LOW_SHELF, dsp.HIGH_SHELF):
			for gain in (-18.0, -9.0, 9.0, 18.0):
				for slope in (0.1, 0.7, 1.0, 4.0, 10.0):
					section = dsp.makeSection(filterType, FS, 150.0, gain, slope)
					self.assertIsNotNone(section)
					for coefficient in section:
						self.assertTrue(math.isfinite(coefficient), (filterType, gain, slope))

	def test_frequencies_at_or_above_nyquist_are_pulled_back(self):
		for freq in (FS / 2.0, FS, FS * 4):
			section = dsp.makeSection(dsp.PEAKING, FS, freq, 6.0, 1.0)
			for coefficient in section:
				self.assertTrue(math.isfinite(coefficient))

	def test_shelf_slope_is_capped_in_the_config_spec(self):
		for band in BANDS:
			limit = "max=1.0" if band.isShelf else "max=10.0"
			self.assertIn(limit, engine.confspec[band.qKey], band.id)


class TestGuiContract(unittest.TestCase):
	"""guiHelper can only pair a label with a fixed set of control types."""

	# From gui.guiHelper._HorizontalCtrlT in NVDA 2025.3.
	LABELABLE = {"Button", "Choice", "ComboBox", "Slider", "SpinCtrl", "TextCtrl"}

	def test_every_labeled_control_is_one_guihelper_can_label(self):
		import re

		path = os.path.join(nvda_stubs.ADDON_ROOT, "cedar", "settingsgui.py")
		with io.open(path, encoding="utf-8") as handle:
			source = handle.read()
		used = set(re.findall(r"addLabeledControl\(\s*[^,]+,\s*wx\.(\w+)", source))
		self.assertTrue(used, "no labeled controls found, the check has gone stale")
		self.assertEqual(used - self.LABELABLE, set())


if __name__ == "__main__":
	unittest.main(verbosity=2)
