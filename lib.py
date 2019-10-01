import os
import requests
import json
import re
import dateutil.parser
import datetime

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

class TestFailure:

    def __init__(self, run, job, test):
        self.run = run
        self.job = job
        self.test = test

    def playbook_path(self):
        if 'ÅÑŚÌβŁÈ' in self.test['className']:
            return self.test['className'].split('ÅÑŚÌβŁÈ')[1].split(':')[0]

    def playbook_line(self):
        if 'ÅÑŚÌβŁÈ' in self.test['className']:
            return self.test['className'].split('ÅÑŚÌβŁÈ')[1].split(':')[1]

    def role_name(self):
        if self.playbook_path() and self.playbook_path().startswith('/test/integration/targets'):
            return self.playbook_path().split('/')[4]
        elif self.test['testName'] == 'timeout':
            return '⏰timeout'
        elif self.test['suiteName'] == 'pytest':
            return 'pytest'

        m = re.match(r'\[[\w-]+\]\s\w+:\s([_\w]+).*', self.test['testName'])
        if m:
            return m.group(1)
        print('Cannot find the role for: testName=%s path=%s suiteName=%s' % (self.test['testName'], self.playbook_path(), self.test['suiteName']))

    def gh_playbook_url(self):
        if self.playbook_path():
            return self.run['projectHtmlUrl'] + '/blob/' + self.run['commitSha'] + self.playbook_path() + '#L' + self.playbook_line()

    def env(self):
        return self.job['env'][0]

    def run_url(self):
        return 'https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/summary/console'.format(**self.run)

    def job_url(self):
        return 'https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/{jobNumber}/tests'.format(**self.job)

    def gh_pr_url(self):
        return 'https://github.com/ansible/ansible/pull/{pullRequestNumber}'.format(**self.run)

    def end_at(self):
        return dateutil.parser.parse(self.job['endedAt'])

    def age(self):
        return int((datetime.datetime.now(datetime.timezone.utc) - self.end_at()).total_seconds() / 3600)


    def save(self):
        file_path = '/tmp/ci_cache/{run_number}_{env}.json'.format(
            run_number=self.run['runNumber'],
            env=self.env().replace('/', '_')
        )

        with open(file_path, 'w') as fd:
            fd.write(json.dumps([self.run, self.job, self.test]))

    @classmethod
    def load(cls, file_path):
         with open(file_path, 'r') as fd:
             run, job, test = json.load(fd)
             return cls(run, job, test)

def is_temporary(test_failure):
    if test_failure.env().startswith('T=sanity/'):
        return False
    elif test_failure.env().startswith('T=units/'):
        return False
    elif test_failure.test['testName'] == 'pep8':
        return False
    elif test_failure.role_name() == '⏰timeout':
        return True
    elif 'Mirror sync in progress?' in test_failure.test['full']:
        return True
    elif 'Failed to download packages: Curl error' in test_failure.test['full']:
        return True
    elif test_failure.job['env'][0].startswith('T=linux/opensuse15') and 'Valid metadata not found at specified URL' in test_failure.test['full']:
        return True
    elif 'Failed to synchronize cache for repo' in test_failure.test['full']:
        return True
    elif 'Failed to download metadata for repo' in test_failure.test['full']:
        return True
    elif 'metadata not found' in test_failure.test['full']:
        return True
    elif 'Failure downloading http://archive.ubuntu.com' in test_failure.test['full']:
        return True
    elif 'Cannot retrieve metalink for repository' in test_failure.test['full']:
        return True
    elif 'One of the configured repositories failed' in test_failure.test['full']:
        return True
    elif 'Failed to download packages:'  in test_failure.test['full']:
        return True
    elif 'Unable to fetch the repository. If this is a' in test_failure.test['full']:
        return True
    elif test_failure.role_name() == 'hg' and 'abort: HTTP Error 500: Internal Server Error' in test_failure.test['full']:
        return True
    elif re.search(r'.*Error fetching key \w+ from keyserver: keyserver.ubuntu.com.*', test_failure.test['full'], re.MULTILINE):
        return True
    elif re.search(r'gpg: requesting key \w+ from hkp server keyserver.ubuntu.com\ngpg: no valid OpenPGP data found.', test_failure.test['full'], re.MULTILINE): 
        return True
    elif "Failure downloading https://s3.amazonaws.com/ansible-ci-files/test/integration/targets/setup_epel/epel-release-latest-7.noarch.rpm, HTTP Error 500: Internal Server Error" in test_failure.test['full']:
        return True
    elif "unable to access 'https://github.com/abadger/test_submodules_newer.git/': OpenSSL SSL_read: SSL_ERROR_SYSCALL, errno 54" in test_failure.test['full']:
        return True
    elif re.search(r'Failed to download packages: Status code: 503.*fedora', test_failure.test['full']):
        return True
    elif 'Failure downloading https://ansible-ci-files.s3.amazonaws.com/test/integration' in test_failure.test['full']:
        return True
    elif 'Failed to download packages: Curl error' in test_failure.test['full']:
        return True
    return None


