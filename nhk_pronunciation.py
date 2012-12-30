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

thisfile = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.py")
derivative_database = os.path.join(mw.pm.addonFolder(), "nhk_pronunciation.csv")
accent_database = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.csv")
accent_pickle = os.path.join(mw.pm.addonFolder(), "ACCDB_unicode.pickle")

AccentEntry = namedtuple('AccentEntry', ['NID','ID','WAVname','K_FLD','ACT','midashigo','nhk','kanjiexpr','NHKexpr','numberchars','nopronouncepos','nasalsoundpos','majiri','kaisi','KWAV','midashigo1','akusentosuu','bunshou','ac'])

thedict = {}

""" Formatting an entry using html """
def format_entry(e):
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
            if key in thedict:
                if kanapron not in thedict[key]:
                    thedict[key].append(kanapron)
            else:
                thedict[key] = [kanapron]

def getPronunciations(expr):
    ret = []
    if expr in thedict:
        for kana, pron in thedict[expr]:
            if pron not in ret:
                ret.append(pron)
    return ret

def lookupPronunciation(expr):
    ret = getPronunciations(expr)

    thehtml = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2//EN">
<HTML>
<HEAD>
<style>
body {
font-size: 30px;
}
.overline {
text-decoration:overline;
}
.nasal {
color: red;
}
.nopron {
color: royalblue;
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
    japanese.lookup.initLookup()
    mw.lookup.selection(lookupPronunciation)

def createMenu():
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

def inline_style(txt):
    txt = txt.replace('class="overline"', 'style="text-decoration:overline;"')
    txt = txt.replace('class="nopron"', 'style="color: royalblue;"')
    txt = txt.replace('class="nasal"', 'style="color: red;"')
    return txt

def add_pronunciation(fields, model, data, n):

    if "japanese" not in model['name'].lower():
        return fields

    if "Pronunciation" not in fields or "Expression" not in fields or "Reading" not in fields:
        return fields

    prons = getPronunciations(fields["Expression"])

    # TODO: Find a way to add styles to the reviewer, so we don't have use inline definitions
    prons = [inline_style(x) for x in prons]

    fields["Pronunciation"] = "  ***  ".join(prons)
    return fields

if  (os.path.exists(accent_pickle) and
    os.stat(accent_pickle).st_mtime > os.stat(accent_database).st_mtime and
    os.stat(accent_pickle).st_mtime > os.stat(thisfile).st_mtime):
    f = open(accent_pickle, 'rb')
    thedict = cPickle.load(f)
    f.close()
else:
    build_database()
    f = open(accent_pickle, 'wb')
    cPickle.dump(thedict, f, cPickle.HIGHEST_PROTOCOL)
    f.close()

createMenu()

from anki.hooks import addHook

addHook("mungeFields", add_pronunciation)
