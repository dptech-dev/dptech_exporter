import yaml


class SnmpTemplate:
    def __init__(self, yml):
        self.name: str = yml.get('name')
        self.version: str = yml.get('version').strip() if 'version' in yml else 'v2c'
        self.community: str|None = yml.get('community').strip() if 'community' in yml else 'public_default'
        self.user: str|None = yml.get('user').strip() if 'user' in yml else ''
        self.auth_protocol: str|None = yml.get('auth_protocol').strip() if 'auth_protocol' in yml else 'none'
        self.auth_key: str|None = str(yml.get('auth_key')).strip() if 'auth_key' in yml else ''
        self.priv_protocol: str|None = yml.get('priv_protocol').strip() if 'priv_protocol' in yml else 'none'
        self.priv_key: str|None = str(yml.get('priv_key')).strip() if 'priv_key' in yml else ''
        self.timeout: int = int(yml.get('timeout')) if 'timeout' in yml else 3
        self.retry: int = int(yml.get('retry')) if 'retry' in yml else 1

        if not self.name:
            raise Exception('snmp template name not set!')

        if not self.version in ['v2c', 'v3']:
            raise Exception(f'snmp version is "{self.version}", only support: v2c, v3')
        if self.version == 'v2c':
            if self.community == '':
                raise Exception('community cannot be empty!')
            self.user = None
            self.auth_protocol = None
            self.auth_key = None
            self.priv_protocol = None
            self.priv_key = None
        else:
            self.community = None
            if self.user == '':
                raise Exception('user cannot be empty!')
            if self.auth_protocol not in ['none', 'md5', 'sha']:
                raise Exception(f'snmp v3 auth protocol is "{self.auth_protocol}", only support: none, md5, sha')
            if self.priv_protocol not in ['none', 'des', 'aes']:
                raise Exception(f'snmp v3 priv protocol is "{self.priv_protocol}", only support: none, des, aes')
            if self.auth_protocol == 'none':
                self.auth_protocol = None
                self.auth_key = None
                self.priv_protocol = None
                self.priv_key = None
            elif self.auth_key == '':
                raise Exception('snpm v3 auth key is need!')
            elif self.priv_protocol == 'none':
                self.priv_protocol = None
                self.priv_key = None
            elif self.priv_key == '':
                raise Exception('snpm v3 priv key is need!')

        if self.timeout <= 0:
            raise Exception(f'bad timeout value: {self.timeout}')
        if self.retry < 0:
            raise Exception(f'bad retry value: {self.retry}')


class Target:
    def __init__(self, yml):
        self.host: str = yml.get('host')
        self.sysname: str|None = yml.get('sysname').strip() if 'sysname' in yml else None
        self.snmp: str|SnmpTemplate = yml.get('snmp').strip() if 'snmp' in yml else 'default'

        if not self.host:
            raise Exception('target host not set!')
        if self.sysname == '':
            raise Exception('target sysname cannot be empty!')
        if self.snmp == '':
            raise Exception('target snmp template cannot be empty!')

_snmp_templtes: list[SnmpTemplate] = []
_targets: list[Target] = []


def config_init(file):
    try:
        with open(file, 'r') as f:
            cfg = yaml.safe_load(f)
            sts = cfg.get('snmp_templates')
            if sts:
                global _snmp_templtes
                _snmp_templtes = [SnmpTemplate(t) for t in sts]
            tgs = cfg.get('targets')
            if tgs:
                global _targets
                _targets = [Target(t) for t in tgs]

                if len(_targets) == 0:
                    raise Exception('no target set!')
                for tg in _targets:
                    temp = next((t for t in _snmp_templtes if t.name == tg.snmp), None)
                    if not temp:
                        raise Exception(f'cannot find snmp template "{tg.snmp}"!')
                    tg.snmp = temp

    except Exception as e:
        raise Exception(f'parse "{file}" fail: {str(e)}')

def config_targets() -> list[Target]:
    return _targets