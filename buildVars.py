"""Add-on metadata, read by build.py to generate the manifest."""

addon_info = {
	"addon_name": "cedar",
	# Translators: summary of the add-on, shown in NVDA's add-on manager.
	"addon_summary": "Cedar",
	# Translators: long description of the add-on, shown in NVDA's add-on manager.
	"addon_description": (
		"Cedar is a Custom Equalizer Designed for Audible Reading. "
		"It gives NVDA its own equalizer for speech, with bass, mid and treble controls, "
		"a set of presets, and a full parametric equalizer behind an advanced settings option. "
		"Warning: this add-on was vibe coded with Claude Opus 5, Anthropic's AI model. "
		"Expect oddities, and please report anything that behaves strangely."
	),
	"addon_version": "1.5",
	"addon_author": "tunmi13 productions <tunmi12@mail.com>",
	"addon_url": "https://github.com/tunmi13productions/cedar",
	"addon_docFileName": "readme.html",
	"addon_minimumNVDAVersion": "2024.1",
	"addon_lastTestedNVDAVersion": "2025.3",
	"addon_updateChannel": None,
}

# Paths inside addon/ that are copied into the package.
addon_source_dirs = ["globalPlugins", "doc", "locale"]
