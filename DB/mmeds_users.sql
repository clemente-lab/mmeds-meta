-- CREATE USER 'mmeds_user'@'%' IDENTIFIED BY 'password';

GRANT EXECUTE ON FUNCTION mmeds.set_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.unset_connection_auth TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE protected_study TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE mmeds.user TO 'mmeds_user'@'%';

INSERT INTO security_token (username, security_token) VALUES ('mmeds_user@localhost', 'some_security_token');

INSERT INTO Study VALUES (1, 1, 'ExperimentOne', 1);
INSERT INTO Study VALUES (2, 2, 'ExperimentTwo', 2);
INSERT INTO Study VALUES (3, 3, 'ExperimentThree', 3);
