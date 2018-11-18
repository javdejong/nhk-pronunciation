from zipfile import ZipFile

with ZipFile('release_20.zip', 'w') as z:
    z.write('ACCDB_unicode.csv')
    z.write('config.json', 'nhk_pronunciation_config.json')
    z.write('config.md', 'nhk_pronunciation_config.md')
    z.write('nhk_pronunciation.py')

with ZipFile('release_21.zip', 'w') as z:
    z.write('__init__.py')
    z.write('ACCDB_unicode.csv')
    z.write('config.json')
    z.write('config.md')
    z.write('nhk_pronunciation.py')
