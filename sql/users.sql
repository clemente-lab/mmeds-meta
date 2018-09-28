DELIMITER //
DROP PROCEDURE IF EXISTS add_users //

CREATE PROCEDURE add_users()
BEGIN
  IF EXISTS(SELECT 1 FROM mysql.user WHERE user = 'mmeds_user') THEN
    DROP USER 'mmeds_user'@'%';
    DELETE FROM security_token WHERE username='mmeds_user@localhost';
  END IF;

  -- Create the user for the mmeds user activites
  CREATE USER 'mmeds_user'@'%' IDENTIFIED BY 'password';

  -- Create a security token for that account
  INSERT INTO security_token (username, security_token) VALUES ('mmeds_user@localhost', 'some_security_token');

  IF NOT EXISTS(SELECT * FROM mmeds.user WHERE user_id = 1) THEN
    INSERT INTO user VALUES (1, 'Public', '', '', '');
  END IF;
END //

CALL add_users();

DROP PROCEDURE IF EXISTS add_users //

DELIMITER ;

-- Grant privileges to the account to be used by the webapp
GRANT EXECUTE ON FUNCTION mmeds.set_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.unset_connection_auth TO 'mmeds_user'@'%';
GRANT EXECUTE ON FUNCTION mmeds.owner_check TO 'mmeds_user'@'%';

-- TEMPORARY PERMISSIONS FOR DEBUGGING GRANT SELECT ON TABLE mmeds.user TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE mmeds.session TO 'mmeds_user'@'%';
GRANT SELECT ON TABLE mmeds.user TO 'mmeds_user'@'%';
