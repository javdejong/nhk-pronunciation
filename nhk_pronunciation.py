# -*- coding: utf-8 -*-

from collections import namedtuple

import io
import re
import os
import sys
import time

if sys.version_info.major == 3:
    from PyQt5.QtWidgets import *
    import pickle
else:
    import cPickle as pickle

from aqt import mw
from aqt.qt import *
from aqt.utils import showText

# ************************************************
#                Global Variables                *
# ************************************************

# Paths to the database files and this particular file
dir_path = os.path.dirname(os.path.normpath(__file__))
thisfile = os.path.join(dir_path, "nhk_pronunciation.py")
derivative_database = os.path.join(dir_path, "nhk_pronunciation.csv")
derivative_pickle = os.path.join(dir_path, "nhk_pronunciation.pickle")
accent_database = os.path.join(dir_path, "ACCDB_unicode.csv")

# "Class" declaration
AccentEntry = namedtuple('AccentEntry', ['NID','ID','WAVname','K_FLD','ACT','midashigo','nhk','kanjiexpr','NHKexpr','numberchars','nopronouncepos','nasalsoundpos','majiri','kaisi','KWAV','midashigo1','akusentosuu','bunshou','ac'])

# The main dict used to store all entries
thedict = {}


if sys.version_info.major == 2:
    import json
    config = json.load(io.open(os.path.join(dir_path, 'nhk_pronunciation_config.json'), 'r'))
else:
    config = mw.addonManager.getConfig(__name__)

# ************************************************
#                  Helper functions              *
# ************************************************
def katakana_to_hiragana(to_translate):
    hiragana = u'がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ' \
               u'あいうえおかきくけこさしすせそたちつてと' \
               u'なにぬねのはひふへほまみむめもやゆよらりるれろ' \
               u'わをんぁぃぅぇぉゃゅょっ'
    katakana = u'ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ' \
               u'アイウエオカキクケコサシスセソタチツテト' \
               u'ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ' \
               u'ワヲンァィゥェォャュョッ'
    katakana = [ord(char) for char in katakana]
    translate_table = dict(zip(katakana, hiragana))
    return to_translate.translate(translate_table)


# ************************************************
#           Database generation functions        *
# ************************************************
def format_entry(e):
    """ Format an entry from the data in the original database to something that uses html """
    txt = e.midashigo1
    strlen = len(txt)
    acclen = len(e.ac)
    accent = "0"*(strlen-acclen) + e.ac

    # Get the nasal positions
    nasal = []
    if e.nasalsoundpos:
        positions = e.nasalsoundpos.split('0')
        for p in positions:
            if p:
                nasal.append(int(p))
            if not p:
                # e.g. "20" would result in ['2', '']
                nasal[-1] = nasal[-1] * 10

    # Get the no pronounce positions
    nopron = []
    if e.nopronouncepos:
        positions = e.nopronouncepos.split('0')
        for p in positions:
            if p:
                nopron.append(int(p))
            if not p:
                # e.g. "20" would result in ['2', '']
                nopron[-1] = nopron[-1] * 10

    outstr = ""
    overline = False

    for i in range(strlen):
        a = int(accent[i])
        # Start or end overline when necessary
        if not overline and a > 0:
            outstr = outstr + '<span class="overline">'
            overline = True
        if overline and a == 0:
            outstr = outstr + '</span>'
            overline = False

        if (i+1) in nopron:
            outstr = outstr + '<span class="nopron">'

        # Add the character stuff
        outstr = outstr + txt[i]

        # Add the pronunciation stuff
        if (i+1) in nopron:
            outstr = outstr + "</span>"
        if (i+1) in nasal:
            outstr = outstr + '<span class="nasal">&#176;</span>'

        # If we go down in pitch, add the downfall
        if a == 2:
            outstr = outstr + '</span>&#42780;'
            overline = False

    # Close the overline if it's still open
    if overline:
        outstr = outstr + "</span>"

    return outstr


