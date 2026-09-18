import json
import sys
print(json.dumps([n * 2 for n in json.load(sys.stdin)]))
