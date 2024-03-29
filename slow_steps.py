#!/bin/env python3

from pprint import pprint
import re
import argparse

parser = argparse.ArgumentParser(description='Read a Shippable log and find the slow tasks.')
parser.add_argument('log_file', type=argparse.FileType('r'), help='a Shippable log file')
parser.add_argument('--min-duration', type=int, default=3,
        help='Only show up the tasks that last more (default: 3)')
args = parser.parse_args()

results = []
re_start = r'^(?P<minutes>\d\d):(?P<secondes>\d\d) TASK \[(?P<task>.*)\]'
re_end = r'^(?P<minutes>\d\d):(?P<secondes>\d\d)\s+$'
start_m = None
end_m = None
for l in args.log_file.readlines():
    m = re.search(re_start, l)
    if m:
        start_m = m
    m = re.search(re_end, l)
    if m:
        end_m = m
    if m and end_m and start_m:
        start_at = int(start_m.group('minutes')) * 60 + int(start_m.group('secondes'))
        task = start_m.group('task')
        end_at = int(end_m.group('minutes')) * 60 + int(end_m.group('secondes'))
        duration = end_at - start_at
        results.append((start_m.group(0), duration))
        end_m = None
        start_m = None

results.sort(key=lambda i: i[1] * -1)
print('Slowest tasks')
for task in results:
    if args.min_duration > task[1]:
        continue
    print('  - %s (%ds)' % task)
