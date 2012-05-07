from __future__ import division
import os, sys, subprocess, shutil
from lxml import etree
import Image
from siyavula.transforms import pspicture2png, tikzpicture2png
import hashlib

print "Usage: %s input.xml [input2.xml ...]"%sys.argv[0]
argv = list(sys.argv)
del argv[0]

namespaces = {
    'style': "http://siyavula.com/cnxml/style/0.1",
}
pageWidth = 764
cachePath = '_plone_ignore_/cache/'

def check_info_hash(iElement):
    import hashlib
    infoHash = hashlib.md5(etree.tostring(iElement, with_tail=False)).hexdigest()
    infoPath = os.path.join(cachePath, 'info', infoHash)
    state = 'unchanged'
    try:
        with open(infoPath, 'rt') as fp:
            infoDict = eval(fp.read())
        for (path, oldHash) in infoDict['dependencies']:
            with open(path, 'rb') as fp:
                newHash = hashlib.md5(fp.read()).hexdigest()
            if newHash != oldHash:
                state = 'changed'
                break
    except IOError:
        state = 'new'
    return infoHash, infoPath, state

def create_directory_for(iPath):
    import os
    try:
        os.makedirs(os.path.dirname(iPath))
    except OSError: # Already exists
        pass

for xmlFilename in argv:
    print
    print 'Processing', xmlFilename
    try:
        with open(xmlFilename, 'rt') as fp:
            xml = fp.read()
    except IOError:
        print 'ERROR: Could not open file. Skipping.'

    # Strip comments
    pos = 0
    while True:
        start = xml.find('<!--', pos)
        if start == -1:
            break
        stop = xml.find('-->', start)
        assert stop != -1
        stop += 3
        xml = xml[:start] + xml[stop:]
        pos = start

    dom = etree.fromstring(xml)

    # Find all images, determine what width should be, determine what width is, resize from original where necessary
    for imageNode in dom.xpath('//image'):

        # Check if this image needs to be recached
        infoHash, infoPath, state = check_info_hash(imageNode)
        if state == 'unchanged':
            continue

        infoDict = {}
        srcNode = imageNode.find('src')
        if (srcNode is None) or (srcNode.text is None):
            print 'ERROR: image with no src'
            print etree.tostring(imageNode)
            continue
        imagePath = srcNode.text.strip()
        with open(imagePath, 'rb') as fp:
            infoDict['dependencies'] = [(imagePath, hashlib.md5(fp.read()).hexdigest())]

        print {'new': 'Creating', 'changed': 'Updating'}[state], imagePath

        inputExtension = imagePath[imagePath.rfind('.')+1:]
        outputFormat = imageNode.get('{%s}format'%namespaces['style'])
        if outputFormat is not None:
            outputExtension = {
                'image/png': 'png',
            }[outputFormat]
        else:
            outputExtension = inputExtension
        outputPath = os.path.join(cachePath, 'images', infoHash  + '.' + outputExtension)
        create_directory_for(outputPath)
        infoDict['output_path'] = outputPath

        relativeWidth = imageNode.attrib.get('{%s}width'%namespaces['style'])
        if relativeWidth is not None:
            relativeWidth = float(relativeWidth)
            if relativeWidth > 1:
                print 'ERROR: specified width is greater than 1.', imagePath
                relativeWidth = 1
            requiredImageWidth = int(round(pageWidth*relativeWidth))
            subprocess.Popen(['convert', imagePath, '-geometry', '%ix'%requiredImageWidth, outputPath]).wait()
        elif outputExtension != inputExtension:
            subprocess.Popen(['convert', imagePath, outputPath]).wait()
        else:
            subprocess.Popen(['cp', imagePath, outputPath]).wait()
        with open(infoPath, 'wt') as fp:
            fp.write(repr(infoDict))

    # Find all pspictures and tikzpictures, determine what width should be, determi...
    for figureType in ['ps', 'tikz']:
        for figureNode in dom.xpath('//' + figureType + 'picture'):

            # Check if this image needs to be recached
            infoHash, infoPath, state = check_info_hash(figureNode)
            if state == 'unchanged':
                continue

            infoDict = {}

            codeNode = figureNode.find('code')
            if (codeNode is None) or (codeNode.text is None):
                print 'ERROR: ' + figureType + 'picture without code'
                print etree.tostring(figureNode)
                continue
            code = codeNode.text
            codeHash = hashlib.md5(''.join(code.split())).hexdigest()

            print {'new': 'Creating', 'changed': 'Updating'}[state], figureType + 'picture', codeHash

            outputPath = os.path.join(cachePath, figureType + 'pictures', codeHash  + '.png')
            create_directory_for(outputPath)
            infoDict['output_path'] = outputPath

            # Find included files
            infoDict['dependencies'] = []
            code = figureNode.find('code').text
            includedFiles = {}
            for includeCommand in [r'\includegraphics', r'\input']:
                pos = 0
                while True:
                    pos = code.find(includeCommand, pos)
                    if pos == -1:
                        break
                    pos += len(includeCommand)
                    if 'a' <= code[pos].lower() <= 'z':
                        continue
                    pos = code.find('{', pos)
                    assert pos != -1
                    pos += 1
                    path = code[pos:code.find('}', pos)].strip()
                    if path in includedFiles:
                        continue

                    fp = open(path, 'rb')
                    infoDict['dependencies'].append((path, hashlib.md5(fp.read()).hexdigest()))
                    fp.seek(0)
                    includedFiles[path] = fp
            transformFunction = {'ps': pspicture2png, 'tikz': tikzpicture2png}[figureType]
            pngPath = transformFunction(figureNode, iPageWidthPx=pageWidth, iIncludedFiles=includedFiles)
            shutil.move(pngPath, outputPath)

            with open(infoPath, 'wt') as fp:
                fp.write(repr(infoDict))
