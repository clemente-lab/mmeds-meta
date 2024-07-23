SET GLOBAL local_infile = true;
SET GLOBAL log_bin_trust_function_creators = 1;

source sql/tables.sql;
source sql/functions.sql;
source sql/users.sql;
source sql/protected_views.sql;
source sql/null_entries.sql;
source sql/views.sql;
source sql/triggers.sql;

SET GLOBAL local_infile = true;
