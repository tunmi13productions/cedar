# Cedar

Cedar is a Custom Equalizer Designed for Audible Reading. It gives NVDA its own equalizer for speech, so you can shape the tone of any synthesizer without touching your system sound settings.

Most people only ever need three controls: bass, mids and treble. Those are the first thing you meet. Everything else, including a full parametric equalizer, sits behind an advanced settings checkbox so it stays out of your way until you want it.

## A warning before you install

This add-on was vibe coded with Claude Opus 5, Anthropic's AI model. It works, and it has a test suite, but it was not written line by line by a human. Expect oddities. If something behaves strangely, please report it rather than assuming it is meant to work that way.

Cedar sits directly in the path of NVDA's speech audio. If it ever goes wrong badly enough that you cannot hear NVDA, delete the cedar folder from your NVDA add-ons directory and restart NVDA.

## Requirements

NVDA 2024.1 or later. Cedar is tested on NVDA 2025.3.

## Installing

Download the latest cedar.nvda-addon from the releases page and press enter on it. Restart NVDA when prompted.

## Using Cedar

Open NVDA menu, Preferences, Settings, and choose the Cedar equalizer category. The panel has:
- Enable the Cedar equalizer, which switches all processing on or off.
- Preset, a list of ready made settings plus any you have saved yourself.
- Bass, Mids and Treble sliders, each adjustable from -18 to +18 decibels with the arrow keys.
- Overall volume trim, which raises or lowers the whole speech level by up to 12 decibels.
- Prevent distortion from boosted bands, which quietly compensates for the level your boosts add. Leave this on unless you know you want the extra loudness.
- Test voice, which speaks a sample sentence so you can judge a setting by ear.
- Save as preset, Delete preset and Reset to flat.

Changes apply as you make them, so NVDA's own speech is the preview. Move the bass slider and you hear the difference in the next thing NVDA says. Pressing Cancel puts everything back the way it was.

## Presets

Cedar ships with Flat, Clarity, Warm, Bright, Bass boost, Less sibilance, Small speakers, Podcast voice, Telephone and Noisy room. Selecting a preset replaces every equalizer setting, so nothing is left over from whatever you had before.

To make your own, set the sliders how you like them, press Save as preset, and give it a name. Your presets appear in the same list, after the built in ones.

The presets were tuned by frequency reasoning rather than by ear against real voices, so treat them as starting points. Different synthesizers have quite different spectral balance, and you may want to move a band or two.

## Advanced settings

Tick Enable advanced settings and the Advanced settings button becomes available. The advanced dialog gives you:
- A Band list covering five bands: Bass and Treble are shelves, Low mid, Mids and Presence are peaking filters.
- Gain as a slider, Frequency as a spin control you can type into, and Width or slope as a named list running from very wide to extremely narrow, so you can put a band exactly where a particular voice needs it.
- Remove low frequency rumble, a high pass filter for synthesizers with a heavy low end.
- Remove high frequency hiss, a low pass filter for synthesizers with a harsh or noisy top end.
- Soften loud peaks instead of clipping them, which rounds off peaks that would otherwise distort.
- Also equalize NVDA sounds and beeps, which extends the equalizer beyond speech.

## Commands

Cedar adds commands for toggling the equalizer, cycling presets, nudging bass, mids and treble, and opening the settings. None of them have a key assigned by default, so nothing you already use is taken away. Assign the ones you want under NVDA menu, Preferences, Input Gestures, in the Cedar equalizer category.

## Which synthesizers work

Cedar filters audio on its way from the synthesizer to your sound card, at the point NVDA hands it over. Every synthesizer that plays through NVDA works, which includes eSpeak NG, Windows OneCore, SAPI 4, SAPI 5, and most add-on synthesizers.

A synthesizer that talks to the sound card itself, rather than handing its audio to NVDA, bypasses Cedar entirely. If a voice sounds unchanged no matter what you do to the sliders, that is why. Cedar also leaves 8 bit and 32 bit audio alone and only processes the 16 bit audio that synthesizers normally produce.

## Performance

Filtering is done in Python, and on a typical voice at 22050 Hz it costs about two percent of one processor core with three bands active. When every gain is at zero Cedar detects that the settings are flat and steps out of the audio path completely, so a disabled or flat equalizer costs nothing at all.

## How it works

NVDA hands every synthesizer's audio to nvwave.WavePlayer.feed on its way to the sound card. Cedar wraps that method, and filters the 16 bit audio through a cascade of biquad filters built from the RBJ audio EQ cookbook formulas. The WavePlayer knows whether a stream is speech or one of NVDA's own sounds, which is how Cedar leaves beeps alone unless you ask otherwise.

## Building from source

Requires Python 3.11 or later. No other packages are needed.
- py build.py builds the nvda-addon file, generating the manifest and readme.html along the way.
- py build.py --scratchpad copies the plugin straight into NVDA's scratchpad, for testing without reinstalling. Enable the scratchpad first under NVDA menu, Preferences, Settings, Advanced, then reload plugins with NVDA+control+F3.
- py build.py --clean removes the build output.
- py tests/test_cedar.py runs the test suite against stubbed NVDA modules, so it works outside NVDA.

## Releases

Pushing a tag of the form v1.0 builds the add-on and publishes it. Each version keeps its own release, and a moving latest tag always carries the newest build under a fixed name, so this link never changes:

https://github.com/tunmi13productions/cedar/releases/latest/download/cedar.nvda-addon

The tag has to match addon_version in buildVars.py or the build fails on purpose.

## License

GNU General Public License version 2.
