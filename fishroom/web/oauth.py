import functools
import urllib.parse as urllib_parse
import tornado.auth
import tornado.escape
from ..config import config


class GitHubOAuth2Mixin(tornado.auth.OAuth2Mixin):
    _OAUTH_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    _OAUTH_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'

    @tornado.auth._auth_return_future
    def get_authenticated_user(self, code, callback):
        http = self.get_auth_http_client()
        body = urllib_parse.urlencode({
            'code': code,
            'client_id': config['github']['client_id'],
            'client_secret': config['github']['client_secret'],
        })

        http.fetch(self._OAUTH_ACCESS_TOKEN_URL,
                   functools.partial(self._on_access_token, callback),
                   method="POST", headers={'Content-Type': 'application/x-www-form-urlencoded'},
                   body=body)


    @staticmethod
    def _on_access_token(future, response):
        if response.error:
            future.set_exception(tornado.auth.AuthError('GitHub auth error: %s' % str(response)))
            return

        args = tornado.escape.parse_qs_bytes(tornado.escape.native_str(response.body))
        future.set_result(bool(args.get('access_token')))
