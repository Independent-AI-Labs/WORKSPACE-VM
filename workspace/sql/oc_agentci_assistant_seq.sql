select max(seq) seq from event where aggregate_id = ? and type = 'message.updated.1' and json_extract(data, '$.info.id') = ?
