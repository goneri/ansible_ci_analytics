import shutil
import os
import re
import json
import requests
from pprint import pprint
import q

import subprocess
import dateutil

def look_up_failure(job, test):
    if 'testhost: mongodb_replicaset : Wait for mongod to start responding port=' in test['testName']:
        return 'https://github.com/ansible/ansible/issues/61938'
    elif 'Mirror sync in progress?' in test['full']:
        return 'Temporary error'
    elif job['env'][0].startswith('windows/2016') and 'System.OutOfMemoryException' in test['full']:
        return 'https://github.com/ansible/ansible/issues/62365'
    return ''

def get_project_by_name(name):
    response = requests.get('https://api.shippable.com/projects?projectFullNames=' + name, headers=headers)
    projects = response.json()
    return projects[0]


def get_runs(project_id=None, branch='devel', limit=15, pull_request=False):
    print('https://api.shippable.com/runs?limit={limit}&projectIds={project_id}&branch={branch}&status=failed&isPullRequest={pull_request}'.format(project_id=project_id, branch=branch, limit=limit, pull_request=pull_request))
    response = requests.get('https://api.shippable.com/runs?limit={limit}&projectIds={project_id}&branch={branch}&status=failed&isPullRequest={pull_request}'.format(project_id=project_id, branch=branch, limit=limit, pull_request=pull_request), headers=headers)

    q(response.content)
    json_content = []
    for i in response.json():
        # Ignore the runs that fail emmediately
        if i['totalTests'] == 0:
            continue
        json_content.append(i)
    return json_content


def get_api_key():
    """
    rtype: str
    """
    key = os.environ.get('SHIPPABLE_KEY', None)
    if key:
        return key

    path = os.path.join(os.environ['HOME'], '.shippable.key')
    try:
        with open(path, 'r') as key_fd:
            return key_fd.read().strip()
    except IOError:
        return None


def save_run(run, file_name):
    fd = open(file_name + '.txt', 'w')

    fd.write('💣 https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/summary/console\n'.format(**run))
    fd.write('Branch: {branchName}\n'.format(**run))
    if run['pullRequestNumber']:
        fd.write('PR https://github.com/ansible/ansible/pull/{pullRequestNumber}\n'.format(**run))
    response = requests.get('https://api.shippable.com/jobs?runIds={id}&status=failed,timeout,unstable'.format(**run), headers=headers)
    for job in response.json():
        test_output = '  🎀 {env}: https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/{jobNumber}/tests\n'.format(**job)
        response = requests.get('https://api.shippable.com/jobs/{id}/jobTestReports'.format(**job), headers=headers)
        module_name = None
        for report in response.json():
            raw_contents = report['contents']
            if raw_contents.startswith('{'):
                contents = json.loads(report['contents'])
                if 'failureDetails' in contents:
                    for test in contents['failureDetails']:
                        q(test)
                        test_output += '    👿 "{testName}"\n'.format(**test)
                        if 'ÅÑŚÌβŁÈ' in test['className']:
                            relative_file_path, line_num = test['className'].split('ÅÑŚÌβŁÈ')[1].split(':')
                            module_name = relative_file_path.split('/')[-3]
                            q(module_name)
                            gh_file_path = run['projectHtmlUrl'] + '/blob/' +run['commitSha'] + relative_file_path + '#L' + line_num
                            test_output += '    📁 {gh_file_path}\n'.format(gh_file_path=gh_file_path, **test)
                        known_as = look_up_failure(job, test)
                        if known_as:
                            test_output += '  📖 See: {known_as}\n'.format(known_as=known_as)
                        else:
                            test_output += '┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓'
                            test_output += test['full']
                            test_output += '┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛'
                        test_output += '\n\n'
                        break  # We only focus on the first error, the others are likely to be consequence of the first one

        fd.write(test_output)
        if module_name:
            module_fd = open(file_name + '/' + module_name + '.txt', 'a+')
            module_fd.write(test_output)



headers = {'Authorization': 'apiToken %s' % get_api_key()}


project_id = get_project_by_name('ansible/ansible')['id']
cases = [
        {
            'branch': 'devel', 
            'pull_request': False},
        {
            'branch': 'devel', 
            'pull_request': True},
        {
            'branch': 'stable-2.9', 
            'pull_request': True},

        {
            'branch': 'stable-2.9', 
            'pull_request': True},
        ]

base_dir = '/tmp/ansible_ci'
shutil.rmtree(base_dir)
for case in cases:
    file_name = '{base_dir}/{branch}'.format(base_dir=base_dir, **case)
    if case['pull_request']:
        file_name += 'with_pr_request'
    os.makedirs(file_name, exist_ok=True)
    for run in get_runs(project_id=project_id, **case):
        save_run(run, file_name)
subprocess.call(['scp', '-r', file_name, 'file.rdu.redhat.com:~/public_html/ansible_ci/'])
