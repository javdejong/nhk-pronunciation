# nhk-pronunciation
Anki2 Add-On to look-up the pronunciation of Japanese expressions.

2.0 version updated to add support for parsing fields containing multiple/conjugated words, 
whether they are inside sentences/fragments or separated by punctuation/symbols, etc. Also adds optional expression field auto-correction to 原形 (citation/dictionary form); accent-dependent colorization to automate [this process](https://www.youtube.com/watch?v=cy7GvwI7uV8&t=4m10s); and bug fixes. See commits for full details.


Installation:
1. Make sure you have the [NHK accent plugin](https://ankiweb.net/shared/info/932119536) installed already.
2. Open your Anki addons folder by going to Tools -> Add-ons - Open Add-ons Folder in Anki.
3. Copy the file nhk_pronunciation.py into your addons folder, overwriting the old nhk_pronunciation.py file.
4. You need to copy the bs4 folder too if you don't have one. This dependency may by removed in the future, but for now you need it.
