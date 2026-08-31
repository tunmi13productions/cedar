"""Biquad filter maths and the sample processing loop for Cedar."""

import cmath
import math
from array import array

PEAKING = "peaking"
LOW_SHELF = "lowshelf"
HIGH_SHELF = "highshelf"
HIGH_PASS = "highpass"
LOW_PASS = "lowpass"

SAMPLE_MAX = 32767.0
SAMPLE_MIN = -32768.0
# Above this level the limiter bends the waveform instead of shearing it flat.
SOFT_KNEE = 0.88 * SAMPLE_MAX


def _normalise(b0, b1, b2, a0, a1, a2):
	return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def makeSection(filterType, sampleRate, freq, gainDb, q):
	"""Build one normalised biquad from the RBJ audio EQ cookbook formulas.

	Returns a (b0, b1, b2, a1, a2) tuple, or None when the section would be a no-op.
	"""
	nyquist = sampleRate / 2.0
	# A pole placed at or above Nyquist is undefined, so pull it back inside the band.
	freq = max(10.0, min(float(freq), nyquist * 0.95))
	q = max(0.1, min(float(q), 18.0))
	w0 = 2.0 * math.pi * freq / sampleRate
	cosW0 = math.cos(w0)
	sinW0 = math.sin(w0)

	if filterType in (PEAKING, LOW_SHELF, HIGH_SHELF):
		if abs(gainDb) < 0.01:
			return None
		A = 10.0 ** (gainDb / 40.0)
	else:
		A = 1.0
	if filterType in (LOW_SHELF, HIGH_SHELF):
		# A shelf slope above 1 overshoots, and at high gain drives the alpha term negative.
		q = min(q, 1.0)

	if filterType == PEAKING:
		alpha = sinW0 / (2.0 * q)
		return _normalise(
			1.0 + alpha * A, -2.0 * cosW0, 1.0 - alpha * A,
			1.0 + alpha / A, -2.0 * cosW0, 1.0 - alpha / A,
		)
	if filterType == LOW_SHELF:
		# q doubles as the shelf slope S here; 1.0 is the steepest non-resonant shelf.
		alpha = sinW0 / 2.0 * math.sqrt(max(0.0, (A + 1.0 / A) * (1.0 / q - 1.0) + 2.0))
		twoSqrtAAlpha = 2.0 * math.sqrt(A) * alpha
		return _normalise(
			A * ((A + 1.0) - (A - 1.0) * cosW0 + twoSqrtAAlpha),
			2.0 * A * ((A - 1.0) - (A + 1.0) * cosW0),
			A * ((A + 1.0) - (A - 1.0) * cosW0 - twoSqrtAAlpha),
			(A + 1.0) + (A - 1.0) * cosW0 + twoSqrtAAlpha,
			-2.0 * ((A - 1.0) + (A + 1.0) * cosW0),
			(A + 1.0) + (A - 1.0) * cosW0 - twoSqrtAAlpha,
		)
	if filterType == HIGH_SHELF:
		alpha = sinW0 / 2.0 * math.sqrt(max(0.0, (A + 1.0 / A) * (1.0 / q - 1.0) + 2.0))
		twoSqrtAAlpha = 2.0 * math.sqrt(A) * alpha
		return _normalise(
			A * ((A + 1.0) + (A - 1.0) * cosW0 + twoSqrtAAlpha),
			-2.0 * A * ((A - 1.0) + (A + 1.0) * cosW0),
			A * ((A + 1.0) + (A - 1.0) * cosW0 - twoSqrtAAlpha),
			(A + 1.0) - (A - 1.0) * cosW0 + twoSqrtAAlpha,
			2.0 * ((A - 1.0) - (A + 1.0) * cosW0),
			(A + 1.0) - (A - 1.0) * cosW0 - twoSqrtAAlpha,
		)
	if filterType == HIGH_PASS:
		alpha = sinW0 / (2.0 * q)
		return _normalise(
			(1.0 + cosW0) / 2.0, -(1.0 + cosW0), (1.0 + cosW0) / 2.0,
			1.0 + alpha, -2.0 * cosW0, 1.0 - alpha,
		)
	if filterType == LOW_PASS:
		alpha = sinW0 / (2.0 * q)
		return _normalise(
			(1.0 - cosW0) / 2.0, 1.0 - cosW0, (1.0 - cosW0) / 2.0,
			1.0 + alpha, -2.0 * cosW0, 1.0 - alpha,
		)
	raise ValueError("unknown filter type %r" % (filterType,))


