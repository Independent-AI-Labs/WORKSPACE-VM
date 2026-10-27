select id, data from message where session_id = ? and time_created > ? and time_created <= ? order by time_created asc