def build_database():
    """ Build the derived database from the original database """
    tempdict = {}
    entries = []

    f = io.open(accent_database, 'r', encoding="utf-8")
    for line in f:
        line = line.strip()
        substrs = re.findall(r'(\{.*?,.*?\})', line)
        substrs.extend(re.findall(r'(\(.*?,.*?\))', line))
        for s in substrs:
            line = line.replace(s, s.replace(',', ';'))
        entries.append(AccentEntry._make(line.split(",")))
    f.close()

    for e in entries:
        textentry = format_entry(e)

        # A tuple holding both the spelling in katakana, and the katakana with pitch/accent markup
        kanapron = (e.midashigo, textentry)

        # Add expressions for both
        for key in [e.nhk, e.kanjiexpr]:
            if key in tempdict:
                if kanapron not in tempdict[key]:
                    tempdict[key].append(kanapron)
            else:
                tempdict[key] = [kanapron]

    o = io.open(derivative_database, 'w', encoding="utf-8")

    for key in tempdict.keys():
        for kana, pron in tempdict[key]:
            o.write("%s\t%s\t%s\n" % (key, kana, pron))

    o.close()


def read_derivative():
    """ Read the derivative file to memory """
    f = io.open(derivative_database, 'r', encoding="utf-8")

    for line in f:
        key, kana, pron = line.strip().split("\t")
        kanapron = (kana, pron)
        if key in thedict:
            if kanapron not in thedict[key]:
                thedict[key].append(kanapron)
        else:
            thedict[key] = [kanapron]

    f.close()


# ************************************************
#              Lookup Functions                  *
# ************************************************
def inline_style(txt):
    """ Map style classes to their inline version """

    for k, v in config["styles"].items():
        txt = txt.replace(k, v)

    return txt


def getPronunciations(expr):
    """ Search pronuncations for a particular expression """
    ret = []
    if expr in thedict:
        for kana, pron in thedict[expr]:
            inlinepron = inline_style(pron)

            if config["pronunciationHiragana"]:
                inlinepron = katakana_to_hiragana(inlinepron)

            if inlinepron not in ret:
                ret.append(inlinepron)
    return ret


def lookupPronunciation(expr):
    """ Show the pronunciation when the user does a manual lookup """
    ret = getPronunciations(expr)

    thehtml = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">
