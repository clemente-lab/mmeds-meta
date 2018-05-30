-- CREATE USER 'mmeds_user'@'%' IDENTIFIED BY 'password';

-- Grant privileges to the account to be used by the webapp
GRANT EXECUTE ON FUNCTION mmeds.set_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.unset_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.owner_check TO 'mmeds_user'@'%';

-- TEMPORARY PERMISSIONS FOR DEBUGGING GRANT SELECT ON TABLE mmeds.user TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE mmeds.session TO 'mmeds_user'@'%';

-- Create a security token for that account
INSERT INTO security_token (username, security_token) VALUES ('mmeds_user@localhost', 'some_security_token');

-- Populate the Study table
-- INSERT INTO Study VALUES (1, 1, 'ExperimentOne', 1);
-- INSERT INTO Study VALUES (2, 2, 'ExperimentTwo', 2);
-- INSERT INTO Study VALUES (3, 3, 'ExperimentThree', 3);

INSERT INTO user VALUES (1, 'Public', '', '');
