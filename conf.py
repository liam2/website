﻿# -*- coding: utf-8 -*-

import tinkerer
import tinkerer.paths

# **************************************************************
# Base settings
# **************************************************************

# Change this to the name of your blog
project = 'LIAM2'

# Change this to the tagline of your blog
tagline = 'Microsimulation made EASIER'

# Change this to the description of your blog
description = 'LIAM2'

# Change this to your name
author = u'Gaëtan de Menten'

# Change this to your copyright string
copyright = u'2011-2018'

# Change this to your blog root URL (required for RSS feed)
website = 'http://liam2.plan.be/'

# **************************************************************
# More tweaks you can do
# **************************************************************

# Add your Disqus shortname to enable comments powered by Disqus
disqus_shortname = None

# Change your favicon (new favicon goes in _static directory)
html_favicon = 'tinkerer.ico'

# Pick another Tinkerer theme or use your own
html_theme = "modern5"

# Theme-specific options, see docs
html_theme_options = dict(
    color="#074e78",             # header color (under the image)
    color_light="#204080",       # navbar text
    nav_hover_color="#ffffff",   # navbar text when hovered (#f8f8f8)
    color_dark="#123764",        # text shadow and "bars" borders

    background_color="#6a80a0",  # background for sides
    shadow_color="#103040",      # color of the shadow of the main column
    paper_color="#f8fafb",       # background for "main" part
    sidebar_color="#dcecfc",     # background for sidebar

    header_color="#d8e8ff",      # main title (#f8f8f8)
    tagline_color="#abc",        # (#93a4ad)

    text_color="#6070a0",        # post titles (#0c0501)
    meta_color="#8898a8",        # posts metadata (#93a4ad)

    link_color="#0b7dc0",

    navbar_color1="#e4f0fb",     # (#354550)
    navbar_color2="#d8e8f8",     # (#021520)
    navbar_color3="#d8e8f8",     # start of 2nd gradient for navbar
    navbar_color4="#a0c0e0",     # end of 2nd gradient for navbar
)

# Link to RSS service like FeedBurner if any, otherwise feed is linked directly
rss_service = None

# Generate full posts for RSS feed even when using "read more"
rss_generate_full_posts = False

# Number of blog posts per page
posts_per_page = 10

# Character use to replace non-alphanumeric characters in slug
slug_word_separator = '_'

# **************************************************************
# Edit lines below to further customize Sphinx build
# **************************************************************

# Add other Sphinx extensions here
extensions = ['tinkerer.ext.blog', 'tinkerer.ext.disqus',
              'sphinx.ext.intersphinx', 'sphinx.ext.extlinks']

# WARNING: braces need to be escaped (doubled) in the template!
# (None, 'objects.inv') means trying first to get objects.inv from the
# web then locally (requires Sphinx 1.3)
intersphinx_mapping = {'doc': ('http://liam2.plan.be/documentation/{version}',
                               (None, 'objects.inv'))}
extlinks = {
    'issue': ('https://github.com/liam2/liam2/issues/%s', 'issue '),
    'pr': ('https://github.com/liam2/liam2/pull/%s', 'pull request '),
    'changes': ('http://liam2.plan.be/documentation/{version}/changes.html#%s',
                None),
}

# Add other template paths here
templates_path = ['_templates']

# Add other static paths here
html_static_path = ['_static', tinkerer.paths.static]

# Add other theme paths here
html_theme_path = ['_themes', tinkerer.paths.themes]

# Add file patterns to exclude from build
exclude_patterns = ["drafts/*", "_templates/*"]

# Add templates to be rendered in sidebar here
# WARNING: braces need to be escaped !
html_sidebars = {
    "**": ["recent.html", "searchbox.html"]
}

# **************************************************************
# Do not modify below lines as the values are required by
# Tinkerer to play nice with Sphinx
# **************************************************************

source_suffix = tinkerer.source_suffix
master_doc = tinkerer.master_doc
version = tinkerer.__version__
release = tinkerer.__version__
html_title = project
html_use_index = False
html_show_sourcelink = False
html_add_permalinks = None
