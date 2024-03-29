import shutil
import os
import re
import json
from pprint import pprint
import datetime
import lib
import glob
import dateutil.parser
import subprocess

# TODO:
# - spot slow task in the log

STATUS_FAILURE=80
STATUS_UNSTABLE=50
STATUS_SUCCESS=30

class Renderer:

    def __init__(self):
        self.test_failures = []
        self.base_dir = '/tmp/ansible_ci'
        os.makedirs(self.base_dir, exist_ok=True)

    def render_by_module(self):
        by_module = {}
        for test_failure in self.test_failures:
            role_name = test_failure.role_name()
            if role_name not in by_module:
                by_module[role_name] = []
            by_module[role_name].append(test_failure)

        fd = open(self.base_dir + '/by_module.html', 'w')
        fd.write("""
<!doctype html>
<html lang="en">
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/fork-awesome@1.1.7/css/fork-awesome.min.css" integrity="sha256-gsmEoJAws/Kd3CjuOQzLie5Q3yshhvmo7YNtBG7aaEY=" crossorigin="anonymous">
    <title>Ansible CI errors</title>
  </head>
  <body>

        <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js" integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo" crossorigin="anonymous"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js" integrity="sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1" crossorigin="anonymous"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js" integrity="sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM" crossorigin="anonymous"></script>

        <body>
        <html>
        <button class="btn btn-primary" type="button" data-toggle="collapse" data-target=".multi-collapse_temporary_True" aria-expanded="true">Hide temp errors</button>
        """)
        entry_counter=0
        multi_collapse_temp_errors = []
        for role_name in sorted(by_module.keys()):
            entry_counter += 1
            test_failures = by_module[role_name]
            fd.write('<div class="container">')
            for test_failure in test_failures:
                if hasattr(test_failure, 'seen'):
                    continue
                seen_counter = []
                branches = [test_failure.job['branchName']]
                status_codes = [test_failure.job['statusCode']]
                envs = [test_failure.job['env'][0]]
                age = test_failure.age()
                # Merge the similar failures
                for i in test_failures:
                    if i.test['testName'] == test_failure.test['testName']:
                        if not (test_failure.playbook_path() and (i.playbook_path() != test_failure.playbook_path())):
                            i.seen = True
                            if i.job['id'] != test_failure.job['id']:
                                branches.append(i.job['branchName'])
                                status_codes.append(i.job['statusCode'])
                                envs.append(i.job['env'][0])
                                seen_counter.append(i.job_url())
                                if i.age() < test_failure.age():
                                    age = i.age()

                # Note: a dup may have a different value in statusCode
                #temporary_error=(is_temporary(test_failure) or (STATUS_UNSTABLE in status_codes))
                temporary_error=lib.is_temporary(test_failure)
                fd.write("""
                <div class="border p-3 border bg-light collapse show multi-collapse_temporary_{temporary_error}">
                <h3>{role_name}</h3>
                👿 <a href="{job_url}">{testName}</a>
                <ul class="list-group list-group-flush">
                <li class="list-group-item">🌿impacted branches: {branches}</li>\n
                <li class="list-group-item">🧮envs: {envs}</li>\n
                <li class="list-group-item">🧮last occurence: {age} hour(s) ago</li>\n
                \n""".format(
                    entry_counter=entry_counter,
                    testName=test_failure.test['testName'],
                    job_url=test_failure.job_url(),
                    envs=', '.join(sorted(set(envs))),
                    branches=', '.join(sorted(set(branches))),
                    age=age,
                    role_name=role_name,
                    temporary_error=temporary_error,
                ))

                if temporary_error:
                    fd.write("""
                <li class="list-group-item"><i class="fa fa-step-forward" aria-hidden="true"></i>Temporary/Non-blocking error</li>\n
                    """)

                if test_failure.gh_playbook_url():
                    fd.write("""
                    <li class="list-group-item"><a href="{gh_playbook_url}">📁playbook task</a></li>\n""".format(
                        gh_playbook_url=test_failure.gh_playbook_url()))

                if seen_counter and age < 3:

                    fd.write("""<li class="list-group-item alert alert-danger" role="alert">⚠Already seen recently: """)
                    for i in seen_counter:
                        fd.write('<a href="' + i + '">🚨</a>')

                    fd.write("""</li>""")

                # if seen_counter and age > 3:

                #     fd.write("""<li class="list-group-item ">👌Problem seems to be resolved: """)
                #     for i in seen_counter:
                #         fd.write('<a href="' + i + '">🦞</a>')

                #     fd.write("""</li>""")


                if has_open_issue(test_failure):
                    fd.write('<li class="list-group-item"><i class="fa fa-github" aria-hidden="true"></i><a href="{open_issue}">Github link</a></li>'.format(open_issue=has_open_issue(test_failure)))
                else:
                    fd.write('<pre><code>{full}</code></pre>'.format(full=test_failure.test['full']))
                fd.write('</ul>')
                fd.write('</div>')
            fd.write('</div>')
        fd.write('</html></body>')
        fd.close()

    def upload(self):
        subprocess.call(['cp', '-r', self.base_dir + '/by_module.html', '/var/www/html/ansible_ci'])

