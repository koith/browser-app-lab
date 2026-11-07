"""Read-only evidence of existing mirror configuration; never create or upload.

A valid config/bucket is NOT a restored gallery or a zero-charge guarantee.
Only secret names/booleans and already-public aggregate inventory leave here.
"""
import json
import os
from pathlib import Path
from private_mirror_free_policy import check_existing_owner_budget,validated_private_config,require_cloudflare_private_standard

REQUIRED={
 'GALLERY_MIRROR_PRIVATE_BUCKET':'OWNER_REPLICA_BUCKET',
 'GALLERY_MIRROR_PROVIDER':'OWNER_REPLICA_PROVIDER',
 'GALLERY_MIRROR_RCLONE_PROVIDER':'RCLONE_CONFIG_OWNERREPLICA_PROVIDER',
 'GALLERY_MIRROR_ACCESS_KEY_ID':'RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID',
 'GALLERY_MIRROR_SECRET_ACCESS_KEY':'RCLONE_CONFIG_OWNERREPLICA_SECRET_ACCESS_KEY',
 'GALLERY_MIRROR_S3_ENDPOINT':'RCLONE_CONFIG_OWNERREPLICA_ENDPOINT',
 'GALLERY_MIRROR_REGION':'RCLONE_CONFIG_OWNERREPLICA_REGION',
}

def inspect(root,environ=None,client_factory=None):
 e=dict(os.environ if environ is None else environ)
 result={'resource_creations':0,'uploaded_photos':0,'original_SHA_readbacks':0,
         'gallery_restored':False,'zero_charge_account_verified':False,
         'existing_private_bucket_readable':False,
         'inventory_budget':check_existing_owner_budget(root)}
 missing=[label for label,key in REQUIRED.items() if not e.get(key)]
 if e.get('OWNER_REPLICA_PROVIDER')=='cloudflare-r2':
  for label,key in [('GALLERY_MIRROR_CF_ACCOUNT_ID','OWNER_REPLICA_CF_ACCOUNT_ID'),
                    ('GALLERY_MIRROR_CF_AUDIT_TOKEN','OWNER_REPLICA_CF_AUDIT_TOKEN')]:
   if not e.get(key):missing.append(label)
 result['missing_secret_names']=missing
 if missing:
  result['state']='BLOCKED_EXISTING_INDEPENDENT_STORAGE_NOT_CONFIGURED'
  return result
 try:
  config=validated_private_config(e)
  if config['provider']=='cloudflare-r2':require_cloudflare_private_standard(config,e)
  if client_factory is None:
   import boto3
   client_factory=boto3.client
  client=client_factory('s3',endpoint_url=config['endpoint'],region_name=config['region'],
      aws_access_key_id=config['key'],aws_secret_access_key=config['secret'])
  client.head_bucket(Bucket=config['bucket'])
  if config['provider']=='backblaze-b2':
   acl=client.get_bucket_acl(Bucket=config['bucket'])
   if any(g.get('Grantee',{}).get('Type')=='Group' for g in acl.get('Grants',[])):
    result['state']='BLOCKED_BUCKET_HAS_PUBLIC_OR_UNVERIFIED_GROUP_GRANT';return result
  result['existing_private_bucket_readable']=True
  result['state']='EXISTING_PRIVATE_BUCKET_READABLE_NOT_MIGRATED_OR_ZERO_CHARGE_VERIFIED'
 except Exception:
  # SDK exception messages may contain signed URLs, bucket names or keys.
  result['state']='BLOCKED_EXISTING_BUCKET_ACCESS_OR_PRIVACY_CHECK_FAILED'
 return result

if __name__=='__main__':
 result=inspect(Path(__file__).resolve().parents[2]/'apps')
 print('READ_ONLY_INDEPENDENT_STORE_OBSERVATION',json.dumps(result,sort_keys=True),flush=True)
 if not result['existing_private_bucket_readable']:raise SystemExit(2)
