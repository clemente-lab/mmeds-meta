from cherrypy.lib.auth_digest import get_ha1_dict_plain
from mmeds.authentication import USERS

CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'log.error_file': 'site.log',
        'tools.sessions.on': True
    },
    '/favicon.ico': {
        'tools.staticfile.filename': '/home/david/Work/mmeds-meta/server/favicon.ico',
        'tools.staticfile.on': True
    },
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.get_ha1': get_ha1_dict_plain(USERS),
        'tools.auth_digest.realm': 'localhost',
        'tools.auth_digest.key': 'a565c2714791cfb',
    }
}
