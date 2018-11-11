get_manual_crl_info_query = '''SELECT
  mci.subjKeyId,
  mci.url
FROM manual_crl_info mci
WHERE mci.archive = 0
;'''


get_crl_hash_query = '''SELECT mcii.subjKeyId as crl_db_hash, mcii.crlLocation AS crl_location
FROM manual_crl_installed_info mcii
WHERE mcii.archive = 0
AND mcii.server = %(server)s
AND mcii.subjKeyId = '%(subjKeyId)s'
;'''


insert_crl_hash_query = '''INSERT INTO manual_crl_installed_info (server, subjKeyId, crlSha1Hash, createDateTime, lastStatus)
  VALUES (%(server)s, '%(subjKeyId)s', NULL, NOW(), 'AWAITING');'''


update_crl_hash_query_ok = '''UPDATE manual_crl_installed_info mcii
SET mcii.crlSha1Hash = '%(crl_file_hash)s',
mcii.crlLocation = '%(crl_actual_file)s',
mcii.updateDateTime = NOW(),
mcii.lastStatus = 'INSTALLED'
WHERE mcii.server = %(server)s
AND mcii.subjKeyId = '%(subjKeyId)s'
AND mcii.archive = 0
;'''


update_crl_hash_query_bad = '''UPDATE manual_crl_installed_info mcii
SET mcii.crlSha1Hash = '%(crl_file_hash)s',
mcii.crlLocation = '%(crl_bad_file)s',
mcii.updateDateTime = NOW(),
mcii.lastStatus = 'NOT_INSTALLED'
WHERE mcii.server = %(server)s
AND mcii.subjKeyId = '%(subjKeyId)s'
AND mcii.archive = 0
;'''


update_set_download_fail_query = '''UPDATE manual_crl_installed_info mcii
SET mcii.lastStatus = 'DOWNLOAD_FAILED'
WHERE mcii.server = %(server)s
AND mcii.subjKeyId = '%(subjKeyId)s'
AND mcii.archive = 0
;'''