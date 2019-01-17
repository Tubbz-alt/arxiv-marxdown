"""Helper script for building a site; used in Docker build process."""

from arxiv.base.globals import get_application_config
from marxdown.factory import create_web_app
from marxdown.build import build_site

if __name__ == '__main__':
    app = create_web_app()
    with app.app_context():
        config = get_application_config()
        build_site(app.config.get('SITE_SEARCH_ENABLED', True))
