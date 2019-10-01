#!/bin/env python3
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

import requests
import sys
import q
# TODO:
# - spot slow task in the log


def should_be_restarted(s, run):
    if run['totalTests'] == 0:
        print('Nothing has been run!')
        return (True, False)

    response = s.get('https://api.shippable.com/jobs?runIds={id}&status=failed,timeout,unstable'.format(**run))
    for job in response.json():
        testReports = s.get('https://api.shippable.com/jobs/{id}/jobTestReports'.format(**job)).json()
        # We only focus on the first error, the others are likely to be consequence of the first one
        raw_contents = None
        for i in testReports:
            if isinstance(i, dict) and i['path'] == '/testresults.json':
                raw_contents = i['contents']
                break

        if raw_contents is None:
            q('Cannot parse testReports')
            q(testReports)
            continue

        if raw_contents.startswith('{'):
            contents = json.loads(raw_contents)
            details = contents.get('errorDetails') or contents.get('failureDetails')
            if not details:
                continue
            test_failure = lib.TestFailure(
                run=run,
                job=job,
                #test=contents['failureDetails'][0])
                test=details[0])
            print('env: %s' % test_failure.env())
            print('full: %s' % test_failure.test['full'])
            print('role_name: %s' % test_failure.role_name())
            is_temp = lib.is_temporary(test_failure)
            if is_temp is not None:
                return (is_temp, True)


    no_restart_patterns = [
            'fix conflicts and then commit the result.',
            ]

    needs_full_restart_patterns = [
            'Try re-running the entire matrix.',
            ]

    needs_restart_patterns = [
            'If the deploy key is not present in the repository, you can use the "Reset Project" button on the project settings page to restore it.',
            'OutOfMemoryException',
            'ERROR: 500: error: instance token not unique',
            'Failed to create vault token for this job.',
            'ERROR: Tests aborted after exceeding the',
            'ERROR: Failed transfer: ',
            ]
    for job in response.json():
        content = s.get('https://api.shippable.com/jobs/{id}/consoles?download=true'.format(**job)).content.decode()

        for i in no_restart_patterns:
            if i in content:
                print('Pattern found: ' + i)
                return (False, True)

        for i in needs_full_restart_patterns:
            if i in content:
                print('Pattern found: ' + i)
                return (True, False)

        for i in needs_restart_patterns:
            if i in content:
                print('Pattern found: ' + i)
                return (True, True)
    return (False, None)


def retry_run(s, run_id, rerun_failed_only=True):
    project_id = lib.get_project_by_name(s, 'ansible/ansible')['id']
    run = s.post('https://api.shippable.com/projects/%s/newBuild' % (project_id), json={'isDebug': False, 'projectId': '573f79d02a8192902e20e34b', 'rerunFailedOnly': rerun_failed_only, 'runId': run_id})
    r.raise_for_status()

def add_ci_verified_label(s, gh_issue):
    r = s.post('https://api.github.com/repos/ansible/ansible/issues/%d/labels' % gh_issue, json={'labels': ['ci_verified']}, headers={'Accept': 'application/vnd.github.symmetra-preview+json', 'Authorization': 'token %s' % os.environ['GITHUB_TOKEN']})
    r.raise_for_status()

def ask_user(message, options):
    user_input = ''
    while user_input not in options:
        user_input = input('message: %s' % options).rstrip()
    return user_input

def create_github_session():
    s = requests.Session()
    s.headers.update({'Authorization': 'token %s' % os.environ['GITHUB_TOKEN']})
    return s

shippable_session = lib.create_session()
github_session = lib.create_session()
r = github_session.get('https://api.github.com/search/issues?q=repo:ansible/ansible is:pr is:open -label:needs_rebase -label:ci_verified -label:wip -label:needs_ci_update+status:failure')
failed_prs = r.json()['items']

for pr in failed_prs:
    pr = github_session.get(pr['pull_request']['url']).json()

    statuses_url = pr['statuses_url']
    statuses = github_session.get(statuses_url).json()
    shippable_statuses = [s for s in statuses if s['context'] == 'Shippable']
    current_shippable_status = shippable_statuses[0]
    if current_shippable_status['state'] != 'failure':
        continue

    sha = pr['head']['sha']
    runs = shippable_session.get('https://api.shippable.com/runs?commitShas={sha}'.format(sha=sha)).json()
    run = runs[0]
    q(run)
    if not run['endedAt']:
        # run ongoing
        continue
    run_web_url = 'https://app.shippable.com/github/ansible/ansible/runs/{runNumber}/summary/console'.format(**run)
    duration = int((dateutil.parser.parse(run['endedAt']) - dateutil.parser.parse(run['startedAt'])).total_seconds())


    print('#######################')
    print('#######################')
    print('#######################')
    print('#######################')
    print(pr['body'])

    print('duration: %d' % int((dateutil.parser.parse(run['endedAt']) - dateutil.parser.parse(run['startedAt'])).total_seconds()))
    need_restart, rerun_failed_only = should_be_restarted(shippable_session, run)
    if need_restart:
        if run['propertyBag']['rerunFailedOnly']:
            print('Already a reRun! No auto-fire...')
        else:
            print(run_web_url)
            print(run['commitUrl'])
            print('temporary_error, retrying, rerun_failed_only=%s' % rerun_failed_only)
            retry_run(shippable_session, run['id'], rerun_failed_only=rerun_failed_only)
            continue
    else:
        print('Looks like a legit error')
    print(run_web_url)
    print(run['commitUrl'])
    user_input = ''
    user_input = ask_user('should I apply the ci_verified label/retry to job/skip', ['label', 'retry', 'retry_full', 'skip'])
    print('user_input: "%s"' % user_input)
    if user_input == 'label':
        add_ci_verified_label(github_session, run['pullRequestNumber'])
    elif user_input == 'retry':
        retry_run(github_session, run['id'])
    elif user_input == 'retry_full':
        retry_run(github_session, run['id'], rerun_failed_only=False)
    elif user_input == 'skip':
        continue

