import requests
import q
import lib
import dateutil.parser
import functools
import datetime

def get_last_successful_runs(s, project_id):

    created_after = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
    q(created_after)
    response = s.get('https://api.shippable.com/runs?createdAfter={created_after}&projectIds={project_id}&branch=devel&isPullRequest=false'.format(created_after=created_after, project_id=project_id))
    q(response.content)
    return response.json()

s = lib.create_session()
project_id = lib.get_project_by_name(s, 'ansible/ansible')['id']


results = {}
for run in get_last_successful_runs(s, project_id=project_id):
    for job in s.get('https://api.shippable.com/jobs?runIds={id}&status=success'.format(**run)).json():
        q(job)
        if job['testsPassed'] == 0:
            continue
        if job['testsPassed'] < 50 or job['statusCode'] != 30:
            continue
        env = job['env'][0]
        duration = dateutil.parser.parse(job['endedAt']) - dateutil.parser.parse(job['startedAt'])
        if duration > datetime.timedelta(minutes=5):
            if env not in results:
                results[env] = []

            results[env].append(duration)

def sum(seq):
     def add(x,y): return x+y
     return functools.reduce(add, seq, datetime.timedelta(0))

def to_minutes(td):
    q(td)
    q(td.total_seconds())
    return int(td.total_seconds() / 60)


for env in sorted(results.keys()):
    values = results[env]
    q(values)
    average = sum(values)/len(values)
    q(average)
    print('env={env} average={average} max={max}'.format(
        env=env,
        average=to_minutes(average),
        max=to_minutes(max(values))))
    q(average)
q(results)