def has_open_issue(test_failure):
    if 'testhost: mongodb_replicaset : Wait for mongod to start responding port=' in test_failure.test['testName']:
        return 'https://github.com/ansible/ansible/issues/61938'
    elif test_failure.job['env'][0].startswith('T=windows/2016') and 'System.OutOfMemoryException' in test_failure.test['full']:
        return 'https://github.com/ansible/ansible/issues/62365'
    elif 'hcloud' in test_failure.job['env'][0] and 'hcloud.hcloud.APIException: <exception str() failed>' in test_failure.test['full']:
        return 'https://github.com/ansible/ansible/issues/62560'
    elif re.match(r'.*hcloud_network.hcloud_network_info\[0\].routes.*', test_failure.test['testName']):
        return  'https://github.com/ansible/ansible/issues/62606'
    elif re.match(r'.*kubernetes-validate python library is required to validate resources.*', test_failure.test['testName']):
        return 'https://github.com/ansible/ansible/pull/62635'
    elif test_failure.role_name() == 'hcloud_volume_info' and '_raise_exception_from_json_content' in test_failure.test['full']:
        return 'https://github.com/ansible/ansible/issues/63019'

def get_runs(s, project_id=None, branch='devel', pull_request=False):
    created_after = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
    response = s.get('https://api.shippable.com/runs?createdAfter={created_after}&projectIds={project_id}&branch={branch}&isPullRequest={pull_request}'.format(project_id=project_id, branch=branch, created_after=created_after, pull_request=pull_request))

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
        if job['testsPassed'] == 0:
            continue
        r = s.get('https://api.shippable.com/jobs/{id}/jobTestReports'.format(**job))
        testReports = r.json()
        # We only focus on the first error, the others are likely to be consequence of the first one
        raw_contents = testReports[-1]['contents']
        if raw_contents.startswith('{'):
            contents = json.loads(testReports[-1]['contents'])
            details = contents.get('errorDetails') or contents.get('failureDetails')
            if not details:
                continue
            test_failure = lib.TestFailure(
                run=run,
                job=job,
                #test=contents['failureDetails'][0])
                test=details[0])
            test_failures.append(test_failure)
    return test_failures

import argparse
parser = argparse.ArgumentParser()
parser.add_argument(
    '--refresh-cache', action='store_true',
                    help='Refresh the cache first.')

args = parser.parse_args()
if args.refresh_cache:
    for i in glob.glob('/tmp/ci_cache/*.json'):
        os.unlink(i)
    s = lib.create_session()
    project_id = lib.get_project_by_name(s, 'ansible/ansible')['id']
    base_dir = '/tmp/ansible_ci'
    for run in get_runs(s, project_id=project_id, branch='devel,stable-2.9,stable-2.8,stable-2.7'):
        for test_failure in collect_test_failures(s, run):
            test_failure.save()



renderer = Renderer()
for i in glob.glob('/tmp/ci_cache/*.json'):
    test_failure = lib.TestFailure.load(i)
    renderer.test_failures.append(test_failure)

renderer.render_by_module()
renderer.upload()
