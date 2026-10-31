# Cedar

Cedar is a Custom Equalizer Designed for Audible Reading. It gives NVDA its own equalizer for speech, so you can shape the tone of any synthesizer without touching your system sound settings.

Most people only ever need three controls: bass, mids and treble. Those are the first thing you meet. Everything else, including a full parametric equalizer, sits behind an advanced settings checkbox so it stays out of your way until you want it.

## A warning before you install

This add-on was vibe coded with Claude Opus 5, Anthropic's AI model. It works, and it has a test suite, but it was not written line by line by a human. Expect oddities. If something behaves strangely, please report it rather than assuming it is meant to work that way.

Cedar filters NVDA's speech audio on its way to your sound card, so if it goes wrong it can affect whether you hear NVDA at all. To remove it normally, go to NVDA menu, Tools, Add-on Store, open the Installed add-ons tab and uninstall it from there. If it ever goes wrong badly enough that you cannot hear NVDA well enough to do that, delete this folder and restart NVDA:

%appdata%\nvda\addons\cedar

## Download

https://github.com/tunmi13productions/cedar/releases/latest/download/cedar.nvda-addon

That link always gives you the newest build. Press enter on the downloaded file to install it, and restart NVDA when prompted.

Cedar runs on NVDA 2024.1 through 2026.3, including every 2025 release. NVDA 2026.1 moved to 64 bit and to Python 3.13, which broke a great many add-ons, but Cedar ships no compiled code and uses no APIs that changed in 2026.1, 2026.2 or 2026.3, so one build covers the whole range.

## Using Cedar

Open NVDA menu, Preferences, Settings, and choose the Cedar equalizer category. The panel has:
- Settings for, which chooses what the controls below edit: the shared settings, or one particular synthesizer. See Settings for each synthesizer below.
- Enable the Cedar equalizer, which switches all processing on or off.
- Give this synthesizer its own settings, where the checkbox names the synthesizer chosen under Settings for.
- Preset, a list of ready made settings plus any you have saved yourself.
- Show levels as, which chooses how every level in Cedar reads. 0 to 100 puts flat at 50 and is the default, matching how NVDA's own rate, pitch and volume already read. Decibels runs from -18 to 18 with 0 flat, if you would rather have the real units. It changes the display only, never the sound.
- Bass, Mids and Treble, adjustable with the arrow keys or by typing a number.
- Overall volume trim, which raises or lowers the whole speech level.
- Prevent distortion from boosted bands, which quietly compensates for the level your boosts add. Leave this on unless you know you want the extra loudness.
- Also equalize NVDA sounds and beeps, which extends the equalizer beyond speech.
- Test voice, which speaks a sample sentence so you can judge a setting by ear.
- Save as preset, Delete preset and Reset to flat.

Changes apply as you make them, so NVDA's own speech is the preview. Change the bass and you hear the difference in the next thing NVDA says. Pressing Cancel puts everything back the way it was.

## Presets

Cedar ships with Flat, Clarity, Warm, Bright, Bass boost, Less sibilance, Small speakers, Podcast voice, Telephone and Noisy room. Selecting a preset replaces every equalizer setting, so nothing is left over from whatever you had before.

To make your own, set the controls how you like them, press Save as preset, and give it a name. Your presets appear in the same list, after the built in ones.

The presets were tuned by frequency reasoning rather than by ear against real voices, so treat them as starting points. Different synthesizers have quite different spectral balance, and you may want to move a band or two.

## Settings for each synthesizer

By default every synthesizer shares one set of equalizer settings. You can give any synthesizer its own copy instead, and Cedar switches to it by itself whenever that synthesizer becomes active. You do not have to switch synthesizers to set this up.

The Settings for list at the top of the panel chooses what the rest of the panel edits. It starts on the synthesizer you are using, and lists:
- Shared settings, used by every synthesizer that does not have its own.
- Every installed synthesizer, marked own settings or uses shared settings. The one speaking now is also marked active. No speech is left out, since it makes no sound to equalize.
- Any synthesizer that has its own settings but is no longer installed, so you can still remove them.

Choose a synthesizer and tick Give this synthesizer its own settings, and it gets its own copy, starting from what it plays now. From then on, the bands, preset, volume trim and filters you change, including in the advanced dialog, apply only to that synthesizer. Untick it to put that synthesizer back on the shared settings. Choosing a synthesizer that uses the shared settings, without ticking the box, edits the shared settings.

Some ways to use it:
- To equalize only one synthesizer, leave the shared settings on Flat, choose that synthesizer, give it its own settings and adjust them. Every other synthesizer is left untouched.
- To give each synthesizer its own preset, choose each one in turn, give it its own settings, and pick a preset.

NVDA's speech, and the Test voice button, always use the synthesizer that is speaking now, so you only hear your changes straight away when you are editing the settings that synthesizer uses. Changes to another synthesizer are kept and take effect when you switch to it.

Whether Cedar is on, how levels read, whether sounds are equalized and your saved presets are always shared. Settings are kept per synthesizer, not per voice, so every SAPI 5 voice shares one set. The commands for nudging bass, mids and treble and cycling presets always adjust whatever the speaking synthesizer is using.

## Advanced settings

Tick Enable advanced settings and the Advanced settings button becomes available. The advanced dialog gives you:
- A Band list covering five bands: Bass and Treble are shelves, Low mid, Mids and Presence are peaking filters.
- Gain and Frequency as spin controls you can type into, and Width or slope as a named list running from very wide to extremely narrow, so you can put a band exactly where a particular voice needs it. Gain follows whichever scale you picked on the main panel.
- Remove low frequency rumble, for synthesizers with a heavy low end.
- Remove high frequency hiss, for synthesizers with a harsh or noisy top end.
- Soften loud peaks instead of clipping them, which rounds off peaks that would otherwise distort.

## Commands

Cedar adds commands for toggling the equalizer, cycling presets, nudging bass, mids and treble, and opening the settings. None of them have a key assigned by default, so nothing you already use is taken away. Assign the ones you want under NVDA menu, Preferences, Input Gestures, in the Cedar equalizer category.

## Which synthesizers work

Every synthesizer that plays its audio through NVDA works, which includes eSpeak NG, Windows OneCore, SAPI 4, SAPI 5, and most add-on synthesizers.

A synthesizer that talks to the sound card itself, rather than handing its audio to NVDA, bypasses Cedar entirely. If a voice sounds unchanged no matter what you do to the controls, that is why.

## Building from source

Requires Python 3.11 or later. No other packages are needed.
- py build.py builds the add-on file.
- py build.py --scratchpad copies the plugin into NVDA's scratchpad for testing, then reload plugins with NVDA+control+F3.
- py tests/test_cedar.py runs the tests.

## License

GNU General Public License version 2.