def peakResponseDb(sections, sampleRate):
	"""Largest magnitude the cascade can produce, in dB, sampled on a log frequency grid."""
	if not sections:
		return 0.0
	peak = 0.0
	nyquist = sampleRate / 2.0
	steps = 200
	logLo = math.log10(20.0)
	logHi = math.log10(max(nyquist * 0.99, 40.0))
	for i in range(steps + 1):
		freq = 10.0 ** (logLo + (logHi - logLo) * i / steps)
		z = cmath.exp(-2j * math.pi * freq / sampleRate)
		mag = 1.0
		for b0, b1, b2, a1, a2 in sections:
			mag *= abs((b0 + b1 * z + b2 * z * z) / (1.0 + a1 * z + a2 * z * z))
		if mag > peak:
			peak = mag
	if peak <= 0.0:
		return 0.0
	return 20.0 * math.log10(peak)


class Cascade:
	"""An immutable, sample-rate-specific chain of biquads ready to run."""

	__slots__ = ("sections", "inputGain", "outputGain", "softClip", "isBypass")

	def __init__(self, sections, inputGain=1.0, outputGain=1.0, softClip=True):
		self.sections = tuple(sections)
		self.inputGain = inputGain
		self.outputGain = outputGain
		self.softClip = softClip
		self.isBypass = not self.sections and abs(inputGain * outputGain - 1.0) < 1e-6

	def newState(self, channels):
		return [[[0.0, 0.0] for _ in self.sections] for _ in range(channels)]


def process(cascade, data, channels, state):
	"""Filter one chunk of interleaved 16 bit PCM, returning new bytes.

	`state` is the per-channel delay line list from Cascade.newState, mutated in place so
	filtering stays continuous across chunk boundaries.
	"""
	buf = array("h")
	buf.frombytes(data)
	if not buf:
		return data
	samples = buf.tolist()
	total = len(samples)
	sections = cascade.sections
	inputGain = cascade.inputGain

	if not sections:
		gain = inputGain * cascade.outputGain
		for i in range(total):
			samples[i] = samples[i] * gain
	else:
		lastIndex = len(sections) - 1
		for ch in range(channels):
			chState = state[ch]
			for si in range(len(sections)):
				b0, b1, b2, a1, a2 = sections[si]
				# Folding the gains into the first and last sections keeps them free.
				if si == 0:
					b0 *= inputGain
					b1 *= inputGain
					b2 *= inputGain
				if si == lastIndex:
					b0 *= cascade.outputGain
					b1 *= cascade.outputGain
					b2 *= cascade.outputGain
				z = chState[si]
				z1 = z[0]
				z2 = z[1]
				# Transposed direct form II: two state words per section, good float behaviour.
				for i in range(ch, total, channels):
					x = samples[i]
					y = b0 * x + z1
					z1 = b1 * x - a1 * y + z2
					z2 = b2 * x - a2 * y
					samples[i] = y
				z[0] = z1
				z[1] = z2

	if cascade.softClip:
		knee = SOFT_KNEE
		headroom = SAMPLE_MAX - SOFT_KNEE
		tanh = math.tanh
		for i in range(total):
			v = samples[i]
			if v > knee:
				v = knee + headroom * tanh((v - knee) / headroom)
			elif v < -knee:
				v = -knee - headroom * tanh((-v - knee) / headroom)
			samples[i] = int(v)
	else:
		for i in range(total):
			v = samples[i]
			if v > SAMPLE_MAX:
				v = SAMPLE_MAX
			elif v < SAMPLE_MIN:
				v = SAMPLE_MIN
			samples[i] = int(v)

	buf = array("h", samples)
	return buf.tobytes()