<HTML>
<HEAD>
<style>
body {
font-size: 30px;
}
</style>
<TITLE>Pronunciations</TITLE>
<meta charset="UTF-8" />
</HEAD>
<BODY>
%s
</BODY>
</HTML>
""" % ("<br/><br/>\n".join(ret))

    showText(thehtml, type="html")


def onLookupPronunciation():
    """ Do a lookup on the selection """
    text = mw.web.selectedText()
    text = text.strip()
    if not text:
        showInfo(_("Empty selection."))
        return
    lookupPronunciation(text)


# ************************************************
#              Interface                         *
# ************************************************

def createMenu():
    """ Add a hotkey and menu entry """
    if not getattr(mw.form, "menuLookup", None):
        ml = QMenu()
        ml.setTitle("Lookup")
        mw.form.menuTools.addAction(ml.menuAction())

    ml = mw.form.menuLookup
    # add action
    a = QAction(mw)
    a.setText("...pronunciation")
    ml.addAction(a)
    a.triggered.connect(onLookupPronunciation)


def setupBrowserMenu(browser):
    """ Add menu entry to browser window """
    a = QAction("Bulk-add Pronunciations", browser)
    a.triggered.connect(lambda: onRegenerate(browser))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(a)


def onRegenerate(browser):
    regeneratePronunciations(browser.selectedNotes())


def get_src_dst_fields(fields):
    """ Set source and destination fieldnames """
    src = None
    srcIdx = None
    dst = None
    dstIdx = None

    for i, f in enumerate(config["srcFields"]):
        if f in fields:
            src = f
            srcIdx = i
            break

    for i, f in enumerate(config["dstFields"]):
        if f in fields:
            dst = f
            dstIdx = i
            break

    return src, srcIdx, dst, dstIdx

def add_pronunciation_once(fields, model, data, n):
    """ When possible, temporarily set the pronunciation to a field """

    # Check if this is a supported note type. If it is not, return.
    # If no note type has been specified, we always continue the lookup proces.
    if config["noteTypes"] and not any(nt.lower() in model['name'].lower() for nt in config["noteTypes"]):
        return fields

    src, srcIdx, dst, dstIdx = get_src_dst_fields(fields)

    if src is None or dst is None:
        return fields

    # Only add the pronunciation if there's not already one in the pronunciation field
    if not fields[dst]:
        prons = getPronunciations(fields[src])
        fields[dst] = "  ***  ".join(prons)

    return fields

def add_pronunciation_focusLost(flag, n, fidx):
    # Check if this is a supported note type. If it is not, return.
    # If no note type has been specified, we always continue the lookup proces.
    if config["noteTypes"] and not any(nt.lower() in n.model()['name'].lower() for nt in config["noteTypes"]):
        return flag

    from aqt import mw
    fields = mw.col.models.fieldNames(n.model())

    src, srcIdx, dst, dstIdx = get_src_dst_fields(fields)

    if not src or not dst:
        return flag

    # dst field already filled?
    if n[dst]:
        return flag

    # event coming from src field?
    if fidx != srcIdx:
        return flag

    # grab source text
    srcTxt = mw.col.media.strip(n[src])
    if not srcTxt:
        return flag

    # update field
    try:
        prons = getPronunciations(srcTxt)
        n[dst] = "  ***  ".join(prons)
    except Exception as e:
        raise
    return True


def regeneratePronunciations(nids):
    mw.checkpoint("Bulk-add Pronunciations")
    mw.progress.start()
    for nid in nids:
        note = mw.col.getNote(nid)

        # Check if this is a supported note type. If it is not, skip.
        # If no note type has been specified, we always continue the lookup proces.
        if config["noteTypes"] and not any(nt.lower() in note.model()['name'].lower() for nt in config["noteTypes"]):
            continue

        src, srcIdx, dst, dstIdx = get_src_dst_fields(note)

        if src is None or dst is None:
            continue

        if note[dst] and not config["regenerateReadings"]:
            # already contains data, skip
            continue

        srcTxt = mw.col.media.strip(note[src])
        if not srcTxt.strip():
            continue

        prons = getPronunciations(srcTxt.strip())
        note[dst] = "  ***  ".join(prons)

        note.flush()
    mw.progress.finish()
    mw.reset()


# ************************************************
#                   Main                         *
# ************************************************

# First check that either the original database, or the derivative text file are present:
if not os.path.exists(derivative_database) and not os.path.exists(accent_database):
    raise IOError("Could not locate the original base or the derivative database!")

# Generate the derivative database if it does not exist yet
if (os.path.exists(accent_database) and not os.path.exists(derivative_database)) or (os.path.exists(accent_database) and os.stat(thisfile).st_mtime > os.stat(derivative_database).st_mtime):
    build_database()

# If a pickle exists of the derivative file, use that. Otherwise, read from the derivative file and generate a pickle.
if  (os.path.exists(derivative_pickle) and
    os.stat(derivative_pickle).st_mtime > os.stat(derivative_database).st_mtime):
    f = io.open(derivative_pickle, 'rb')
    thedict = pickle.load(f)
    f.close()
else:
    read_derivative()
    f = io.open(derivative_pickle, 'wb')
    pickle.dump(thedict, f, pickle.HIGHEST_PROTOCOL)
    f.close()

# Create the manual look-up menu entry
createMenu()

from anki.hooks import addHook

addHook("mungeFields", add_pronunciation_once)

addHook('editFocusLost', add_pronunciation_focusLost)

# Bulk add
addHook("browser.setupMenus", setupBrowserMenu)
