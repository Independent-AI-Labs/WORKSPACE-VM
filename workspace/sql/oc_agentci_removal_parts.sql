select data from event where aggregate_id = ? and json_extract(data, '$.part.messageID') = ? and json_extract(data, '$.part.type') = 'text' order by seq asc
