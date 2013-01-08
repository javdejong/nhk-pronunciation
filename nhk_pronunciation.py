# -*- coding: utf-8 -*-

from collections import namedtuple
import re
import codecs
import os
import cPickle
import time

from aqt import mw
from aqt.qt import *
from aqt.utils import showText

import japanese


# ************************************************
#                User Options                    *
# ************************************************

# Style mappings (edit this if you want different colors etc.):
styles = {'class="overline"': 'style="text-decoration:overline;"',
          'class="nopron"':   'style="color: royalblue;"',
          'class="nasal"':    'style="color: red;"',
          '&#42780;': '&#42780;'}

# Expression, Reading and Pronunciation fields (edit if the names of your fields are different)
exprField = 'Expression'
readField = 'Reading'
pronField = 'Pronunciation'

# Regenerate readings even if they already exist?
regenerate_readings = False


# ************************************************
#                Global Variables                *
# ************************************************

# Paths to the database files and this particular file
thisfile = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.py")
derivative_database = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.csv")
derivative_pickle = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.pickle")
accent_database = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.csv")

# "Class" declaration
AccentEntry = namedtuple('AccentEntry', ['NID','ID','WAVname','K_FLD','ACT','midashigo','nhk','kanjiexpr','NHKexpr','numberchars','nopronouncepos','nasalsoundpos','majiri','kaisi','KWAV','midashigo1','akusentosuu','bunshou','ac'])

# The main dict used to store all entries
thedict = {}


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

    f = codecs.open(accent_database, 'r', 'utf8')
    for line in f:
        line = re.sub("\{(.*),(.*)\}", "\{\1;\2\}", line.strip())
        line = re.sub("\((.*),(.*)\)", "\(\1;\2\)   ", line.strip())
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

    o = codecs.open(derivative_database, 'w', 'utf8')

    for key in tempdict.iterkeys():
        for kana, pron in tempdict[key]:
            o.write("%s\t%s\t%s\n" % (key, kana, pron))

    o.close()


def read_derivative():
    """ Read the derivative file to memory """
    f = codecs.open(derivative_database, 'r', 'utf8')

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

    for key in styles.iterkeys():
        txt = txt.replace(key, styles[key])

    return txt


def getPronunciations(expr):
    """ Search pronuncations for a particular expression """
    ret = []
    if expr in thedict:
        for kana, pron in thedict[expr]:
            inlinepron = inline_style(pron)
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
    japanese.lookup.initLookup()
    mw.lookup.selection(lookupPronunciation)


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
    a.setText("...pronunciation on alc")
    a.setShortcut("Ctrl+6")
    ml.addAction(a)
    mw.connect(a, SIGNAL("triggered()"), onLookupPronunciation)


def setupBrowserMenu(browser):
    """ Add menu entry to browser window """
    a = QAction("Bulk-add Pronunciations", browser)
    browser.connect(a, SIGNAL("triggered()"), lambda e=browser: onRegenerate(e))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(a)


def onRegenerate(browser):
    regeneratePronunciations(browser.selectedNotes())


def add_pronunciation_once(fields, model, data, n):
    """ When possible, temporarily set the pronunciation to a field """

    if "japanese" not in model['name'].lower():
        return fields

    if pronField not in fields or exprField not in fields:
        return fields

    # Only add the pronunciation if there's not already one in the pronunciation field
    if not fields[pronField]:
        prons = getPronunciations(fields[exprField])
        fields[pronField] = "  ***  ".join(prons)

    return fields


def regeneratePronunciations(nids):
    mw.checkpoint("Bulk-add Pronunciations")
    mw.progress.start()
    for nid in nids:
        note = mw.col.getNote(nid)
        if "japanese" not in note.model()['name'].lower():
            continue

        if pronField not in note or exprField not in note:
            continue

        if note[pronField] and not regenerate_readings:
            # already contains data, skip
            continue

        srcTxt = mw.col.media.strip(note[exprField])
        if not srcTxt.strip():
            continue

        prons = getPronunciations(srcTxt)
        note[pronField] = "  ***  ".join(prons)

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
    f = open(derivative_pickle, 'rb')
    thedict = cPickle.load(f)
    f.close()
else:
    read_derivative()
    f = open(derivative_pickle, 'wb')
    cPickle.dump(thedict, f, cPickle.HIGHEST_PROTOCOL)
    f.close()

# Create the manual look-up menu entry
createMenu()

from anki.hooks import addHook

addHook("mungeFields", add_pronunciation_once)


# Bulk add
addHook("browser.setupMenus", setupBrowserMenu)
