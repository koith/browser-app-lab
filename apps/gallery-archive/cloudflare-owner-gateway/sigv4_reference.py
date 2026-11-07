"""Independent official-SDK reference for deterministic NONSECRET test inputs."""
import datetime
import json
import sys
import botocore.auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

data=json.load(sys.stdin)
instant=datetime.datetime.strptime(data['date'],'%Y%m%dT%H%M%SZ').replace(tzinfo=datetime.timezone.utc)
botocore.auth.get_current_datetime=lambda:instant
request=AWSRequest(method='GET',url=data['url'])
botocore.auth.S3SigV4Auth(Credentials(data['key'],data['secret']),'s3',data['region']).add_auth(request)
print(json.dumps(dict(request.headers)))
