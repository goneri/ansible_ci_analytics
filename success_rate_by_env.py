import requests
import os
import lib
import dateutil.parser
import functools
import datetime

def get_last_runs(s, project_id, branch):

    created_after = (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat()
    response = s.get('https://api.shippable.com/runs?createdAfter={created_after}&projectIds={project_id}&branch={branch}&isPullRequest=false'.format(created_after=created_after, project_id=project_id, branch=branch))
    return response.json()

s = lib.create_session()
project_id = lib.get_project_by_name(s, 'ansible/ansible')['id']


def get_success_rates(branch):
    results = {}
    for run in get_last_runs(s, project_id, branch):
        for job in s.get('https://api.shippable.com/jobs?runIds={id}'.format(**run)).json():
            if job['testsPassed'] == 0:
                continue
            env = job['env'][0]
            if env not in results:
                results[env] = []
            results[env].append(job['statusCode'])
    success_rates = {}
    for env in results:
        r = results[env]
        success_rates[env] = int(len([i for i in r if i == 30]) / len(r) * 100)
    return success_rates

fd = open('/var/www/html/ansible_ci/.succes_rate_by_env.html', 'w')
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
<h1>success rate per env during the last 24h</h1>
""")

for branch in ['devel', 'stable-2.8', 'stable-2.9']:
    fd.write("""
<table class="table table-bordered table-dark">
  <thead>
    <tr>
      <th scope="col">Env</th>
      <th scope="col">success rate (%)</th>
    </tr>
  </thead>
    <tbody>
""")
    success_rates = get_success_rates(branch)
    fd.write('<h2>{branch}</h2>'.format(branch=branch))
    for env, success_rate in sorted(success_rates.items(), key=lambda item: item[1]):
        if success_rate < 20:
            _class = 'bg-danger'
        elif success_rate < 40:
            _class = 'bg-warning'
        elif success_rate < 100:
            _class = 'bg-info'
        else:
            continue

        fd.write('<tr class="{_class}"><th>{env}</th><th>{success_rate}</th></tr>'.format(env=env, success_rate=success_rate, _class=_class))
    fd.write('</tbody></table>')

os.rename('/var/www/html/ansible_ci/.succes_rate_by_env.html', '/var/www/html/ansible_ci/succes_rate_by_env.html')
