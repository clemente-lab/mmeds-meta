CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'log.error_file': 'site.log',
        'server.socket_port': 443,
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': '../server/data/cert.pem',
        'server.ssl_private_key': '../server/data/privkey.pem',
        'tools.secureheaders.on': True,
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
        'tools.sessions.httponly': True,
        'request.scheme': 'https'
    },
    '/favicon.ico': {
        'tools.staticfile.filename': '/home/david/Work/mmeds-meta/server/favicon.ico',
        'tools.staticfile.on': True,
    },
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': 'localhost',
        'tools.auth_digest.key': 'a565c2714791cfb',
    }
}
