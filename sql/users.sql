DELIMITER //
DROP PROCEDURE IF EXISTS `mmeds_data1`.`add_users` //

CREATE PROCEDURE `mmeds_data1`.`add_users`()
BEGIN
    -- Only run this code when in a test database
    IF NOT (SELECT @@HOSTNAME) = 'data1' THEN
        IF EXISTS(SELECT 1 FROM mysql.user WHERE user = 'mmedsadmin') THEN
            DROP USER 'mmedsadmin'@'localhost';
            DELETE FROM security_token WHERE username='mmedsadmin@localhost';
        END IF;

        -- Create the user for the mmeds user activites
        CREATE USER 'mmedsadmin'@'localhost' IDENTIFIED BY 'password';

        IF EXISTS(SELECT 1 FROM mysql.user WHERE user = 'mmedsusers') THEN
            DROP USER 'mmedsusers'@'localhost';
            DELETE FROM security_token WHERE username='mmedsusers@localhost';
        END IF;

        -- Create the user for the mmeds user activites
        CREATE USER 'mmedsusers'@'localhost' IDENTIFIED BY 'password';
    END IF;

    -- Create a security token for that account
    INSERT INTO security_token (username, security_token) VALUES ('mmedsusers@localhost', 'some_security_token');

    IF NOT EXISTS(SELECT * FROM mmeds_data1.user WHERE user_id = 1) THEN
        INSERT INTO user VALUES (1, 'Public', '', '', '', 1);
    END IF;
END //

CALL `mmeds_data1`.`add_users`();

DROP PROCEDURE IF EXISTS `mmeds_data1`.`add_users` //

DELIMITER ;

-- Grant privileges to the account to be used by the webapp
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`set_connection_auth` TO 'mmedsusers'@'localhost';
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`unset_connection_auth` TO 'mmedsusers'@'localhost';
GRANT EXECUTE ON FUNCTION `mmeds_data1`.`owner_check` TO 'mmedsusers'@'localhost';

-- TEMPORARY PERMISSIONS FOR DEBUGGING GRANT SELECT ON TABLE mmeds_data1.user TO 'mmedsusers'@'localhost';
GRANT SELECT ON TABLE `mmeds_data1`.`session` TO 'mmedsusers'@'localhost';
GRANT SELECT ON TABLE `mmeds_data1`.`user` TO 'mmedsusers'@'localhost';
