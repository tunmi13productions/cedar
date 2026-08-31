"""Just enough of NVDA's runtime to import and exercise Cedar outside NVDA itself."""

import builtins
import enum
import os
import re
import sys
import types

ADDON_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "addon", "globalPlugins")

_SPEC_PATTERN = re.compile(r"^(\w+)\((.*)\)$")


def _parseSpec(spec):
	"""Read a configobj validator string well enough to recover its default."""
	match = _SPEC_PATTERN.match(spec)
	kind, rawArgs = match.group(1), match.group(2)
	default = None
	for part in rawArgs.split(","):
		part = part.strip()
		if part.startswith("default="):
			default = part[len("default="):].strip()
	if kind == "boolean":
		return default == "True"
	if kind == "float":
		return float(default)
	if kind == "string":
		return default.strip('"').strip("'")
	raise ValueError("unhandled spec %r" % (spec,))


class Section(dict):
	"""A stand in for a configobj section that fills itself in from its spec."""

	def applySpec(self, spec):
		for key, value in spec.items():
			self[key] = _parseSpec(value)


class ExtensionPoint:
	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		if handler in self.handlers:
			self.handlers.remove(handler)

	def notify(self, **kwargs):
		for handler in list(self.handlers):
			handler(**kwargs)


class _AudioPurpose(enum.Enum):
	SPEECH = enum.auto()
	SOUNDS = enum.auto()


class FakeWavePlayer:
	"""Mirrors the parts of nvwave.WavePlayer that Cedar touches."""

	def __init__(self, channels=1, samplesPerSec=22050, bitsPerSample=16, purpose=_AudioPurpose.SPEECH):
		self.channels = channels
		self.samplesPerSec = samplesPerSec
		self.bitsPerSample = bitsPerSample
		self._purpose = purpose
		self.fed = []
		self.stopped = 0

	def feed(self, data, size=None, onDone=None):
		self.fed.append(bytes(data) if size is None else bytes(data[:size]))

	def stop(self):
		self.stopped += 1


def _module(name, **attrs):
	mod = types.ModuleType(name)
	for key, value in attrs.items():
		setattr(mod, key, value)
	sys.modules[name] = mod
	return mod


class _Anything:
	"""Absorbs any attribute access, so stub modules do not need every wx constant spelled out."""

	def __init__(self, *args, **kwargs):
		pass

	def __getattr__(self, name):
		return _Anything()

	def __call__(self, *args, **kwargs):
		return _Anything()


def install():
	builtins._ = lambda text: text
	builtins.ngettext = lambda s, p, n: s if n == 1 else p

	_module("addonHandler", initTranslation=lambda: None)
	_module("logHandler", log=_Anything())
	_module("ui", message=lambda text: None)
	_module("globalPluginHandler", GlobalPlugin=type("GlobalPlugin", (object,), {"terminate": lambda self: None}))
	_module("scriptHandler", script=lambda **kwargs: (lambda func: func))

	nvwave = _module("nvwave", WavePlayer=FakeWavePlayer, AudioPurpose=_AudioPurpose)

	synthDriverHandler = _module("synthDriverHandler")
	synthDriverHandler.synth = None
	synthDriverHandler.getSynth = lambda: synthDriverHandler.synth

	class Conf(dict):
		"""Materialises a section from the registered spec the first time it is asked for."""

		def __init__(self):
			super().__init__()
			self.spec = {}

		def __getitem__(self, key):
			if key not in self and key in self.spec:
				section = Section()
				section.applySpec(self.spec[key])
				dict.__setitem__(self, key, section)
			return dict.__getitem__(self, key)

	configMod = _module(
		"config",
		conf=Conf(),
		post_configProfileSwitch=ExtensionPoint(),
		post_configReset=ExtensionPoint(),
	)

	wx = _module("wx", Dialog=type("Dialog", (object,), {}), NOT_FOUND=-1)
	wx.__getattr__ = lambda name: _Anything()

	guiHelper = _module("gui.guiHelper", BoxSizerHelper=_Anything, ButtonHelper=_Anything, BORDER_FOR_DIALOGS=10)
	settingsDialogs = _module(
		"gui.settingsDialogs",
		SettingsPanel=type("SettingsPanel", (object,), {"title": "", "makeSettings": lambda self, s: None}),
	)
	message = _module("gui.message", messageBox=lambda *args, **kwargs: 0)
	guiMod = _module(
		"gui",
		guiHelper=guiHelper,
		settingsDialogs=settingsDialogs,
		message=message,
		NVDASettingsDialog=type("NVDASettingsDialog", (object,), {"categoryClasses": []}),
		mainFrame=_Anything(),
		messageBox=message.messageBox,
	)
	guiMod.__path__ = []

	if ADDON_ROOT not in sys.path:
		sys.path.insert(0, ADDON_ROOT)
	return nvwave, configMod
