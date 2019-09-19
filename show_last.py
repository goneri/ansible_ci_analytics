import shutil
import os
import re
import json
from pprint import pprint
import q

import lib

import subprocess

# TODO:
# - spot slow task in the log

class TestFailure:

    def __init__(self, run, job, test):
        self.run = run
        self.job = job
        self.test = test
        self.gh_file_path = None

    def playbook_path(self):
        if 'ÅÑŚÌβŁÈ' in self.test['className']:
            return self.test['className'].split('ÅÑŚÌβŁÈ')[1].split(':')[0]

    def playbook_line(self):
        if 'ÅÑŚÌβŁÈ' in self.test['className']:
            return self.test['className'].split('ÅÑŚÌβŁÈ')[1].split(':')[1]

    def module_name(self):
        if self.playbook_path():
            return self.playbook_path().split('/')[-3]

    def gh_playbook_url(self):
        if self.playbook_path():
            return self.run['projectHtmlUrl'] + '/blob/' + self.run['commitSha'] + self.playbook_path() + '#L' + self.playbook_line()

    def run_url(self):
        return 'https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/summary/console'.format(**self.run)

    def job_url(self):
        return 'https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/{jobNumber}/tests'.format(**self.job)

    def gh_pr_url(self):
        return 'https://github.com/ansible/ansible/pull/{pullRequestNumber}'.format(**self.run)


class Renderer:

    def __init__(self):
        self.test_failures = []
        self.base_dir = '/tmp/ansible_ci'
        os.makedirs(self.base_dir, exist_ok=True)

    def render_branch(self, branch):
        for test_failure in self.test_failures:
            if test_failure.run['branchName'] == 'branch':
                print(test_failure.run_url())
                print(test_failure.run['pullRequestNumber'])

    def render_by_module(self):
        by_module = {}
        for test_failure in self.test_failures:
            module_name = test_failure.module_name()
            if module_name not in by_module:
                by_module[module_name] = []
            by_module[module_name].append(test_failure)

        fd = open(self.base_dir + '/by_module.html', 'w')
        for module_name, test_failures in by_module.items():
            fd.write('<h2>{module_name}</h2>'.format(module_name=module_name))
            for test_failure in test_failures:
                if hasattr(test_failure, 'seen'):
                    continue
                seen_counter = []
                for i in test_failures:
                    if i.gh_playbook_url() == test_failure.gh_playbook_url():
                        i.seen = True
                        if i.job['id'] != test_failure.job['id']:
                            seen_counter.append(i.job_url())
                fd.write("""
                <ul><li>👿 <a href="{job_url}">{testName}</a></li>\n
                <li>🌿branch: {branch}</li> <a href="{gh_playbook_url}">📁playbook task</a></li>\n
                <li>🧮env: {env}</li>\n
                \n""".format(
                    testName=test_failure.test['testName'],
                    job_url=test_failure.job_url(),
                    env=test_failure.job['env'][0],
                    branch=test_failure.job['branchName'],
                    gh_playbook_url=test_failure.gh_playbook_url(),
                ))

                if seen_counter:
                    fd.write('<li>Already seen recently: ')
                    for i in seen_counter:
                        fd.write('<a href="' + i + '">🚨</a>')
                    fd.write('</li>')

                known_as = look_up_failure(test_failure)
                if known_as:
                    fd.write('<strong>See: <a href="{known_as}"></a>{known_as}</strong>'.format(known_as=known_as))
                else:
                    fd.write('<code>{full}</code>'.format(full=test_failure.test['full']))
                fd.write('</ul>')
        fd.close()

    def upload(self):
        subprocess.call(['ssh', 'file.rdu.redhat.com', 'rm :~/public_html/ansible_ci/*'])
        subprocess.call(['scp', '-r', self.base_dir, 'file.rdu.redhat.com:~/public_html/ansible_ci/'])

def look_up_failure(test_failure):
    if 'testhost: mongodb_replicaset : Wait for mongod to start responding port=' in test_failure.test['testName']:
        return 'https://github.com/ansible/ansible/issues/61938'
    elif 'Mirror sync in progress?' in test_failure.test['full']:
        return 'Temporary error'
    elif test_failure.job['env'][0].startswith('windows/2016') and 'System.OutOfMemoryException' in test_failure.test['full']:
        return 'https://github.com/ansible/ansible/issues/62365'
    elif test_failure.job['env'][0].startswith('hcloud') and 'hcloud.hcloud.APIException: <exception str() failed>' in test_failure.test['full']:
        return 'https://github.com/ansible/ansible/issues/62560'
    return ''

def get_runs(s, project_id=None, branch='devel', limit=10, pull_request=False):
    response = s.get('https://api.shippable.com/runs?limit={limit}&projectIds={project_id}&branch={branch}&status=failed&isPullRequest={pull_request}'.format(project_id=project_id, branch=branch, limit=limit, pull_request=pull_request))

    q(response.content)
    json_content = []
    for i in response.json():
        # Ignore the runs that fail emmediately
        if i['totalTests'] == 0:
            continue
        json_content.append(i)
    return json_content


def collect_test_failures(s, run):
    response = s.get('https://api.shippable.com/jobs?runIds={id}&status=failed,timeout,unstable'.format(**run))
    test_failures = []
    for job in response.json():
        testReports = s.get('https://api.shippable.com/jobs/{id}/jobTestReports'.format(**job)).json()
        # We only focus on the first error, the others are likely to be consequence of the first one
        q(testReports)
        raw_contents = testReports[-1]['contents']
        q(raw_contents)
        if raw_contents.startswith('{'):
            contents = json.loads(testReports[-1]['contents'])
            q(contents)
            if 'failureDetails' in contents:
                details = contents['errorDetails'] or contents['failureDetails']
                if not details:
                    continue
                test_failure = TestFailure(
                    run=run,
                    job=job,
                    #test=contents['failureDetails'][0])
                    test=details[0])
                q(test_failure)
                test_failures.append(test_failure)
    q(test_failures)
    return test_failures

s = lib.create_session()
project_id = lib.get_project_by_name(s, 'ansible/ansible')['id']
cases = [
        {
            'branch': 'devel',
            'pull_request': False},
        {
            'branch': 'stable-2.9',
            'pull_request': False},
        {
            'branch': 'stable-2.8',
            'pull_request': False},

        ]

base_dir = '/tmp/ansible_ci'
renderer = Renderer()
for case in cases:
    for run in get_runs(s, project_id=project_id, **case):
        for test_failure in collect_test_failures(s, run):
            renderer.test_failures.append(test_failure)

print(renderer.test_failures)
#renderer.render_branch('devel')
renderer.render_by_module()
renderer.upload()
