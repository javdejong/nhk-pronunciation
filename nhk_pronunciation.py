# -*- coding: utf-8 -*-

from collections import namedtuple
import re
import codecs
import os
import cPickle
import time
from string import punctuation
from bs4 import BeautifulSoup

from aqt import mw
from aqt.qt import *
from aqt.utils import showText

import japanese
import japanese.lookup
from japanese.reading import MecabController
import sys  


# ************************************************
#                User Options                    *
# ************************************************

# Style mappings (edit this if you want different colors etc.):
styles = {'class="overline"': 'style="text-decoration:overline;"',
          'class="nopron"':   'style="color: royalblue;"',
          'class="nasal"':    'style="color: red;"',
          '&#42780;': '&#42780;'}

# Expression, Reading and Pronunciation fields (edit if the names of your fields are different)
srcFields = ['Expression']    
dstFields = ['Pronunciation']

# Regenerate readings even if they already exist?
regenerate_readings = False

# Use hiragana instead of katakana for readings?
pronunciation_hiragana = False

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

hiragana = u'がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ' \
               u'あいうえおかきくけこさしすせそたちつてと' \
               u'なにぬねのはひふへほまみむめもやゆよらりるれろ' \
               u'わをんぁぃぅぇぉゃゅょっ'
katakana = u'ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ' \
               u'アイウエオカキクケコサシスセソタチツテト' \
               u'ナニヌネノハヒフヘホマミムメモヤユヨラリルレロ' \
               u'ワヲンァィゥェォャュョッ'
mecab = MecabController()
               
#Ref: https://stackoverflow.com/questions/15033196/using-javascript-to-check-whether-a-string-contains-japanese-characters-includi/15034560#15034560               
regex = ur'[^\u3040-\u309f\u30a0-\u30ff\uff66-\uff9f\u4e00-\u9fff\u3400-\u4dbf]+'#+ (?=[A-Za-z ]+–)'
jap_reg = re.compile(regex, re.U)

# ************************************************
#                  Helper functions              *
# ************************************************
def katakana_to_hiragana(to_translate):
    katakana = [ord(char) for char in katakana]
    translate_table = dict(zip(katakana, hiragana))
    return to_translate.translate(translate_table)

def no_kana(srcTxt):
    """removes okurigana at the end of string srcTxt
    
    To avoid creating fake words which will give failed lookups,
    ignores kana in the middle of the word since lots of real 
    words have kana in the middle."""
    kana = r'[' + hiragana + r']*$'
    kana_compiled = re.compile(kana, re.UNICODE)
    return re.sub(kana_compiled, '', srcTxt)

def nix_punctuation(text):
    return ''.join(char for char in text if char not in punctuation)

def multi_lookup_helper(srcTxt_all, lookup_func):
    """
    Gets the pronunciation (or another type of dictionary lookup)
    for both the raw text and it without okurigana
    """
    prons = []
    for srcTxt in srcTxt_all:
        kanjiTxt = no_kana(srcTxt)
        new_prons = lookup_func(srcTxt)       
        if new_prons:
            prons.extend(new_prons)
        elif srcTxt != kanjiTxt:
            new_stripped_prons = lookup_func(kanjiTxt)
            if new_stripped_prons:
                prons.extend(new_stripped_prons)
            
    return prons

def japanese_splitter(src):
    """
    Helper function for multi_lookup(src, lookup_func)
    but is its own function for modularity
    
    1) If multiple words are separated by a ・ (Japanese slash)
    or other punctuation, splits into separate words."""
    srcTxt_all = []
    #remove html formatting like color, which Anki uses
    soup = BeautifulSoup(src, "html.parser")
    src = soup.get_text()
    #Separate the src field into individual words
    separated = re.sub(jap_reg, ' ', src)
    separated2 = nix_punctuation(separated)
    srcTxt_all = separated2.replace('・', ' ').split(' ')
    
    return srcTxt_all

def multi_lookup(src, lookup_func, separator = "  ***  "):
    """Has 3 functions: 1) If multiple words are separated by a ・ (Japanese slash)
    or other punctuation, gets the pronunciation for each word. 
    2) Removes useless kana from words and re-searches, in order to get
    all pronunciations (this gets around expressions that include grammar context).
    3) Iterates through all words in the expression, like the Japanese support readings add-on"""
    #NOTE: doesn't handle conjugations 
    #(and probably won't until/unless I integrate it with OJAD)
    srcTxt_all = japanese_splitter(src)
    prons = multi_lookup_helper(srcTxt_all, lookup_func)

    #This is needed to parse things like 料理する and other sentences
    if len(prons) < len(srcTxt_all):
        #parsing with mecab like the Japanese support addon does
        srcTxt_all = re.sub(r'\[.*?\].*?\s+', ' ', mecab.reading(src)).split("[")[0].split(" ")
        prons = multi_lookup_helper(srcTxt_all, lookup_func)

    
    fields_dest = separator.join(prons)
    
    return fields_dest


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

            if pronunciation_hiragana:
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
    a.setText("...pronunciation")
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


def get_src_dst_fields(fields):
    """ Set source and destination fieldnames """
    src = None
    srcIdx = None
    dst = None
    dstIdx = None

    for i, f in enumerate(srcFields):
        if f in fields:
            src = f
            srcIdx = i
            break

    for i, f in enumerate(dstFields):
        if f in fields:
            dst = f
            dstIdx = i
            break

    return src, srcIdx, dst, dstIdx

def add_pronunciation_once(fields, model, data, n):
    """ When possible, temporarily set the pronunciation to a field """

    #if "japanese" not in model['name'].lower():
    #    return fields

    src, srcIdx, dst, dstIdx = get_src_dst_fields(fields)

    if not src or dst is None:
        return fields

    # Only add the pronunciation if there's not already one in the pronunciation field
    if not fields[dst]:
        fields[dst] = multi_lookup(fields[src], getPronunciations)

    return fields

def add_pronunciation_focusLost(flag, n, fidx):
    # japanese model?
    #if "japanese" not in n.model()['name'].lower():
    #    return flag

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
        n[dst] = multi_lookup(srcTxt, getPronunciations)
    except Exception, e:
        raise
    return True


def regeneratePronunciations(nids):
    mw.checkpoint("Bulk-add Pronunciations")
    mw.progress.start()
    for nid in nids:
        note = mw.col.getNote(nid)
        #if "japanese" not in note.model()['name'].lower():
        #    continue

        src, srcIdx, dst, dstIdx = get_src_dst_fields(note)

        if not src or dst is None:
            continue

        if note[dst] and not regenerate_readings:
            # already contains data, skip
            continue

        srcTxt = mw.col.media.strip(note[src])
        if not srcTxt.strip():
            continue
        
        note[dst] = multi_lookup(srcTxt, getPronunciations)

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

#fix encoding:
reload(sys)  
sys.setdefaultencoding('utf8')
    
# Create the manual look-up menu entry
createMenu()

from anki.hooks import addHook

addHook("mungeFields", add_pronunciation_once)

addHook('editFocusLost', add_pronunciation_focusLost)

# Bulk add
addHook("browser.setupMenus", setupBrowserMenu)
