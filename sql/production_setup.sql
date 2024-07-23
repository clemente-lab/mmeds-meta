SET GLOBAL local_infile = true;
SET GLOBAL log_bin_trust_function_creators = 1;

source production_tables.sql;
source functions.sql;
source production_users.sql;
source production_views.sql;
source null_entries.sql;
source views.sql;
