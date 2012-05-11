#!/usr/bin/env python

import zipfile
import os
import shutil
import json
from lxml import etree

cnxml2html = "/home/ewald/programming/emas.buildout/src/emas.theme/emas/theme/transforms/cnxmlplus2html.py"

# create booki.zip
zf = zipfile.ZipFile('booki.zip', mode='w')


if __name__ == "__main__":
    # assuming cache_plone_images.py is one level up
    # we first run the script that creates pngs from any tikz and pstricks code
    command = "python %s/cache_plone_images.py *.cnxmlplus"% os.path.realpath(__file__).rpartition('/')[0]
    os.system(command)

    # cnxmlplus -> html 
    cnxmlplusfiles = [f for f in os.listdir(os.curdir) if '.cnxmlplus' in f]
    cnxmlplusfiles.sort()

    # make a folder called booki_temp
    os.mkdir('booki_temp')
    cwd = os.getcwd()
    os.chdir('booki_temp')

    # add the required mimetype file into the folder
    mime = open('mimetype', 'w')
    mime.write('application/x-booki+zip')
    mime.close()

    zf.write('mimetype')
    
    #create the static folder
    os.mkdir('static')
    zf.write('static')
    os.chdir(cwd)

    # build the info.json object and convert the cnxml files to html
    infojson = {}
    infojson['version'] = 1
    infojson['manifest'] = {}
    infojson['spine'] = []
    infojson['TOC'] = []
    infojson['metadata'] = {}


    #copy all die images contained in _plone_ignore_ to static
    for directory, dirnames, filenames in os.walk(os.path.join('_plone_ignore_', 'cache')):
        if 'info' not in directory:
            for f in filenames:
                shutil.copy2(os.path.join(directory, f), os.path.join(cwd, 'booki_temp', 'static'))
                # add the image to the manifest
                infojson['manifest'][f] = {
                    'url': os.path.join('static',f),
                    'mimetype': 'image/%s'%f.partition('.')[2],
                    'contributors': ["Siyavula"],
                    'rightsholders': ["Siyavula"],
                    'license': ['CC-BY']}


    
    infojsonfile = open(os.path.join('booki_temp', 'info.json'), 'w')

    for cnxml in cnxmlplusfiles:
        command = "python %s %s" %(cnxml2html, cnxml)
        os.system(command)

        # We now have a file called 'output.html' in the current folder. Rename to the same name as the original filename
        name, extension = os.path.splitext(cnxml)

        # add the chapter to the manifest in info.json
        infojson['manifest'][name] = {
                'url': name + '.html',
                'mimetype': 'text/html',
                'contributors': ["Siyavula"],
                'rightsholders': ["Siyavula"],
                'license': ['CC-BY']}

        # add file to spine object in info.json
        infojson['spine'].append(name)

        # add chapter to TOC
        title = name.replace('-', ' ')

        infojson['TOC'].append({'title':title,
            'url': name+'.html',
            'type': 'chapter',
            'role': 'text',
            'children': []})



        # 
        # Replace the <img> src attributes in the html with 'static/filename'
        #
        htmlfile = open('output.html', 'r').read()
        
        # read the cnxmlfile also, we need to add the chapter title to the html file.
        cnxmlfile = open(cnxml, 'r').read()
        xmlroot = etree.XML(cnxmlfile)
        chaptertitle = etree.fromstring('<h1 class="chapter-header">%s</h1>'%xmlroot.find('.//title').text)

        root = etree.HTML(htmlfile)
        first_div = root.find('.//div')
        first_div.insert(0, chaptertitle)
        first_div.attrib['id'] = 'content'

        images = root.findall('.//img')
        for im in images:
            src = im.attrib['src']
            try:
                # split the src string into folder, seperator, filename
                head, sep, tail = src.rpartition('/')
            except:
                print 'ERROR, Cannot split src attribute in html', src
            src = '/'.join(['static',tail])
            im.attrib['src'] = src

        #
        # Also find the div.example elements, they need new classes to indicate one of
        # ['General experiment', 'Formal experiment', 'Informal experiment', 'Activity', 'Investigation', 'Group discussion', 'Case study', 'Project']
        #
        
        cnxlabels = [('General experiment','g_experiment'), ('Formal experiment', 'f_experiment'), ('Informal experiment', 'i_experiment'), ('Activity', 'activity'), ('Investigation', 'investigation'), ('Group discussion', 'group_discussion'), ('Case study', 'casestudy'), ('Project', 'project')]

        examples = root.findall('.//div[@class="example"]/h5/span[@class="cnx_label"]')
        for ex in examples:
            label = ex.text
            # see if the label is one of the special ones
            if any([c[0] in label for c in cnxlabels]):
                # modify the class="example" to reflect the new type

                newclass = [c[1] for c in cnxlabels if c[0] in label][0]
                print newclass
                # get parent div element
                div_example = ex.find('....')
                div_example.attrib['class'] = newclass
                print "Found Example Environment. Changing example class to ", newclass 

 
        
        htmlfile = open('output.html', 'w')
        htmlfile.write(etree.tostring(root))
        htmlfile.close()



        shutil.move('output.html', 'booki_temp/%s.html'%name)
        os.chdir('booki_temp')
        zf.write('%s.html'%name)
        os.chdir(cwd)


        # clean up some other files
        os.remove('output.html.shortcodecnxml')
        os.remove('output.html.shortcodehtml')

    # get the title of the book from the directory's name
    title = os.getcwd().rpartition('/')[2]

    infojson['metadata'] = {'http://purl.org/dc/elements/1.1/':
            {
                'creator': {
                    '': ["Siyavula"]},
                'title': {
                    '': [title]},
                'language': {
                    '': ['en']},
                'identifier': {
                    'Siyavula-%s'%title: ['http://www.siyavula.com']}
             }
    }


    
    infojsonfile.write(json.dumps(infojson))
    infojsonfile.close()
    
    os.chdir('booki_temp')
    zf.write('info.json')
    zf.write('static')
    for f in os.listdir('static'):
        zf.write(os.path.join('static', f))
    zf.close()


