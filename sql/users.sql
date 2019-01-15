DELIMITER //
DROP PROCEDURE IF EXISTS `mmeds_data1`.`add_users` //

CREATE PROCEDURE `mmeds_data1`.`add_users`()
BEGIN
  -- Create a security token for that account
  INSERT INTO security_token (username, security_token) VALUES ('mmedsusers@localhost', 'some_security_token');

  IF NOT EXISTS(SELECT * FROM mmeds_data1.user WHERE user_id = 1) THEN
    INSERT INTO user VALUES (1, 'Public', '', '', '');
  END IF;
END //

CALL `mmeds_data1`.`add_users`();

DROP PROCEDURE IF EXISTS `mmeds_data1`.`add_users` //

DELIMITER ;

-- Grant privileges to the account to be used by the webapp
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`set_connection_auth` TO 'mmedsusers'@'%';
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`unset_connection_auth` TO 'mmedsusers'@'%';
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`owner_check` TO 'mmedsusers'@'%';

-- TEMPORARY PERMISSIONS FOR DEBUGGING GRANT SELECT ON TABLE mmeds_data1.user TO 'mmedsusers'@'%';
GRANT SELECT ON TABLE `mmeds_data1`.`session` TO 'mmedsusers'@'%';
GRANT SELECT ON TABLE `mmeds_data1`.`user` TO 'mmedsusers'@'%';
