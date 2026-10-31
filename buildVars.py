"""Add-on metadata, read by build.py to generate the manifest."""

addon_info = {
	"addon_name": "cedar",
	# Translators: summary of the add-on, shown in NVDA's add-on manager.
	"addon_summary": "Cedar",
	# Translators: long description of the add-on, shown in NVDA's add-on manager.
	"addon_description": (
		"Cedar is a Custom Equalizer Designed for Audible Reading. "
		"It gives NVDA its own equalizer for speech, with bass, mid and treble controls, "
		"a set of presets, optional separate settings for each synthesizer, "
		"and a full parametric equalizer behind an advanced settings option. "
		"Warning: this add-on was vibe coded with Claude Opus 5, Anthropic's AI model. "
		"Expect oddities, and please report anything that behaves strangely."
	),
	"addon_version": "1.7",
	# Translators: what changed in this version, shown in NVDA's add-on store.
	"addon_changelog": (
		"Any synthesizer can now have its own equalizer settings, used whenever it is active. "
		"The new Settings for list edits the shared settings or any installed synthesizer "
		"without switching to it. "
		"Also equalize NVDA sounds and beeps has moved from the advanced dialog to the main panel. "
		"Tested with NVDA 2026.3, and still supports every 2025 release."
	),
	"addon_author": "tunmi13 <tunmi12@mail.com>",
	"addon_url": "https://github.com/tunmi13productions/cedar",
	"addon_docFileName": "readme.html",
	"addon_minimumNVDAVersion": "2024.1",
	"addon_lastTestedNVDAVersion": "2026.3",
	"addon_updateChannel": None,
}

# Paths inside addon/ that are copied into the package.
addon_source_dirs = ["globalPlugins", "doc", "locale"]
