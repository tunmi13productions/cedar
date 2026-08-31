"""Packages Cedar into a .nvda-addon file, or installs it into NVDA's scratchpad for testing.

	py build.py                 build cedar-<version>.nvda-addon
	py build.py --scratchpad    copy the plugin into NVDA's scratchpad and stop
	py build.py --clean         remove build output
"""

import html
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.join(ROOT, "addon")
sys.path.insert(0, ROOT)

from buildVars import addon_info, addon_source_dirs  # noqa: E402

MANIFEST_TEMPLATE = """name = {addon_name}
summary = "{addon_summary}"
description = \"\"\"{addon_description}\"\"\"
author = "{addon_author}"
url = {addon_url}
version = {addon_version}
docFileName = {addon_docFileName}
minimumNVDAVersion = {addon_minimumNVDAVersion}
lastTestedNVDAVersion = {addon_lastTestedNVDAVersion}
updateChannel = {addon_updateChannel}
"""

_INLINE = (
	(re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
	(re.compile(r"`(.+?)`"), r"<code>\1</code>"),
)


def _inline(text):
	text = html.escape(text)
	for pattern, repl in _INLINE:
		text = pattern.sub(repl, text)
	return text


def markdownToHtml(markdown, title):
	"""Convert the subset of markdown the readme uses: headings, lists, paragraphs, bold and code."""
	out = []
	listTag = None

	def closeList():
		nonlocal listTag
		if listTag:
			out.append("</%s>" % listTag)
			listTag = None

	for line in markdown.splitlines():
		stripped = line.strip()
		if not stripped:
			closeList()
			continue
		heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
		if heading:
			closeList()
			level = len(heading.group(1))
			out.append("<h%d>%s</h%d>" % (level, _inline(heading.group(2)), level))
			continue
		bullet = re.match(r"^[-*]\s+(.*)$", stripped)
		numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
		if bullet or numbered:
			wanted = "ul" if bullet else "ol"
			if listTag != wanted:
				closeList()
				out.append("<%s>" % wanted)
				listTag = wanted
			out.append("<li>%s</li>" % _inline((bullet or numbered).group(1)))
			continue
		closeList()
		out.append("<p>%s</p>" % _inline(stripped))
	closeList()
	return (
		'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
		"<title>%s</title>\n</head>\n<body>\n%s\n</body>\n</html>\n" % (html.escape(title), "\n".join(out))
	)


def writeManifest(path):
	values = dict(addon_info)
	values["addon_url"] = values["addon_url"] or "None"
	values["addon_updateChannel"] = values["addon_updateChannel"] or "None"
	with open(path, "w", encoding="utf-8", newline="\n") as f:
		f.write(MANIFEST_TEMPLATE.format(**values))


def writeDocs():
	source = os.path.join(ROOT, "readme.md")
	if not os.path.isfile(source):
		return
	target = os.path.join(ADDON_DIR, "doc", "en", addon_info["addon_docFileName"])
	os.makedirs(os.path.dirname(target), exist_ok=True)
	with open(source, encoding="utf-8") as f:
		markdown = f.read()
	with open(target, "w", encoding="utf-8", newline="\n") as f:
		f.write(markdownToHtml(markdown, addon_info["addon_summary"]))
	print("wrote %s" % os.path.relpath(target, ROOT))


def packageName():
	return "%s-%s.nvda-addon" % (addon_info["addon_name"], addon_info["addon_version"])


def build():
	writeDocs()
	manifestPath = os.path.join(ADDON_DIR, "manifest.ini")
	writeManifest(manifestPath)
	target = os.path.join(ROOT, packageName())
	with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
		archive.write(manifestPath, "manifest.ini")
		for sourceDir in addon_source_dirs:
			base = os.path.join(ADDON_DIR, sourceDir)
			if not os.path.isdir(base):
				continue
			for dirPath, dirNames, fileNames in os.walk(base):
				dirNames[:] = [d for d in dirNames if d != "__pycache__"]
				for fileName in fileNames:
					if fileName.endswith((".pyc", ".pyo")):
						continue
					full = os.path.join(dirPath, fileName)
					archive.write(full, os.path.relpath(full, ADDON_DIR).replace(os.sep, "/"))
	print("built %s" % os.path.relpath(target, ROOT))


def scratchpadPath():
	appData = os.environ.get("APPDATA")
	if not appData:
		raise SystemExit("APPDATA is not set, cannot find NVDA's scratchpad")
	return os.path.join(appData, "nvda", "scratchpad", "globalPlugins")


def installToScratchpad():
	target = os.path.join(scratchpadPath(), "cedar")
	if os.path.isdir(target):
		shutil.rmtree(target)
	shutil.copytree(
		os.path.join(ADDON_DIR, "globalPlugins", "cedar"),
		target,
		ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
	)
	print("copied to %s" % target)
	print("Restart NVDA plugins with NVDA+control+F3 to load it.")


def clean():
	for name in os.listdir(ROOT):
		if name.endswith(".nvda-addon"):
			os.remove(os.path.join(ROOT, name))
			print("removed %s" % name)
	manifest = os.path.join(ADDON_DIR, "manifest.ini")
	if os.path.isfile(manifest):
		os.remove(manifest)
		print("removed addon/manifest.ini")


if __name__ == "__main__":
	args = sys.argv[1:]
	if "--clean" in args:
		clean()
	elif "--scratchpad" in args:
		installToScratchpad()
	else:
		build()
