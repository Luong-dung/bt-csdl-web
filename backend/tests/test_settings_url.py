"""W48-03 (review #122): DB_PASSWORD/DB_USER with URL-special characters must survive DATABASE_URL."""
import pytest
from sqlalchemy.engine import make_url

from config.settings import Settings


@pytest.mark.parametrize('password', ['plain', 'p@ss', 'a#b', '100%', 'x:y/z', 'q?r&s=t', 'sp ace', 'ổn@#%:/'])
def test_database_url_round_trips_special_characters(password):
    url = make_url(Settings(DB_PASSWORD=password, DB_USER='app:user', DB_NAME='db_test').DATABASE_URL)
    assert (url.password, url.username, url.database, url.host) == (password, 'app:user', 'db_test', '127.0.0.1')


def test_alembic_env_escapes_percent_for_configparser():
    """alembic/env.py passes the URL through ConfigParser, where a bare "%" raises ValueError."""
    from pathlib import Path

    from alembic.config import Config
    url = Settings(DB_PASSWORD='a#b%c@d').DATABASE_URL
    env = (Path(__file__).parents[1] / 'alembic' / 'env.py').read_text(encoding='utf-8')
    assert 'settings.DATABASE_URL.replace("%", "%%")' in env
    config = Config()
    config.set_main_option('sqlalchemy.url', url.replace('%', '%%'))
    assert config.get_main_option('sqlalchemy.url') == url
    assert make_url(config.get_main_option('sqlalchemy.url')).password == 'a#b%c@d'
