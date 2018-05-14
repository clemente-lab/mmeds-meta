CREATE USER 'mmeds_user'@'%' IDENTIFIED BY 'password';

GRANT EXECUTE ON FUNCTION mmeds.set_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.unset_connection_auth TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE mmeds.protected_study TO 'mmeds_user'@'%';

INSERT INTO mmeds.user (user_id, username, password) VALUES (1, 'alice', '5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8');
INSERT INTO mmeds.user (user_id, username, password) VALUES (2, 'bob', 'e38ad214943daad1d64c102faec29de4afe9da3d');
INSERT INTO mmeds.user (user_id, username, password) VALUES (3, 'eve', '21298df8a3277357ee55b01df9530b535cf08ec1');

INSERT INTO mmeds.Study VALUES (1, 1, 'ExperimentOne', 1);
INSERT INTO mmeds.Study VALUES (2, 2, 'ExperimentTwo', 2);
INSERT INTO mmeds.Study VALUES (3, 3, 'ExperimentThree', 3);
