"""Responsible for rendering markdown content to HTML."""

from typing import Callable, Optional, Mapping, Union, Tuple
import re
import xml.etree.ElementTree as ET
from markdown import markdown, Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from mdx_partial_gfm import PartialGithubFlavoredMarkdownExtension

from arxiv.base import logging

from .domain import SourcePage

logger = logging.getLogger(__name__)

ALLOWED_JINJA = r"\$jinja\s*{{ '([{}%]+)' }}([^{]+){{ '([{}%]+)' }}\s*jinja\$"


def render(content: str, dereferencer: Optional[Callable] = None) -> str:
    """
    Render markdown content to HTML.

    Parameters
    ----------
    content : str
        Markdown content.
    dereferencer : function
        Used for generating URLs from internal paths and slugs. Should accept
        a HREF value (str), and return a URL (str). Optional.
    static_dereferencer : function
        Used for generating URLs for static files. Should accept
        a src value (str), and return a URL (str). Optional.

    Returns
    -------
    str
        Rendered HTML.

    """
    extensions = ['tables', 'fenced_code', 'codehilite', 'toc', 'attr_list',
                  PartialGithubFlavoredMarkdownExtension()]
    if dereferencer is not None:
        extensions.append(ReferenceExtension('a', 'href', dereferencer))
        extensions.append(ReferenceExtension('img', 'src', dereferencer))
    return escape_braces(markdown(content, extensions=extensions))


def escape_braces(content: str) -> str:
    """
    Curly braces in content must be escaped.

    Otherwise, they are treated as Jinja2 syntax.
    """
    def repl(match):
        print(match.groups())
        return "foo"
    return re.sub(ALLOWED_JINJA, r"\1\2\3",
                  re.sub(r"([{}%]+)", r"{{ '\g<1>' }}", content))


class ReferenceProcessor(Treeprocessor):
    """Convert internal links to full paths."""

    def __init__(self, tag: str, attr: str,
                 dereferencer: Optional[Callable] = None) -> None:
        """Set the link dereferencer for use during processing."""
        self.dereferencer = dereferencer
        self.tag = tag
        self.attr = attr

    def run(self, root: ET.ElementTree) -> None:
        """Perform link conversion on ``root``."""
        if self.dereferencer is not None:
            self.translate_anchors(root)

    def translate_anchors(self, element: ET.Element) -> None:
        """Traverse ``element`` looking for and updating anchor elements."""
        for child in element:
            if child.tag == self.tag:
                value = child.attrib.get(self.attr)
                try:
                    child.attrib[self.attr] = self.dereferencer(value)
                except KeyError:
                    continue
            self.translate_anchors(child)


class ReferenceExtension(Extension):
    """Adds :class:`.ReferenceProcessor` to the markdown processor."""

    def __init__(self, tag: str, attr: str, dereferencer: Optional[Callable]) \
            -> None:
        """Set the link dereferencer for use during processing."""
        self.tag = tag
        self.attr = attr
        self.dereferencer = dereferencer

    def extendMarkdown(self, md: Markdown, md_globals: Mapping) -> None:
        """Add :class:`.ReferenceProcessor` to the markdown processor."""
        inst = ReferenceProcessor(self.tag, self.attr, self.dereferencer)
        md.treeprocessors[f'{self.tag}_{self.attr}_reference_processor'] = inst


def get_linker(page: SourcePage, site_name: str) -> Callable:
    def linker(href: str) -> Tuple[str, str, str, Optional[str]]:
        if not href or '://' in href or href.startswith('/') \
                or href.startswith('#'):
            return href, None, None, None
        anchor = None
        if '#' in href:
            href, anchor = href.split('#', 1)
        if href.endswith('.md'):
            path = href[:-3]
            route = f'{site_name}.from_sitemap'
            kwarg = 'page_path'
        elif '.' not in href.split('/')[-1]:
            path = href
            route = f'{site_name}.from_sitemap'
            kwarg = 'page_path'
        else:
            path = href
            route = f'{site_name}.static'
            kwarg = 'filename'
        base_path = '/'.join(page.page_path.split('/')[:-1])
        target_path = '/'.join([base_path, path.rstrip('/')]).lstrip('/')
        return route, kwarg, target_path, anchor
    return linker


def get_deferencer(page: SourcePage, site_name: str) -> Callable:
    def link_dereferencer(href: str) -> str:
        route, kwarg, target_path, anchor = get_linker(page, site_name)(href)
        if kwarg is None:
            return route
        if anchor is not None:
            return "$jinja {{ url_for('%s', %s='%s', _anchor='%s') }} jinja$" \
                % (route, kwarg, target_path, anchor)
        return "$jinja {{ url_for('%s', %s='%s') }} jinja$" \
            % (route, kwarg, target_path)
    return link_dereferencer
