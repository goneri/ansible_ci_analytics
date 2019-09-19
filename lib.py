import os
import requests

def get_auth_header():
    """
    rtype: str
    """
    key = os.environ.get('SHIPPABLE_KEY', None)
    return {'Authorization': 'apiToken %s' % key}


def create_session():
    s = requests.Session()
    s.headers.update(get_auth_header())
    return s

def get_project_by_name(s, name):
    response = s.get('https://api.shippable.com/projects?projectFullNames=' + name)
    projects = response.json()
    return projects[0]

