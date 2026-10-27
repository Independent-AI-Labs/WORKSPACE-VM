select seq, json_extract(data, '$.messageID') messageID from event where aggregate_id = ? and type = 'message.removed.1' and seq > ? order by seq asc limit 1
